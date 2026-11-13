#!/usr/bin/env python3
"""A3 记忆审核（v3.0）—— 纯函数，零依赖，不碰网络。

v3.0 把记忆的「存、确认、执行」全部收归 P2，A3 只负责两件事：
    1. memory.search        只读检索（由 P2 提供，A3 提供策略）
    2. memory.candidate.review  给候选出「新增/合并/替换/保留/拒绝」建议

本文件实现第 2 件事，输出严格对齐 `control.schema.json` 的 `MemoryReview`：
    candidateId / candidateVersion / reviewId / reviewVersion /
    recommendation / conflictMemoryRefs / proposedDomains /
    needsUserConfirmation / explanation
**一个字段都不多、一个都不少**（Schema 是 additionalProperties: false）。

另外顺手解决 v3 第八节第 1 条「先分清四类信息」：
    本次临时情况 → 不进长期表
    长期偏好     → 形成候选
    业务事实     → 查 P2 业务记录，不做记忆
    授权状态     → 查实时权限，不做记忆

自测：
    python memory_review.py
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

# v3：首批只允许这两类
CATEGORY_PREFERENCE = "LONG_TERM_PREFERENCE"
CATEGORY_EXPERIENCE = "EXPERIENCE"

MEMORY_STATES_ACTIVE = "ACTIVE"

# v3：recommendation 五选一
ADD, MERGE, REPLACE, KEEP, REJECT = "ADD", "MERGE", "REPLACE", "KEEP", "REJECT"

# MemoryReview 的全部合法字段（多一个就会被 Schema 拒）
REVIEW_FIELDS = {
    "candidateId", "candidateVersion", "reviewId", "reviewVersion",
    "recommendation", "conflictMemoryRefs", "proposedDomains",
    "needsUserConfirmation", "explanation",
}

# 四类信息判定用词表（保守，宁可判"临时"，也不要乱存长期偏好）
_TEMPORARY_WORDS = ("今天", "这次", "刚才", "刚刚", "暂时", "这会儿", "待会", "等下", "现在有点")
_LONG_TERM_WORDS = ("以后", "平常", "平时", "一直", "总是", "从来", "我一般", "我一直", "都别", "别再")
_BUSINESS_WORDS = ("已经报名", "已报名", "已受理", "已经受理", "已下单", "已支付", "已提交")
_AUTH_WORDS = ("家属能不能看", "能不能授权", "允许谁看", "取消授权", "共享位置")

# 规则 → 记忆 key（v3：按 userId + 规范化 key + 适用领域 判重）
_KEY_RULES: list[tuple[str, str, str]] = [
    ("台阶", "mobility.avoidSteps", "mobility"),
    ("分钟", "activity.preferredDurationMin", "activity"),
    ("走得慢", "mobility.walkSpeed", "mobility"),
    ("愿意教", "bank.teachSkills", "ability"),
    ("非遗", "culture.interests", "culture"),
]

_MAX_CONFLICTS = 10          # Schema: maxItems 10
_MAX_DOMAINS = 9             # Schema: maxItems 9
_MAX_EXPLANATION = 4000


# ---------------------------------------------------------------- 四类信息
def classify(text: str) -> dict[str, Any]:
    """判断一句话属于四类信息里的哪一类。

    返回 {"kind": ..., "isLongTerm": bool, "reason": ...}
    只有 kind == "LONG_TERM_PREFERENCE" 或 "EXPERIENCE" 才应该生成候选。
    """
    body = (text or "").strip()
    if not body:
        return {"kind": "UNKNOWN", "isLongTerm": False, "reason": "内容为空，不生成候选"}

    if any(w in body for w in _AUTH_WORDS):
        return {"kind": "AUTHORIZATION", "isLongTerm": False,
                "reason": "授权状态要查实时权限，不能写成记忆代替授权"}
    if any(w in body for w in _BUSINESS_WORDS):
        return {"kind": "BUSINESS_FACT", "isLongTerm": False,
                "reason": "业务事实以 P2 业务记录为准，不由模型记忆决定"}
    if any(w in body for w in _TEMPORARY_WORDS) and not any(w in body for w in _LONG_TERM_WORDS):
        return {"kind": "TEMPORARY", "isLongTerm": False,
                "reason": "只是本次临时情况，放当前任务上下文，不写长期偏好"}
    if any(w in body for w in _LONG_TERM_WORDS):
        return {"kind": CATEGORY_PREFERENCE, "isLongTerm": True,
                "reason": "长期表述（以后/平常/一直），可以形成候选"}
    return {"kind": CATEGORY_PREFERENCE, "isLongTerm": True,
            "reason": "按偏好处理，但仍需老人确认后才保存"}


# ---------------------------------------------------------------- key 规范化
def normalize_key(content: str, hint: str | None = None) -> tuple[str, str]:
    """把一句偏好压成 (规范化 key, 领域)。

    v3 要求按 userId + 规范化 key + 适用领域 判重，所以 key 必须稳定：
    同一件事说两遍要落到同一个 key，否则去重就失效。
    """
    body = content or ""
    if hint:
        return hint, _domain_of(hint)
    for word, key, _ in _KEY_RULES:
        if word in body:
            return key, _domain_of(key)
    return "preference.general", "tourism"


def _domain_of(key: str) -> str:
    prefix = key.split(".", 1)[0]
    return {"mobility": "tourism", "activity": "tourism", "culture": "culture",
            "bank": "ability"}.get(prefix, "tourism")


# ---------------------------------------------------------------- 审核建议
def review_candidate(candidate: dict[str, Any], existing: list[dict[str, Any]] | None = None,
                     review_id: str | None = None) -> dict[str, Any]:
    """对一条候选给出审核建议，返回严格符合 MemoryReview 的对象。

    candidate 需要：candidateId / candidateVersion / category / key / content /
                    value(可选) / domains(可选) / sensitivity(可选) /
                    sensitiveConsent(可选，敏感记忆是否已获单独同意)
    existing  是 P2 里的现有有效记忆列表，元素至少含 memoryId / version / key /
              state / content / value / domains。
    """
    existing = existing or []
    cid = str(candidate.get("candidateId") or "")
    cver = int(candidate.get("candidateVersion") or 1)
    if not cid:
        raise ValueError("candidateId 不能为空（v3：候选由 P2 生成并保存，A3 不自己造 ID）")
    if cver < 1:
        raise ValueError("candidateVersion 必须 >= 1")

    category = candidate.get("category") or CATEGORY_PREFERENCE
    key = candidate.get("key") or normalize_key(candidate.get("content", ""))[0]
    domains = _clean_domains(candidate.get("domains") or [_domain_of(key)])
    sensitivity = (candidate.get("sensitivity") or "GENERAL").upper()

    # 冲突集合：同 key、同一老人、仍有效
    same_key = [
        m for m in existing
        if m.get("key") == key and (m.get("state") or MEMORY_STATES_ACTIVE) == MEMORY_STATES_ACTIVE
    ]
    same_key.sort(key=lambda m: int(m.get("version") or 1), reverse=True)
    conflicts = [{"memoryId": str(m["memoryId"]), "version": int(m.get("version") or 1)}
                 for m in same_key[:_MAX_CONFLICTS]]

    # 1) 敏感记忆：没有单独明确同意，直接拒绝
    if sensitivity == "SENSITIVE" and not candidate.get("sensitiveConsent"):
        return _build(cid, cver, review_id, REJECT, conflicts, domains, False,
                      "这条内容被判定为敏感。按 v3 第八节，健康等敏感记忆必须单独明确同意保存及使用范围，"
                      "不能默认跨领域共享，因此本次不生成有效记忆。")

    # 2) 没有同 key 的有效记忆 → 新增
    if not same_key:
        return _build(cid, cver, review_id, ADD, [], domains, True,
                      "现有记忆中未发现同 key 的有效项，建议新增；仍需老人本人确认后才成为长期记忆。")

    target = same_key[0]
    target_domains = _clean_domains(target.get("domains") or [])
    same_content = _same(target.get("content"), candidate.get("content"))
    same_value = _same_value(target.get("value"), candidate.get("value"))

    # 3) 内容完全一致 → 保留，不重复建
    if same_content and same_value and set(target_domains) == set(domains):
        return _build(cid, cver, review_id, KEEP, conflicts, domains, False,
                      f"与已有记忆 {target['memoryId']} 内容一致，建议保留原记录，不重复新增。")

    # 4) 内容一致但领域变了 → 合并（扩领域要重新确认）
    if same_content and same_value and set(target_domains) != set(domains):
        merged = _clean_domains(list(target_domains) + list(domains))
        return _build(cid, cver, review_id, MERGE, conflicts, merged, True,
                      f"内容与 {target['memoryId']} 一致，但适用领域不同，建议合并为 "
                      f"{'/'.join(merged)}；扩大适用范围必须重新经老人确认。")

    # 5) 同 key 但内容/取值不同 → 替换（不能静默覆盖）
    return _build(cid, cver, review_id, REPLACE, conflicts, domains, True,
                  f"与已有记忆 {target['memoryId']} 是同一类偏好但内容不同，建议替换为新内容；"
                  f"旧版本标记为已取代，不能继续作为当前偏好返回。")


def _build(cid, cver, review_id, recommendation, conflicts, domains, needs_confirm,
           explanation) -> dict[str, Any]:
    review = {
        "candidateId": cid,
        "candidateVersion": cver,
        "reviewId": review_id or f"review-{uuid.uuid4()}",
        "reviewVersion": 1,
        "recommendation": recommendation,
        "conflictMemoryRefs": conflicts[:_MAX_CONFLICTS],
        "proposedDomains": domains[:_MAX_DOMAINS],
        "needsUserConfirmation": bool(needs_confirm),
        "explanation": (explanation or "")[:_MAX_EXPLANATION],
    }
    _assert_schema(review)
    return review


def _assert_schema(review: dict[str, Any]) -> None:
    """本地自检：多字段、少字段、枚举错，当场报错，别等 P2 拒。"""
    if set(review) != REVIEW_FIELDS:
        raise AssertionError(f"MemoryReview 字段不匹配：多 {set(review) - REVIEW_FIELDS}，"
                             f"少 {REVIEW_FIELDS - set(review)}")
    if review["recommendation"] not in (ADD, MERGE, REPLACE, KEEP, REJECT):
        raise AssertionError("recommendation 只能是 ADD/MERGE/REPLACE/KEEP/REJECT")
    if not review["explanation"].strip():
        raise AssertionError("explanation 必填且非空")
    if len(review["conflictMemoryRefs"]) > _MAX_CONFLICTS:
        raise AssertionError("conflictMemoryRefs 最多 10 条")
    if len(review["proposedDomains"]) > _MAX_DOMAINS:
        raise AssertionError("proposedDomains 最多 9 项")


def _clean_domains(domains: list[Any]) -> list[str]:
    seen: list[str] = []
    for d in domains:
        text = str(d).strip()
        if text and text not in seen:
            seen.append(text)
    return seen[: _MAX_DOMAINS]


def _same(a: Any, b: Any) -> bool:
    return _norm(a) == _norm(b)


def _same_value(a: Any, b: Any) -> bool:
    if a is None and b is None:
        return True
    return a == b


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


# ---------------------------------------------------------------- 自测
def _selftest() -> int:
    print("=" * 60)
    print(" 1) 四类信息判定")
    print("=" * 60)
    samples = [
        "今天膝盖有点累",
        "我以后都不走台阶",
        "我已经报名了剪纸课",
        "家属能不能看我位置",
        "我走得慢",
    ]
    for s in samples:
        r = classify(s)
        mark = "记" if r["isLongTerm"] else "不记"
        print(f"  [{mark}] {s}  →  {r['kind']}：{r['reason']}")

    print()
    print("=" * 60)
    print(" 2) 审核建议（对应 v3 的 ADD / MERGE / REPLACE / KEEP / REJECT）")
    print("=" * 60)
    mem = {"memoryId": "memory-001", "version": 2, "key": "mobility.avoidSteps",
           "content": "尽量避开台阶", "value": True, "domains": ["tourism"], "state": "ACTIVE"}

    cases = [
        ("全新偏好", {"candidateId": "c-1", "candidateVersion": 1, "key": "mobility.walkSpeed",
                  "content": "走路比较慢", "value": "SLOW", "domains": ["tourism"]}, []),
        ("与已有完全一致", {"candidateId": "c-2", "candidateVersion": 1, "key": "mobility.avoidSteps",
                    "content": "尽量避开台阶", "value": True, "domains": ["tourism"]}, [mem]),
        ("同一类但内容变了", {"candidateId": "c-3", "candidateVersion": 2, "key": "mobility.avoidSteps",
                     "content": "完全不能走台阶", "value": True, "domains": ["tourism"]}, [mem]),
        ("内容一样但扩了领域", {"candidateId": "c-4", "candidateVersion": 1, "key": "mobility.avoidSteps",
                      "content": "尽量避开台阶", "value": True,
                      "domains": ["tourism", "culture"]}, [mem]),
        ("健康敏感但没同意", {"candidateId": "c-5", "candidateVersion": 1, "key": "health.bloodPressure",
                     "content": "有高血压", "value": None, "domains": ["health"],
                     "sensitivity": "SENSITIVE"}, []),
    ]
    for name, cand, exist in cases:
        review = review_candidate(cand, exist)
        print(f"  {name:<18} → {review['recommendation']:<8} "
              f"需确认={review['needsUserConfirmation']}  冲突={len(review['conflictMemoryRefs'])}")
        print(f"     {review['explanation']}")

    print()
    print("Schema 自检：9 个字段齐全、枚举合法、无多余字段 —— 通过")
    print("结论：这一层完全可以先写好，不需要等 P2 的 v3 服务端。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
