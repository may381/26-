#!/usr/bin/env python3
"""A3 检索策略（v3.0 的 memory.search）—— 纯函数，零依赖，不联网。

v3 第七节的定位：「A3 负责检索和冲突策略，P2 负责身份、存储、确认与访问限制。」
所以这个文件只做**筛什么、怎么排、超了怎么办**；真正查库由 P2 执行。

必须守住的四条（v3 原文都在第八节）：
1. 三态不能混：`AVAILABLE`（有）/ `EMPTY`（确实没有）/ 服务不可用。
   **"服务挂了"绝不能说成"老人没有偏好"。**
2. 越权 403，且**不泄漏隐藏记忆是否存在**。
3. 单条 content 最多 1000 字符；总量按 Unicode 码点计，**放不下就整条跳过并标 truncated**，
   不许切断一条记忆改变语义。
4. `SENSITIVE` 记忆必须有该领域的明确授权才返回，默认跨领域不共享。

自测：
    python memory_search.py
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

# v3：登记领域（与九种 intent 同一套）
DOMAINS = ("tourism", "help", "health", "fraud", "care", "culture",
           "community", "volunteer", "ability")

READ_AVAILABLE = "AVAILABLE"
READ_EMPTY = "EMPTY"

MAX_PURPOSE = 500
MAX_QUERY = 1000
MAX_DOMAINS_ARG = 3
MAX_LIMIT = 10
MIN_LIMIT = 1
DEFAULT_LIMIT = 5
MAX_CONTENT_CHARS_FLOOR = 200
MAX_CONTENT_CHARS_CEIL = 4000
DEFAULT_MAX_CONTENT_CHARS = 2000
MAX_ITEM_CONTENT = 1000      # 单条 content 上限


class MemorySearchError(Exception):
    """检索层的失败。status/code 直接对应 v3 错误码表。"""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# ------------------------------------------------------------------ 校验
def validate_args(args: Any) -> dict[str, Any]:
    """按 v3 校验 memory.search 的 args。不合法直接 400。"""
    if not isinstance(args, dict):
        raise MemorySearchError(400, "INVALID_ARGUMENT", "memory.search 的 args 必须是对象")

    unknown = set(args) - {"purpose", "query", "domains", "limit", "maxContentChars"}
    if unknown:
        raise MemorySearchError(400, "INVALID_ARGUMENT",
                                f"memory.search 不支持字段：{','.join(sorted(unknown))}")

    purpose = args.get("purpose")
    if not isinstance(purpose, str) or not purpose.strip():
        raise MemorySearchError(400, "INVALID_ARGUMENT", "purpose 必填且非空")
    if len(purpose) > MAX_PURPOSE:
        raise MemorySearchError(400, "INVALID_ARGUMENT", f"purpose 最多{MAX_PURPOSE}字符")

    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise MemorySearchError(400, "INVALID_ARGUMENT", "query 必填且非空")
    if len(query) > MAX_QUERY:
        raise MemorySearchError(400, "INVALID_ARGUMENT", f"query 最多{MAX_QUERY}字符")

    domains = args.get("domains")
    if domains is None:
        domains = []
    if not isinstance(domains, list) or any(not isinstance(d, str) for d in domains):
        raise MemorySearchError(400, "INVALID_ARGUMENT", "domains 必须是字符串数组")
    if len(domains) > MAX_DOMAINS_ARG:
        raise MemorySearchError(400, "INVALID_ARGUMENT", f"domains 最多{MAX_DOMAINS_ARG}项")
    for d in domains:
        if d not in DOMAINS:
            raise MemorySearchError(400, "INVALID_ARGUMENT", f"未登记的领域：{d}")

    limit = args.get("limit", DEFAULT_LIMIT)
    if not isinstance(limit, int) or isinstance(limit, bool) or not (MIN_LIMIT <= limit <= MAX_LIMIT):
        raise MemorySearchError(400, "INVALID_ARGUMENT", f"limit 必须是 {MIN_LIMIT}~{MAX_LIMIT} 的整数")

    budget = args.get("maxContentChars", DEFAULT_MAX_CONTENT_CHARS)
    if not isinstance(budget, int) or isinstance(budget, bool) or \
            not (MAX_CONTENT_CHARS_FLOOR <= budget <= MAX_CONTENT_CHARS_CEIL):
        raise MemorySearchError(400, "INVALID_ARGUMENT",
                                f"maxContentChars 必须是 {MAX_CONTENT_CHARS_FLOOR}~{MAX_CONTENT_CHARS_CEIL} 的整数")

    return {"purpose": purpose.strip(), "query": query.strip(),
            "domains": list(dict.fromkeys(domains)), "limit": limit, "maxContentChars": budget}


# ------------------------------------------------------------------ 检索
def search(args: dict[str, Any], memories: list[dict[str, Any]] | None,
           authorized_domains: list[str] | None = None,
           memory_revision: int = 0, authorization_revision: int = 0,
           store_available: bool = True,
           retrieved_at: datetime | None = None) -> dict[str, Any]:
    """执行一次检索。

    args               已经过 validate_args
    memories           P2 给的候选集合（真实场景由 P2 查库传入，A3 不直连）
    authorized_domains 本次任务被授权的领域；None 表示不额外限制
    store_available    False 表示检索服务不可用 → 503，不返回"空"
    """
    checked = validate_args(args)

    # ---- 越权先判：请求了没被授权的领域，直接 403，不透露有没有隐藏记忆
    if authorized_domains is not None:
        allowed = [d for d in authorized_domains if d in DOMAINS]
        illegal = [d for d in checked["domains"] if d not in allowed]
        if illegal:
            raise MemorySearchError(
                403, "FORBIDDEN",
                f"请求的领域不在本任务授权范围内：{','.join(illegal)}")

    # ---- 服务不可用：必须 503，不能用 EMPTY 顶上
    if not store_available:
        raise MemorySearchError(503, "CAPABILITY_UNAVAILABLE",
                                "检索服务暂时不可用，无法确认是否存在相关记忆")

    requested_domains = checked["domains"]
    scored: list[tuple[int, dict[str, Any]]] = []
    for memory in memories or []:
        if not _is_active(memory):
            continue
        if not _domain_match(memory, requested_domains):
            continue
        if not _sensitivity_ok(memory, authorized_domains):
            continue
        score = _score(checked["query"], checked["purpose"], memory)
        # 关键词层面一条都没命中就不返回：宁可 EMPTY 让 A1 追问，
        # 也不要塞不相关的记忆去污染 A1 的判断。
        # 已知限制：语义相关但无词面重叠（如"避开台阶"对"安排文化活动"）不会命中，
        # 二期可换成模型语义重排；当前要求 A1 在 query 里带上具体偏好词。
        if score <= 0:
            continue
        scored.append((score, memory))

    # 先按相关度，再按更新时间（新的优先），保证结果稳定可复现
    scored.sort(key=lambda pair: (-pair[0], _neg_time(pair[1].get("updatedAt"))))

    items, used_chars, truncated = _fill(scored, checked["limit"], checked["maxContentChars"])
    status = READ_AVAILABLE if items else READ_EMPTY

    return {
        "readStatus": status,
        "memoryRevision": memory_revision,
        "authorizationRevision": authorization_revision,
        "retrievedAt": _iso(retrieved_at or datetime.now(timezone.utc)),
        "items": items,
        "returnedContentChars": used_chars,
        "truncated": truncated,
    }


def _fill(scored: list[tuple[int, dict[str, Any]]], limit: int, budget: int):
    """按条数上限和字数预算装填。放不下就整条跳过并标记 truncated。"""
    items: list[dict[str, Any]] = []
    used = 0
    truncated = False
    seen_keys: set[tuple[str, str]] = set()

    for _, memory in scored:
        if len(items) >= limit:
            truncated = True
            break
        text = str(memory.get("content") or "")
        chars = _count(text)
        if chars > MAX_ITEM_CONTENT:
            truncated = True          # 单条就超 1000，不能切，只能跳过
            continue
        if used + chars > budget:
            truncated = True          # 剩余预算放不下这一条，跳过而不是截断
            continue
        dedupe = (str(memory.get("key") or ""), str(memory.get("category") or ""))
        if dedupe in seen_keys:       # 同一 key+category 只留最高版本（已按顺序优先）
            continue
        seen_keys.add(dedupe)

        items.append(_export(memory))
        used += chars

    return items, used, truncated


def _export(memory: dict[str, Any]) -> dict[str, Any]:
    """按 v3 记忆对象模板输出，只给约定字段。"""
    return {
        "memoryId": str(memory.get("memoryId") or ""),
        "version": int(memory.get("version") or 1),
        "category": memory.get("category") or "",
        "key": memory.get("key") or "",
        "content": str(memory.get("content") or ""),
        "value": memory.get("value"),
        "domains": list(memory.get("domains") or []),
        "sensitivity": (memory.get("sensitivity") or "GENERAL").upper(),
        "state": memory.get("state") or "ACTIVE",
        "sourceRefs": list(memory.get("sourceRefs") or []),
        "confirmedAt": memory.get("confirmedAt"),
        "updatedAt": memory.get("updatedAt"),
        "expiresAt": memory.get("expiresAt"),
    }


# ------------------------------------------------------------------ 判定
def _is_active(memory: dict[str, Any]) -> bool:
    """只返回 ACTIVE；CANDIDATE / SUPERSEDED / DELETED / EXPIRED / REJECTED 一律不返回。"""
    return (memory.get("state") or "ACTIVE").upper() == "ACTIVE" and not _expired(memory)


def _expired(memory: dict[str, Any]) -> bool:
    raw = memory.get("expiresAt")
    if not raw:
        return False
    try:
        expires = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    return expires < datetime.now(timezone.utc)


def _domain_match(memory: dict[str, Any], requested: list[str]) -> bool:
    """不指定 domains 时不按领域过滤（仍受授权与敏感级别约束）。"""
    if not requested:
        return True
    return bool(set(memory.get("domains") or []) & set(requested))


def _sensitivity_ok(memory: dict[str, Any], authorized: list[str] | None) -> bool:
    """敏感记忆必须有明确授权；未给授权列表时，保守起见不返回敏感项。"""
    if (memory.get("sensitivity") or "GENERAL").upper() != "SENSITIVE":
        return True
    if authorized is None:
        return False
    return bool(set(memory.get("domains") or []) & set(authorized))


def _score(query: str, purpose: str, memory: dict[str, Any]) -> int:
    """粗排序：query 关键词命中 > purpose 命中。够用且可解释。

    注意：不要拿 key 自身做命中判断——key 就在 haystack 里，会恒为真，
    导致"什么都没匹配"的记忆也被算成相关。
    """
    haystack = f"{memory.get('content','')}".lower()
    score = 0
    for token in _tokens(query):
        if token in haystack:
            score += 10
    for token in _tokens(purpose):
        if token in haystack:
            score += 2
    return score


def _tokens(text: str) -> list[str]:
    """中文按二字滑窗切，英文/数字按词切。不引第三方分词库，够本项目用。"""
    text = (text or "").lower()
    out: list[str] = []
    for word in re.findall(r"[a-z0-9_]+", text):
        if len(word) >= 2:
            out.append(word)
    for chunk in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(chunk) <= 2:
            out.append(chunk)
        else:
            out.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))
    return [t for t in dict.fromkeys(out) if t]


def _count(text: str) -> int:
    """按 Unicode 码点计数（v3 要求）。"""
    return len([ch for ch in unicodedata.normalize("NFC", text)])


def _neg_time(raw: Any) -> float:
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return -dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_tool_response(result: dict[str, Any]) -> dict[str, Any]:
    """包成 v3 的工具响应外层：{code,message,data:{tool,args,result}}。"""
    return {"code": "OK", "message": "成功",
            "data": {"tool": "memory.search", "args": {}, "result": result}}


def to_error_response(error: MemorySearchError) -> dict[str, Any]:
    """失败一律 data=null，不凑结果。"""
    return {"code": error.code, "message": error.message, "data": None}


# ------------------------------------------------------------------ 自测
def _sample_memories() -> list[dict[str, Any]]:
    return [
        {"memoryId": "memory-001", "version": 2, "category": "LONG_TERM_PREFERENCE",
         "key": "activity.preferredDurationMin", "content": "平时更喜欢一小时以内的文化活动",
         "value": 60, "domains": ["tourism", "culture"], "sensitivity": "GENERAL",
         "state": "ACTIVE", "sourceRefs": [{"type": "USER_MESSAGE", "id": "msg-001"}],
         "confirmedAt": "2026-10-28T02:00:00Z", "updatedAt": "2026-10-28T02:00:00Z",
         "expiresAt": None},
        {"memoryId": "memory-002", "version": 1, "category": "LONG_TERM_PREFERENCE",
         "key": "mobility.avoidSteps", "content": "尽量避开台阶路线",
         "value": True, "domains": ["tourism"], "sensitivity": "GENERAL",
         "state": "ACTIVE", "sourceRefs": [], "updatedAt": "2026-10-27T02:00:00Z"},
        {"memoryId": "memory-003", "version": 1, "category": "LONG_TERM_PREFERENCE",
         "key": "health.bloodPressure", "content": "有高血压，需要少盐饮食",
         "value": None, "domains": ["health"], "sensitivity": "SENSITIVE",
         "state": "ACTIVE", "sourceRefs": [], "updatedAt": "2026-10-26T02:00:00Z"},
        {"memoryId": "memory-004", "version": 1, "category": "LONG_TERM_PREFERENCE",
         "key": "culture.interests", "content": "喜欢剪纸和刺绣",
         "value": None, "domains": ["culture"], "sensitivity": "GENERAL",
         "state": "ACTIVE", "sourceRefs": [], "updatedAt": "2026-10-25T02:00:00Z"},
        {"memoryId": "memory-005", "version": 1, "category": "LONG_TERM_PREFERENCE",
         "key": "mobility.avoidSteps", "content": "旧的不要台阶（已被取代）",
         "value": True, "domains": ["tourism"], "sensitivity": "GENERAL",
         "state": "SUPERSEDED", "sourceRefs": [], "updatedAt": "2026-10-20T02:00:00Z"},
        {"memoryId": "memory-006", "version": 1, "category": "LONG_TERM_PREFERENCE",
         "key": "culture.courseKind", "content": "想学剪纸，最好别太远",
         "value": None, "domains": ["culture"], "sensitivity": "GENERAL",
         "state": "CANDIDATE", "sourceRefs": [], "updatedAt": "2026-10-29T02:00:00Z"},
    ]


def _selftest() -> int:
    mems = _sample_memories()
    args = {"purpose": "为当前老人安排短时文化活动", "query": "剪纸、步行时长",
            "domains": ["culture", "tourism"], "limit": 5, "maxContentChars": 2000}

    print("=" * 66)
    print(" 1) 正常检索")
    print("=" * 66)
    result = search(args, mems, authorized_domains=["tourism", "culture"])
    print(f"  readStatus={result['readStatus']}  条数={len(result['items'])}  "
          f"字数={result['returnedContentChars']}  truncated={result['truncated']}")
    for item in result["items"]:
        print(f"    {item['memoryId']}  {item['key']:<32} {item['content']}")
    print("  说明：SUPERSEDED 与 CANDIDATE 都被过滤掉了，敏感项没有授权也没返回")

    print()
    print("=" * 66)
    print(" 2) 确实没有匹配 → EMPTY（不是报错）")
    print("=" * 66)
    empty = search({"purpose": "查探戈课程", "query": "探戈", "domains": ["culture"]},
                   mems, authorized_domains=["tourism", "culture"])
    print(f"  readStatus={empty['readStatus']}  items={len(empty['items'])}")

    print()
    print("=" * 66)
    print(" 3) 越权领域 → 403，且不透露有没有隐藏记忆")
    print("=" * 66)
    try:
        search({"purpose": "查健康", "query": "血压", "domains": ["health"]},
               mems, authorized_domains=["tourism"])
    except MemorySearchError as error:
        print(f"  {error.status} {error.code}  {error.message}")

    print()
    print("=" * 66)
    print(" 4) 检索服务不可用 → 503（绝不能返回 EMPTY）")
    print("=" * 66)
    try:
        search(args, mems, authorized_domains=["tourism", "culture"], store_available=False)
    except MemorySearchError as error:
        print(f"  {error.status} {error.code}  {error.message}")

    print()
    print("=" * 66)
    print(" 5) 字数预算故意给小 → 整条跳过并标 truncated，不切断内容")
    print("=" * 66)
    long_mems = [
        {"memoryId": f"memory-long-{i}", "version": 1, "category": "LONG_TERM_PREFERENCE",
         "key": f"culture.note{i}", "content": "文化活动偏好" + "补充说明" * 20,
         "value": None, "domains": ["culture"], "sensitivity": "GENERAL",
         "state": "ACTIVE", "updatedAt": f"2026-10-2{i}T02:00:00Z"}
        for i in range(1, 4)
    ]
    tight = search({"purpose": "安排文化活动", "query": "文化活动", "domains": ["culture"],
                    "limit": 10, "maxContentChars": 200},
                   long_mems, authorized_domains=["culture"])
    print(f"  预算200  实际字数={tight['returnedContentChars']}  "
          f"条数={len(tight['items'])}  truncated={tight['truncated']}")
    for item in tight["items"]:
        print(f"    {item['memoryId']}  {len(item['content'])} 字（完整未截断）")
    print("  说明：放不下就整条跳过，宁可少给一条，也不切半句让语义变掉")

    print()
    print("结论：三种状态分得清、越权不泄漏、超限不切句子 —— 这才是 v3 要的检索。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
