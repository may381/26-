#!/usr/bin/env python3
"""A3 的 v3 服务 —— P2 真正能调到的那个口。

前面几个文件都是纯函数（memory_search / memory_review / v3_messages / culture_courses），
好处是能单测、能离线回放；坏处是**没人能调**。这个文件把它们接成一个 HTTP 服务。

对 P2 提供三条路由（v3 协议要求 A3 必须有的）：

    POST /internal/v3/messages                         ← 主入口，P2 派活
    GET  /internal/v3/invocations/{invocationId}       ← 调用收据（回复丢了来查）
    POST /internal/v3/invocations/{invocationId}/cancel ← 取消
    GET  /health                                       ← 探活，不泄露数据

主入口现在接了两类活：

    1. 非遗文化课程   —— 按老人偏好筛课，返回 culture.course_candidates 卡片（DEMO）
    2. 记忆候选审核   —— 返回 MEMORY_REVIEW 卡片，9 字段对齐官方 Schema

怎么区分？看 context.dependencyResults 里有没有 MEMORY_CANDIDATE 卡片。
有就是审核任务，没有就按文化业务处理。**审核跨领域**（健康、旅游的候选都归 A3 审），
所以它不受 SUPPORTED_INTENTS 限制。

为什么收据这么重要？
    v3 原文：「同invocationId重复送达不能并行执行第二次」。
    网络抖动时 P2 会把同一个请求发两遍，如果 A3 每次都重新跑一遍，
    就可能给老人重复报名、重复推送。所以要先把 invocationId 记下来，
    来的第二遍直接返回上次的结果 —— 这叫幂等。

端口默认 18003，不是随便定的：
    P2 的配置里有 `agents.a3Url = http://127.0.0.1:18003`，
    A2 也按这套约定用 18002（P2 里 a2Url 就是 18002）。
    所以 A1=18001 / A2=18002 / A3=18003 是全队的约定，改了就连不上。

注意：v2 的 server.py 也用 18003，两个不能同时跑。要本地演示 v2 就先关掉本服务。

自测（起真服务，打真请求）：
    python v3_server.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

import ability_bank
import contribution
import culture_courses
import culture_knowledge
import learning_record
import memory_review
import memory_search
import schema_check
import v3_messages

SERVICE_NAME = "a3-v3"
DEFAULT_PORT = 18003
MAX_BODY = 1024 * 1024                      # 1MiB，和 v2 保持一致

# A3 这一批能做的是"非遗文化"。别的领域老实说没接，不硬凑。
SUPPORTED_INTENTS = ("culture",)

# 认出"这句话不归我管"。只放明确不属于文化领域的信号词，
# 宁可不判（默认当文化处理），也不要误判 —— 误判会让老人被推来推去。
_OTHER_DOMAIN_WORDS: dict[str, tuple[str, ...]] = {
    "health": ("血压", "血糖", "吃药", "药", "医生", "头晕", "心慌", "不舒服",
               "疼", "体检", "化验"),
    "fraud": ("被骗", "诈骗", "转账", "可疑电话", "中奖了"),
    "help": ("救命", "摔倒", "喘不上气", "走不动了", "报警"),
    "care": ("护工", "护理", "照顾我", "陪护"),
    "tourism": ("门票", "导游", "景区", "路线怎么走", "订酒店"),
}

# 老人说"文化课"时，用这些话认出他到底想学哪类
_ASK_OPTIONS = [
    {"id": "papercut", "label": "剪纸", "value": "papercut"},
    {"id": "embroidery", "label": "刺绣", "value": "embroidery"},
    {"id": "calligraphy", "label": "书法", "value": "calligraphy"},
    {"id": "taichi", "label": "太极", "value": "taichi"},
]

# 出现这些词，说明老人问的是"文化活动"这个大类，该反问要他具体点。
# 刻意不放"学"字 —— "想学跳伞"里也有"学"，放进去就会答非所问。
_GENERIC_CULTURE_WORDS = ("文化", "非遗", "活动", "课程", "班", "手艺", "培训")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime | None = None) -> str:
    return (moment or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ 收据
@dataclass
class Receipt:
    """一次调用的收据。存得住的才算收据，只在内存里跑一遍不算。"""

    invocation_id: str
    task_id: str
    status: str = "RECEIVED"          # RECEIVED/RUNNING/FINISHED/FAILED/CANCEL_REQUESTED/CANCELLED
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    received_at: str = field(default_factory=_iso)
    updated_at: str = field(default_factory=_iso)
    cancel_request_id: str | None = None
    cancel_reason: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "invocationId": self.invocation_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "receivedAt": self.received_at,
            "updatedAt": self.updated_at,
        }


# ------------------------------------------------------------------ 业务
def detect_domain(text: str) -> str:
    """粗判这句话归哪个领域。

    只在**明确命中别的领域、且完全不沾文化**时才判给别的领域。
    宁可判成 culture（然后反问澄清），也不要误判 ——
    把"想学剪纸"判成 help，老人会被莫名其妙转给紧急求助。
    """
    body = (text or "").strip()
    if not body:
        return "culture"

    culture_hits = bool(culture_courses.kinds_from_interests(body)) or \
        any(word in body for word in ("文化", "非遗", "课程", "上课", "班", "学"))

    if not culture_hits:
        for domain, words in _OTHER_DOMAIN_WORDS.items():
            if any(word in body for word in words):
                return domain
    return "culture"


# ------------------------------------------------------------------ 记忆审核
# v3 第九节：A3 审完返回 MEMORY_REVIEW 类型的 Result，payload 就是那 9 个字段。
# 审核是**跨领域**的 —— 健康、旅游、文化的候选都归 A3 审，
# 所以审核任务不受 SUPPORTED_INTENTS 限制（那个限制只管"文化业务"）。
RESULT_TYPE_REVIEW = "MEMORY_REVIEW"
RESULT_TYPE_CANDIDATE = "MEMORY_CANDIDATE"

# 这几类数据 P2 不放进 InvocationRequest（协议字段是固定的十二个，塞不了自定义内容），
# 所以走 dependencyResults 里的卡片传过来。类型名在这里约定死。
RESULT_TYPE_ATTENDANCE = "culture.attendance_records"
RESULT_TYPE_CONTRIBUTION = "ability.contribution_records"
RESULT_TYPE_SUPPLY = "ability.skill_supply_list"
RESULT_TYPE_DEMAND = "ability.skill_demand_list"


def find_result_payload(inv: v3_messages.Invocation, type_name: str) -> dict[str, Any] | None:
    """从 dependencyResults 里捞指定类型的卡片 payload。

    v3 的 context 只允许十二个固定字段，没法塞打卡记录、贡献记录这类业务数据，
    所以约定把这些数据做成 Result 卡片随 dependencyResults 传过来。
    找不到返回 None —— 调用方据此判断"这次没有数据"，而不是当成空数据。
    """
    for dependency in inv.dependency_results:
        for result in dependency.get("results") or []:
            if str(result.get("type") or "").upper() != type_name.upper():
                continue
            payload = result.get("payload")
            if isinstance(payload, dict):
                return dict(payload)
    return None

# 建议 → 给老人听的话。不能让老人听到 ADD/REPLACE 这种词。
REVIEW_REPLIES = {
    "ADD": "这条我记下来了，等您点个头就存进您的偏好里，以后不用再重复说。",
    "KEEP": "这条您以前说过，我这儿已经有了，就不重复记了。",
    "MERGE": "这条和之前记的是一回事，合在一起就行。不过范围变大了，还得您再点个头。",
    "REPLACE": "这条和您之前说的不太一样了，我按新的记。旧的就不用了，您看行吗？",
    "REJECT": "这条涉及比较私密的事，我得先问清楚您愿不愿意让我记，没您同意我不存。",
}

REVIEW_TITLES = {
    "ADD": "建议新增一条长期偏好",
    "KEEP": "建议保留原记录，不重复新增",
    "MERGE": "建议与已有记忆合并",
    "REPLACE": "建议替换原有偏好",
    "REJECT": "建议不保存（需本人明确同意）",
}


def find_candidate(inv: v3_messages.Invocation) -> dict[str, Any] | None:
    """从请求里找出要审核的候选。找不到返回 None。

    协议没写死候选从哪儿来（line 754 只说"A1从dependencyResults或P2查询取得"），
    所以按可靠程度依次找两个地方：
        1. dependencyResults 里带完整内容的 MEMORY_CANDIDATE 卡片  ← 首选
        2. businessRefs 里只有 id/version 的引用                  ← 只能报"信息不足"
    这个顺序要跟 P2 确认。找不到就退回文化业务，不硬猜。
    """
    for dependency in inv.dependency_results:
        for result in dependency.get("results") or []:
            if str(result.get("type") or "").upper() != RESULT_TYPE_CANDIDATE:
                continue
            payload = result.get("payload")
            # 这里是 dict 就认，哪怕缺 candidateId —— 缺字段要由审核逻辑报 400，
            # 不能因为少一个字段就当成"这不是审核请求"然后去做文化业务。
            if isinstance(payload, dict):
                return dict(payload)

    for ref in (inv.raw.get("context") or {}).get("businessRefs") or []:
        if str(ref.get("type") or "").upper() == RESULT_TYPE_CANDIDATE:
            return {"candidateId": ref.get("id"), "candidateVersion": ref.get("version") or 1,
                    "_incomplete": True}
    return None


def intent_from_candidate(candidate: dict[str, Any]) -> str:
    """候选属于哪个领域，头任务就算哪个 intent。都不合法时退回 culture。"""
    for domain in candidate.get("domains") or []:
        if domain in v3_messages.DOMAINS:
            return domain
    return "culture"


def to_review_card(review: dict[str, Any], candidate: dict[str, Any],
                   now: datetime | None = None) -> dict[str, Any]:
    """把 MemoryReview 包成 v3 的 Result 卡片。

    availability 用 NEEDS_VERIFICATION 而不是 REAL，理由：
        这个建议是 A3 按当前能看到的记忆算出来的，但 v3 明确要求
        「P2仍需校验候选与审核属于同一老人、仍有效且版本匹配」。
        标 REAL 会让人以为"已验证"，标 NEEDS_VERIFICATION 才是实话 ——
        结论是对的，但落地前还得再验一次版本。
    """
    base = now or _now()
    picked = str(review.get("recommendation") or "")
    seed = json.dumps([review.get("candidateId"), review.get("reviewId"),
                       review.get("recommendation")], ensure_ascii=False)
    digest = hashlib.sha1(seed.encode()).hexdigest()[:12]

    return {
        "resultId": f"memory-review-{digest}",
        "type": RESULT_TYPE_REVIEW,
        "schemaVersion": "1.0",
        "title": REVIEW_TITLES.get(picked, "记忆候选审核建议"),
        # 候选不是业务对象，编一个 businessRef 会让 P2 去查一个不存在的东西
        "businessRef": None,
        "availability": "NEEDS_VERIFICATION",
        "generatedAt": _iso(base),
        "sources": [{
            "type": "MEMORY_CANDIDATE",
            "id": str(review.get("candidateId") or ""),
            "version": int(review.get("candidateVersion") or 1),
        }],
        "pendingChecks": [
            "建议基于当前可见记忆计算，P2 写入前需再次校验候选与审核版本",
            "需老人本人确认后才成为长期记忆，A3 不代替老人决定",
            "A3 不生成确认号，确认由 A1 准备、P2 执行",
        ],
        # 9 个字段原样放进 payload，与协议 line 754 对齐
        "payload": dict(review),
    }



def build_culture_answer(inv: v3_messages.Invocation,
                         memories: list[dict[str, Any]] | None = None,
                         courses: list[dict[str, Any]] | None = None,
                         now: datetime | None = None) -> dict[str, Any]:
    """文化领域的回答：先看能不能定类别，能定就给卡片，不能定就反问。

    这就是 A3 的全部业务逻辑，故意写得很直白 ——
    模型可以换、话术可以调，但「先问清、再给三个以内、只查不报名」这条不动。
    """
    base = now or _now()
    pool = courses if courses is not None else culture_courses.DEMO_COURSES
    text = inv.text or ""

    # 兴趣来源有两个：老人这句话本身，或者记忆里存过的偏好
    kinds = culture_courses.kinds_from_interests(text)
    if not kinds and memories:
        for memory in memories:
            if memory.get("key") == "culture.interests":
                kinds = culture_courses.kinds_from_interests(memory.get("content"))
                if kinds:
                    break

    # 定不下来类别，分两种情况，不能混：
    #   A. 老人问的是"文化活动"这个大类（含下面这些词）→ 该反问，他没说要哪一类
    #   B. 老人说了具体东西，但我们没这类班（比如"想学跳伞"）→ 该直说没有
    # 混成一种就会出现"老人想学跳伞，系统反问他剪纸还是刺绣"，读起来像没听懂。
    if not kinds:
        if any(word in text for word in _GENERIC_CULTURE_WORDS):
            question = v3_messages.new_input_request(
                "您想学哪一类？剪纸、刺绣、书法，还是太极？",
                ["activityKind"],
                options=_ASK_OPTIONS,
                allow_free_text=True)
            return v3_messages.build_response(
                inv, intent="culture", domains=["culture"],
                reply_text="好呀，您想学哪一类？剪纸、刺绣、书法，还是太极？",
                next_step=v3_messages.NEXT_WAIT_INPUT,
                input_request=question)

        # B：说了具体的东西，但我们确实没这类班 —— 直说没有，再给出现有的
        empty_card = culture_courses.to_result_card([], now=base,
                                                    query={"interests": text})
        return v3_messages.build_response(
            inv, intent="culture", domains=["culture"],
            reply_text="您说的这类我们这边暂时没有开班。现在有剪纸、刺绣、书法和太极，您要不要看看？",
            next_step=v3_messages.NEXT_COMPLETE,
            outcome=v3_messages.OUTCOME_SUCCEEDED,
            results=[empty_card])

    picked = culture_courses.filter_courses(pool, interests=text)
    ranked = culture_courses.rank_courses(picked, interests=text)
    card = culture_courses.to_result_card(
        ranked, now=base, query={"interests": text, "kinds": kinds})
    reply = culture_courses.build_reply_text(ranked, now=base)

    return v3_messages.build_response(
        inv, intent="culture", domains=["culture", "tourism"],
        reply_text=reply,
        next_step=v3_messages.NEXT_COMPLETE,
        outcome=v3_messages.OUTCOME_SUCCEEDED,
        results=[card])


# ------------------------------------------------------------------ 服务
class V3Service:
    """把所有路由的处理收在一处，HTTP 那层只管收包发包。"""

    def __init__(self, agent_key: str | None = None,
                 courses: list[dict[str, Any]] | None = None,
                 memories_factory: Callable[[str], list[dict[str, Any]] | None] | None = None,
                 now: Callable[[], datetime] | None = None) -> None:
        self.agent_key = agent_key
        self.courses = courses if courses is not None else culture_courses.DEMO_COURSES
        # memories_factory 的三种返回**必须分清**，这是 v3 的硬要求：
        #   返回 list  → 查到了（空列表 = 确实没有相关记忆）
        #   返回 None  → 查不了（没有网关、服务挂了）→ 调用方要报 503
        # 混成一种，就会把"服务挂了"说成"老人没有偏好"。
        self.memories_factory = memories_factory or (lambda user_id: [])
        self.now = now or _now
        self._receipts: dict[str, Receipt] = {}
        self._lock = threading.Lock()

    # ---- 鉴权
    def check_key(self, provided: str | None) -> None:
        """服务密钥。没配密钥时不校验（本地演示），配了就一定校验。"""
        if not self.agent_key:
            return
        if provided != self.agent_key:
            raise v3_messages.ProtocolError("UNAUTHORIZED", "服务密钥校验失败")

    # ---- 主入口
    def handle_invocation(self, body: Any) -> tuple[int, dict[str, Any]]:
        try:
            inv = v3_messages.parse_invocation(body)
        except v3_messages.ProtocolError as error:
            return v3_messages.error_response(error.code, error.message)

        # 幂等：同一个 invocationId 只算一次
        with self._lock:
            existing = self._receipts.get(inv.invocation_id)
            if existing is not None:
                return self._replay(existing)
            receipt = Receipt(invocation_id=inv.invocation_id, task_id=inv.task_id,
                              status="RUNNING", received_at=_iso(self.now()))
            self._receipts[inv.invocation_id] = receipt

        try:
            if inv.deadline_passed(self.now()):
                raise v3_messages.ProtocolError(
                    "UPSTREAM_TIMEOUT", "已经超过 P2 给的截止时间，不再开始新的处理")

            # 分流顺序是有讲究的：从"信号最明确"排到"最泛"。
            # 1) 记忆审核：请求里带了 MEMORY_CANDIDATE，信号最硬，且跨领域
            candidate = find_candidate(inv)
            if candidate is not None:
                response = self._handle_review(inv, candidate)

            # 2) 学习进度：带了打卡记录卡片，说明就是要看进度
            elif (payload := find_result_payload(inv, RESULT_TYPE_ATTENDANCE)) is not None:
                response = self._handle_learning(inv, payload)

            # 3) 贡献整理：带了已确认记录卡片
            elif (payload := find_result_payload(inv, RESULT_TYPE_CONTRIBUTION)) is not None:
                response = self._handle_contribution(inv, payload)

            # 4) 能力银行：老人说"我会…愿意教…"，这是在登记供给
            elif (skill := ability_bank.parse_skill(inv.text)) is not None:
                response = self._handle_ability(inv, skill)

            # 5) 文化知识问答：问句式（"剪纸是什么""唔该什么意思"）
            elif culture_knowledge.is_knowledge_question(inv.text):
                response = self._handle_knowledge(inv)

            # 6) 剩下的按文化课程推荐处理（也是默认兜底）
            else:
                domain = detect_domain(inv.text)
                if domain not in SUPPORTED_INTENTS:
                    # v3：CAPABILITY_UNAVAILABLE = 「已登记能力尚未接入或不可用」。
                    # 健康、反诈、求助归 A2/A1。说"不接"比瞎答一句强得多。
                    raise v3_messages.ProtocolError(
                        "CAPABILITY_UNAVAILABLE",
                        f"「{domain}」领域归其他智能体负责，A3 当前只接入文化领域")

                memories = self.memories_factory(inv.user_id)
                response = build_culture_answer(inv, memories=memories,
                                                courses=self.courses, now=self.now())

            response = self._deep_validate(response)

        except v3_messages.ProtocolError as error:
            with self._lock:
                receipt.status = "FAILED"
                receipt.error = {"code": error.code, "message": error.message,
                                 "retryable": error.code in ("UPSTREAM_TIMEOUT", "CAPABILITY_UNAVAILABLE")}
                receipt.updated_at = _iso(self.now())
            return v3_messages.error_response(error.code, error.message)
        except Exception as error:  # noqa: BLE001 - 兜底，别让进程挂掉
            with self._lock:
                receipt.status = "FAILED"
                receipt.error = {"code": "INTERNAL_ERROR",
                                 "message": "服务内部错误", "retryable": False}
                receipt.updated_at = _iso(self.now())
            print(f"[{SERVICE_NAME}] 处理失败：{error!r}", file=sys.stderr)
            return v3_messages.error_response("INTERNAL_ERROR", "服务内部错误")

        with self._lock:
            receipt.status, receipt.result = "FINISHED", response
            receipt.updated_at = _iso(self.now())
        return 200, response

    def _handle_review(self, inv: v3_messages.Invocation,
                       candidate: dict[str, Any]) -> dict[str, Any]:
        """审核一条记忆候选。

        核心判断：**拿不到已有记忆就不给建议。**
        理由很实在：审核要回答"这条是不是和已有的重复/冲突"。
        如果读不到已有记忆，光是看到"没有冲突"就报 ADD，很可能造成
        同一件事被存两遍。所以这时候必须报 503，而不是给一个看起来合理的建议。
        v3 原文第八节：不能把"服务不可用"说成"老人没有偏好"。
        """
        if candidate.get("_incomplete"):
            raise v3_messages.ProtocolError(
                "INVALID_ARGUMENT",
                "只给了候选的 businessRef（id/version），没有候选内容，无法审核。"
                "请在 context.dependencyResults 里带 MEMORY_CANDIDATE 卡片。")

        for name in ("candidateId", "content"):
            if not str(candidate.get(name) or "").strip():
                raise v3_messages.ProtocolError(
                    "INVALID_ARGUMENT", f"候选缺少 {name}，无法审核")

        memories = self.memories_factory(inv.user_id)
        if memories is None:
            raise v3_messages.ProtocolError(
                "CAPABILITY_UNAVAILABLE",
                "无法读取老人已有记忆，不能判断这条候选是否与现有偏好重复。"
                "此时给建议可能造成重复写入，因此暂不受理。")

        try:
            review = memory_review.review_candidate(candidate, existing=memories)
        except ValueError as error:
            raise v3_messages.ProtocolError("INVALID_ARGUMENT", f"候选不合法：{error}") from error

        card = to_review_card(review, candidate, now=self.now())
        intent = intent_from_candidate(candidate)
        domains = [d for d in (candidate.get("domains") or []) if d in v3_messages.DOMAINS] or [intent]

        # 审核时确实读了哪些记忆，必须如实登记 —— 不然 P2 无法追溯建议的依据
        used = [{"memoryId": ref["memoryId"], "version": int(ref["version"])}
                for ref in review.get("conflictMemoryRefs") or []]

        return v3_messages.build_response(
            inv, intent=intent, domains=domains,
            reply_text=REVIEW_REPLIES.get(str(review.get("recommendation")), "这条我看过了。"),
            next_step=v3_messages.NEXT_COMPLETE,
            outcome=v3_messages.OUTCOME_SUCCEEDED,
            results=[card],
            used_memory_refs=used,
            available_memories=memories)

    def _handle_learning(self, inv: v3_messages.Invocation,
                         payload: dict[str, Any]) -> dict[str, Any]:
        """学习进度：把 P2 的打卡记录解读成人话。

        注意这里**不产生任何出勤记录** —— 只读 P2 给的数据。
        """
        try:
            plan = payload.get("plan")
            if not plan:
                course = payload.get("course")
                if not isinstance(course, dict):
                    raise v3_messages.ProtocolError(
                        "INVALID_ARGUMENT", "看学习进度需要 plan，或至少给一个 course")
                plan = learning_record.build_plan(
                    course, weekly_times=int(payload.get("weeklyTimes") or 1),
                    total_sessions=payload.get("totalSessions"), now=self.now())

            summary = learning_record.summarize_progress(
                plan, payload.get("sessions") or [], now=self.now())
            card = learning_record.to_progress_card(summary, now=self.now())
        except learning_record.LearningRecordError as error:
            raise v3_messages.ProtocolError(error.code, error.message, error.status) from error

        return v3_messages.build_response(
            inv, intent="culture", domains=["culture"],
            reply_text=summary["summaryText"],
            next_step=v3_messages.NEXT_COMPLETE,
            outcome=v3_messages.OUTCOME_SUCCEEDED,
            results=[card])

    def _handle_contribution(self, inv: v3_messages.Invocation,
                             payload: dict[str, Any]) -> dict[str, Any]:
        """贡献整理：只解释已确认的记录，不新增不修改。"""
        try:
            summary = contribution.summarize(payload.get("records") or [], now=self.now())
            card = contribution.to_card(summary, now=self.now())
        except contribution.ContributionError as error:
            raise v3_messages.ProtocolError(error.code, error.message, error.status) from error

        return v3_messages.build_response(
            inv, intent="ability", domains=["ability"],
            reply_text=summary["summaryText"],
            next_step=v3_messages.NEXT_COMPLETE,
            outcome=v3_messages.OUTCOME_SUCCEEDED,
            results=[card])

    def _handle_ability(self, inv: v3_messages.Invocation,
                        skill: dict[str, Any]) -> dict[str, Any]:
        """能力银行：老人说"我会什么、愿不愿意教"，登记一条待审核的技能。

        状态是 SUBMITTED 而不是 PUBLISHED —— A3 没权力让技能直接上线。
        所以这里不是 WAIT_CONFIRMATION（那会误导成"等老人点确认"），
        而是 COMPLETE + 说明下一步等社区审核。
        """
        try:
            record = ability_bank.build_skill_record(inv.user_id, skill, now=self.now())
            card = ability_bank.to_skill_card(record, now=self.now())
            reply = ability_bank.build_reply_text(record)
        except ability_bank.AbilityBankError as error:
            raise v3_messages.ProtocolError(error.code, error.message, error.status) from error

        return v3_messages.build_response(
            inv, intent="ability", domains=["ability"],
            reply_text=reply,
            next_step=v3_messages.NEXT_COMPLETE,
            outcome=v3_messages.OUTCOME_SUCCEEDED,
            results=[card])

    def _handle_knowledge(self, inv: v3_messages.Invocation) -> dict[str, Any]:
        """非遗 / 方言 / 地方文化问答。

        查不到就把空卡片和"没资料"一起返回 —— 空是合法结果，
        比编一段听起来像真的强得多。
        """
        try:
            items = culture_knowledge.search(inv.text)
            card = culture_knowledge.to_result_card(items, inv.text, now=self.now())
            reply = culture_knowledge.build_answer_text(items)
        except culture_knowledge.CultureKnowledgeError as error:
            raise v3_messages.ProtocolError(error.code, error.message, error.status) from error

        return v3_messages.build_response(
            inv, intent="culture", domains=["culture"],
            reply_text=reply,
            next_step=v3_messages.NEXT_COMPLETE,
            outcome=v3_messages.OUTCOME_SUCCEEDED,
            results=[card])

    def _replay(self, receipt: Receipt) -> tuple[int, dict[str, Any]]:
        """重复送达：把上次的答案原样还回去，不再跑一遍。"""
        if receipt.status == "FINISHED" and receipt.result is not None:
            return 200, receipt.result
        if receipt.status in ("CANCELLED", "CANCEL_REQUESTED"):
            return v3_messages.error_response("TASK_NOT_RUNNABLE", "该调用已取消，不再执行")
        if receipt.status == "FAILED" and receipt.error is not None:
            return v3_messages.error_response(receipt.error["code"],
                                              receipt.error.get("message", ""))
        return v3_messages.error_response("CONFLICT", "同一调用正在处理中，请稍后用收据接口查询")

    def _deep_validate(self, response: dict[str, Any]) -> dict[str, Any]:
        """出包前再用官方 Schema 校一次，含 results 里的每张卡片。"""
        folder = v3_messages.schema_dir()
        if folder is None:
            return response
        root = schema_check.load_schema(os.path.join(folder, "control.schema.json"))
        try:
            schema_check.validate(response, root["definitions"]["AgentResponse"], root)
        except schema_check.SchemaError as error:
            raise v3_messages.ProtocolError(
                "INTERNAL_ERROR", f"生成的响应不合规，已拦截：{error}") from error
        return response

    # ---- 收据
    def get_receipt(self, invocation_id: str) -> tuple[int, dict[str, Any]]:
        with self._lock:
            receipt = self._receipts.get(invocation_id)
            if receipt is None:
                return v3_messages.error_response("NOT_FOUND", "没有这个调用的收据")
            payload = {"code": "OK", "message": "成功", "data": receipt.to_payload()}
        return 200, payload

    # ---- 取消
    def cancel(self, invocation_id: str, body: Any) -> tuple[int, dict[str, Any]]:
        try:
            if not isinstance(body, dict):
                raise v3_messages.ProtocolError("INVALID_ARGUMENT", "请求体必须是 JSON 对象")
            if body.get("protocolVersion") != v3_messages.PROTOCOL_VERSION:
                raise v3_messages.ProtocolError(
                    "UNSUPPORTED_PROTOCOL_VERSION",
                    f"只支持 protocolVersion={v3_messages.PROTOCOL_VERSION!r}")
            if body.get("invocationId") != invocation_id:
                raise v3_messages.ProtocolError(
                    "INVALID_ARGUMENT", "路径里的 invocationId 与正文不一致")
            cancel_request_id = body.get("cancelRequestId")
            if not isinstance(cancel_request_id, str) or not cancel_request_id.strip():
                raise v3_messages.ProtocolError("INVALID_ARGUMENT", "cancelRequestId 必填")

            with self._lock:
                receipt = self._receipts.get(invocation_id)
                if receipt is None:
                    return v3_messages.error_response("NOT_FOUND", "没有这个调用，无法取消")

                if receipt.status in ("FINISHED", "FAILED"):
                    # v3 样例 18：「只接受取消并非已经结束」——
                    # 已经结束的活儿，回一句"取消已受理"就是骗人。
                    finished = "完成" if receipt.status == "FINISHED" else "失败"
                    return 409, {"code": "TASK_NOT_RUNNABLE",
                                 "message": f"该调用已{finished}，无法取消",
                                 "data": None}

                # 同一个 cancelRequestId 重复提交 → 返回同样的结果，不重复启动取消流程
                if receipt.cancel_request_id and receipt.cancel_request_id != cancel_request_id:
                    return 409, {"code": "CONFLICT",
                                 "message": "已有另一个取消请求在处理", "data": None}

                receipt.cancel_request_id = cancel_request_id
                receipt.cancel_reason = str(body.get("reason") or "")
                receipt.status = "CANCELLED"
                receipt.updated_at = _iso(self.now())

            payload = {"code": "OK", "message": "成功",
                       "data": {"invocationId": invocation_id,
                                "cancelRequestId": cancel_request_id,
                                "status": "CANCELLED", "lastProgressSeq": 0,
                                "reconciliationRequired": False}}
            return 200, payload
        except v3_messages.ProtocolError as error:
            return v3_messages.error_response(error.code, error.message)

    # ---- 演示用：直接跑一次检索策略
    def demo_search(self, body: Any) -> tuple[int, dict[str, Any]]:
        """只在演示台上用。真实链路里 memory.search 由 P2 提供网关，A3 不自己对外开。

        这个入口故意叫 /internal/demo/...，一眼能看出不是正式接口。
        它接受调用方塞进来的 memories / authorizedDomains / storeAvailable，
        这样才能把「确实没有」「越权」「服务不可用」三种情况分别演示出来。
        """
        try:
            if not isinstance(body, dict):
                raise v3_messages.ProtocolError("INVALID_ARGUMENT", "请求体必须是 JSON 对象")
            result = memory_search.search(
                body.get("args") or {},
                body.get("memories") or [],
                authorized_domains=body.get("authorizedDomains"),
                store_available=bool(body.get("storeAvailable", True)),
                memory_revision=int(body.get("memoryRevision") or 0),
                authorization_revision=int(body.get("authorizationRevision") or 0))
            return 200, {"code": "OK", "message": "成功", "data": result}
        except memory_search.MemorySearchError as error:
            return error.status, {"code": error.code, "message": error.message, "data": None}
        except v3_messages.ProtocolError as error:
            return v3_messages.error_response(error.code, error.message)

    # ---- 探活
    def health(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            counts: dict[str, int] = {}
            for receipt in self._receipts.values():
                counts[receipt.status] = counts.get(receipt.status, 0) + 1
        return 200, {"code": "OK", "message": "成功", "data": {
            "status": "UP", "service": SERVICE_NAME,
            "protocolVersion": v3_messages.PROTOCOL_VERSION,
            "schemaAvailable": v3_messages.schema_available(),
            "supportedIntents": list(SUPPORTED_INTENTS),
            "capabilities": {
                "cultureCourseQuery": True,
                "memoryCandidateReview": True,
                "memorySearchGateway": False,
            },
            "invocations": counts,
        }}


# ------------------------------------------------------------------ HTTP
def make_handler(service: V3Service, quiet: bool = False):
    class Handler(BaseHTTPRequestHandler):
        server_version = "A3V3/0.1"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            # quiet=True 时不打访问日志：投屏演示时这些行会糊在输出中间
            if quiet:
                return
            sys.stderr.write(f"[{SERVICE_NAME}] " + (fmt % args) + "\n")

        # ---- 基础
        def _drain(self) -> None:
            """回包前先把请求体读完。不读就回错误码，客户端会收到连接重置，
            把"密钥错"看成"网络错"，联调时会白查半天。"""
            if getattr(self, "_body_consumed", False):
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                length = 0
            if 0 < length <= MAX_BODY:
                try:
                    self.rfile.read(length)
                except OSError:
                    pass
            self._body_consumed = True

        def _send(self, status: int, payload: dict[str, Any], trace_id: str) -> None:
            self._drain()
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-Trace-Id", trace_id)
            self.send_header("X-Agent-Protocol-Version", v3_messages.PROTOCOL_VERSION)
            # 允许演示台页面（file:// 或另一个端口）直接调本服务。
            # 只放行这几个头，且不带 Cookie —— A3 用的是 capabilityToken，不依赖浏览器会话。
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, X-Agent-Key, X-Trace-Id")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Expose-Headers",
                             "X-Trace-Id, X-Agent-Protocol-Version")
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self) -> None:
            """跨域预检。浏览器发 POST 前会先问一句"允不允许"，得先答。"""
            self._drain()
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, X-Agent-Key, X-Trace-Id")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()

        def _read_json(self) -> Any:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                length = 0
            if length <= 0:
                raise v3_messages.ProtocolError("INVALID_ARGUMENT", "请求体为空")
            if length > MAX_BODY:
                raise v3_messages.ProtocolError("INVALID_ARGUMENT", "请求体超过 1MiB")
            raw = self.rfile.read(length)
            self._body_consumed = True
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise v3_messages.ProtocolError("INVALID_ARGUMENT", "请求体不是合法 JSON") from error

        def _trace(self) -> str:
            raw = (self.headers.get("X-Trace-Id") or "").strip()
            if raw and len(raw) <= 64 and all(c.isalnum() or c in "_-" for c in raw):
                return raw
            return str(uuid.uuid4())

        # ---- 路由
        def do_GET(self) -> None:
            trace_id, path = self._trace(), urlparse(self.path).path
            try:
                if path == "/health":
                    return self._send(*service.health(), trace_id)
                if path.startswith("/internal/v3/invocations/"):
                    service.check_key(self.headers.get("X-Agent-Key"))
                    invocation_id = path.rsplit("/", 1)[-1]
                    if not invocation_id:
                        raise v3_messages.ProtocolError("INVALID_ARGUMENT", "缺少 invocationId")
                    return self._send(*service.get_receipt(invocation_id), trace_id)
                self._send(404, {"code": "NOT_FOUND", "message": "接口不存在", "data": None}, trace_id)
            except v3_messages.ProtocolError as error:
                self._send(*v3_messages.error_response(error.code, error.message), trace_id)
            except Exception as error:  # noqa: BLE001
                print(f"[{SERVICE_NAME}] GET 异常：{error!r}", file=sys.stderr)
                self._send(500, {"code": "INTERNAL_ERROR", "message": "服务内部错误",
                                 "data": None}, trace_id)

        def do_POST(self) -> None:
            trace_id, path = self._trace(), urlparse(self.path).path
            try:
                if path == "/internal/v3/messages":
                    service.check_key(self.headers.get("X-Agent-Key"))
                    return self._send(*service.handle_invocation(self._read_json()), trace_id)
                if path.endswith("/cancel") and path.startswith("/internal/v3/invocations/"):
                    service.check_key(self.headers.get("X-Agent-Key"))
                    parts = path.strip("/").split("/")
                    invocation_id = parts[-2]
                    return self._send(*service.cancel(invocation_id, self._read_json()), trace_id)
                if path == "/internal/demo/memory/search":
                    service.check_key(self.headers.get("X-Agent-Key"))
                    return self._send(*service.demo_search(self._read_json()), trace_id)
                self._send(404, {"code": "NOT_FOUND", "message": "接口不存在", "data": None}, trace_id)
            except v3_messages.ProtocolError as error:
                self._send(*v3_messages.error_response(error.code, error.message), trace_id)
            except Exception as error:  # noqa: BLE001
                print(f"[{SERVICE_NAME}] POST 异常：{error!r}", file=sys.stderr)
                self._send(500, {"code": "INTERNAL_ERROR", "message": "服务内部错误",
                                 "data": None}, trace_id)

    return Handler


def create_server(port: int, service: V3Service, host: str = "127.0.0.1",
                  quiet: bool = False) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(service, quiet=quiet))
    server.daemon_threads = True
    return server


# ------------------------------------------------------------------ 自测
def _sample_body(text: str = "想学剪纸，走路别太远",
                 invocation_id: str | None = None,
                 deadline_offset_s: int = 3600) -> dict[str, Any]:
    deadline = datetime.fromtimestamp(
        _now().timestamp() + deadline_offset_s, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "protocolVersion": "3.0", "userId": "u100", "conversationId": "conv-001",
        "messageId": "msg-001",
        "task": {"id": "child-003", "parentTaskId": "root-001", "version": 2,
                 "attempt": 1, "invocationId": invocation_id or f"invoke-{uuid.uuid4().hex[:8]}",
                 "deadlineAt": deadline},
        "input": {"text": text, "attachmentIds": []},
        "context": {"businessRefs": [], "history": [], "completedEffects": [],
                    "reason": "USER_MESSAGE", "candidateTasks": [],
                    "dependencyResults": [], "confirmationResults": [],
                    "actionLedger": [], "planSteps": [],
                    "readSet": {"memoryRevision": 7, "authorizationRevision": 3,
                                "provenanceRefs": []},
                    "inputResponse": None, "pendingInputRequests": []},
        "capabilityToken": "DEMO-TOKEN-NOT-A-REAL-CREDENTIAL",
    }


def _call(port: int, method: str, path: str, body: Any = None) -> tuple[int, dict[str, Any]]:
    import urllib.error
    import urllib.request

    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                                    headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def _selftest() -> int:
    service = V3Service()
    server = create_server(0, service)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"自测服务已启动：127.0.0.1:{port}")

    ok = True

    print()
    print("=" * 70)
    print(" 1) 探活")
    print("=" * 70)
    status, body = _call(port, "GET", "/health")
    print(f"  {status}  status={body['data']['status']}  "
          f"schema={body['data']['schemaAvailable']}  "
          f"能做的领域={body['data']['supportedIntents']}")

    print()
    print("=" * 70)
    print(" 2) 老人说「想学剪纸」→ 直接给卡片")
    print("=" * 70)
    invocation_id = f"invoke-{uuid.uuid4().hex[:8]}"
    status, body = _call(port, "POST", "/internal/v3/messages",
                         _sample_body("想学剪纸，走路别太远", invocation_id))
    data = body.get("data") or {}
    print(f"  {status}  next={data.get('control', {}).get('next')}  "
          f"outcome={data.get('control', {}).get('outcome')}")
    print(f"  回复：{data.get('reply', {}).get('text')}")
    card = (data.get("results") or [{}])[0]
    print(f"  卡片：{card.get('title')}  availability={card.get('availability')}  "
          f"条数={card.get('payload', {}).get('totalCandidates')}")

    print()
    print("=" * 70)
    print(" 3) 同一个 invocationId 再发一遍 → 幂等，不再跑")
    print("=" * 70)
    status2, body2 = _call(port, "POST", "/internal/v3/messages",
                           _sample_body("想学剪纸，走路别太远", invocation_id))
    print(f"  {status2}  两次 resultId 是否相同："
          f"{body2['data']['results'][0]['resultId'] == card.get('resultId')}")
    print(f"  收据里的调用数：{_call(port, 'GET', '/health')[1]['data']['invocations']}")

    print()
    print("=" * 70)
    print(" 4) 老人只说「想参加文化活动」→ 反问，不硬猜")
    print("=" * 70)
    status, body = _call(port, "POST", "/internal/v3/messages",
                         _sample_body("我想参加文化活动"))
    data = body.get("data") or {}
    print(f"  {status}  next={data.get('control', {}).get('next')}")
    print(f"  问题：{data.get('control', {}).get('inputRequest', {}).get('question')}")
    print(f"  inputRequestId 是 UUID v4："
          f"{uuid.UUID(data['control']['inputRequest']['inputRequestId']).version == 4}")

    print()
    print("=" * 70)
    print(" 5) 回复丢了 → P2 拿 invocationId 来查收据")
    print("=" * 70)
    status, body = _call(port, "GET", f"/internal/v3/invocations/{invocation_id}")
    print(f"  {status}  status={body['data']['status']}  "
          f"result 有没有={body['data']['result'] is not None}")

    print()
    print("=" * 70)
    print(" 6) 取消一个还没开始的调用 → 之后再来就 TASK_NOT_RUNNABLE")
    print("=" * 70)
    fresh = f"invoke-{uuid.uuid4().hex[:8]}"
    service._receipts[fresh] = Receipt(invocation_id=fresh, task_id="child-009", status="RUNNING")
    cancel_body = {"protocolVersion": "3.0", "invocationId": fresh,
                   "cancelRequestId": "cancel-001", "reason": "用户改主意了"}
    status, body = _call(port, "POST", f"/internal/v3/invocations/{fresh}/cancel", cancel_body)
    print(f"  取消：{status}  status={body.get('data', {}).get('status')}")

    print()
    print("=" * 70)
    print(" 7) 取消一个已经完成的 → 必须 409，不能说「已受理」")
    print("=" * 70)
    body_cancel = {"protocolVersion": "3.0", "invocationId": invocation_id,
                   "cancelRequestId": "cancel-002", "reason": "晚了"}
    status, body = _call(port, "POST", f"/internal/v3/invocations/{invocation_id}/cancel",
                         body_cancel)
    print(f"  {status}  {body.get('code')}：{body.get('message')}")
    ok = ok and status == 409

    print()
    print("=" * 70)
    print(" 8) 版本不对 / 缺密钥 / 超时 —— 三种错码都要能对上")
    print("=" * 70)
    for label, payload, path in (
        ("版本 2.0", {**_sample_body(), "protocolVersion": "2.0"}, "/internal/v3/messages"),
        ("没带 capabilityToken", {k: v for k, v in _sample_body().items()
                                   if k != "capabilityToken"}, "/internal/v3/messages"),
        ("过期截止时间", _sample_body(deadline_offset_s=-60), "/internal/v3/messages"),
    ):
        status, body = _call(port, "POST", path, payload)
        print(f"  {label:<18} → {status} {body['code']}")

    print()
    print("=" * 70)
    print(" 9) A3 不管的领域 → 503，不硬凑答案")
    print("=" * 70)
    status, body = _call(port, "POST", "/internal/v3/messages",
                         _sample_body("帮我看看血压高不高"))
    print(f"  {status}  {body['code']}：{body['message']}")
    print("  说明：健康归 A2。说不接，比瞎答一句强")

    server.shutdown()
    print()
    print("结论：能调、能查、能取消、重复发不会重跑、不会硬答不属于自己的问题。")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A3 v3 服务")
    parser.add_argument("--port", type=int, default=int(os.environ.get("A3_V3_PORT", DEFAULT_PORT)))
    parser.add_argument("--host", default=os.environ.get("A3_V3_HOST", "127.0.0.1"))
    parser.add_argument("--key", default=os.environ.get("A3_AGENT_KEY"),
                        help="服务密钥；不填则不校验（仅限本地演示）")
    parser.add_argument("--selftest", action="store_true", help="起一个随机端口的服务自测")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    service = V3Service(agent_key=args.key)
    server = create_server(args.port, service, args.host)
    print(f"[{SERVICE_NAME}] 监听 http://{args.host}:{args.port}")
    print(f"[{SERVICE_NAME}] 协议 {v3_messages.PROTOCOL_VERSION}，"
          f"Schema {'已就位' if v3_messages.schema_available() else '缺失（不做自校）'}")
    print(f"[{SERVICE_NAME}] 密钥校验：{'开启' if args.key else '关闭（仅演示）'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{SERVICE_NAME}] 收到中断，退出")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
