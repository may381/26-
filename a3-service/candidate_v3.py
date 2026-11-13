#!/usr/bin/env python3
"""候选 v3 化：把 v2 的候选转成 v3 的记忆对象形状，再接审核。

为什么要这一层：
    v2 的候选是「ruleId:tripId + content + evidence」；
    v3 的记忆对象要求 `category / key / value / domains / sensitivity / state / version / expiresAt`，
    去重按 `userId + 规范化 key + domains`，候选 7 天未确认即过期。
    老规则（时长/台阶/步速/经历）本身还能用，缺的是这层"翻译"。

三条 v3 硬约束（不要越界）：
    1. category 首批只有 LONG_TERM_PREFERENCE / EXPERIENCE，其他类型不硬塞；
    2. domains 必须是登记领域（九种），不能自造 "mobility" 这种；
    3. state 一律 CANDIDATE —— 候选不参与正常长期检索，也不代表已保存。

自测：
    python candidate_v3.py
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from candidates import generate_candidates
from memory_review import CATEGORY_EXPERIENCE, CATEGORY_PREFERENCE, review_candidate

# v3：登记领域（与九种 intent 同一套，不要自造）
DOMAINS = {"tourism", "help", "health", "fraud", "care", "culture",
           "community", "volunteer", "ability"}

STATE_CANDIDATE = "CANDIDATE"
CANDIDATE_TTL_DAYS = 7          # v3：候选 7 天未确认即过期

# suggestedProfilePatch 的键 → v3 的规范化 memory key
_PATCH_TO_KEY: dict[str, tuple[str, str]] = {
    "walkDurationMin": ("activity.preferredDurationMin", "tourism"),
    "avoidSteps": ("mobility.avoidSteps", "tourism"),
    "walkSpeed": ("mobility.walkSpeed", "tourism"),
}
_TYPE_TO_CATEGORY = {
    "experience": CATEGORY_EXPERIENCE,
    "preference": CATEGORY_PREFERENCE,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _stable_candidate_id(user_id: str, trip_id: str, dedupe_key: str) -> str:
    """本地演示用的稳定候选 ID。

    注意：v3 里 candidateId 由 P2 生成并保存，A3 不能自己造。这里只在没有 P2 的场景
    用「用户+行程+规则」算一个稳定值，保证同一行程重试不产生两条候选。
    """
    raw = f"{user_id}|{trip_id}|{dedupe_key}".encode("utf-8")
    return "cand-local-" + hashlib.sha1(raw).hexdigest()[:12]


def _sensitivity_of(key: str) -> str:
    return "SENSITIVE" if key.startswith("health.") else "GENERAL"


def _to_v3(legacy: dict[str, Any], user_id: str, trip_id: str,
           created_at: datetime) -> dict[str, Any] | None:
    """一条 v2 候选 → 一条 v3 候选。转不了的返回 None（由调用方记进 skipped）。"""
    legacy_type = legacy.get("type")
    category = _TYPE_TO_CATEGORY.get(legacy_type)
    if category is None:
        return None

    patch = legacy.get("suggestedProfilePatch") or {}
    if category == CATEGORY_EXPERIENCE:
        key, value, domain = "experience.tripSummary", None, "tourism"
    else:
        if not patch:
            return None
        patch_key = next(iter(patch))
        if patch_key not in _PATCH_TO_KEY:
            return None
        key, domain = _PATCH_TO_KEY[patch_key]
        value = patch[patch_key]

    source_ref = legacy.get("sourceRef") or {}
    return {
        "candidateId": _stable_candidate_id(user_id, trip_id, legacy.get("dedupeKey", "")),
        "candidateVersion": 1,
        "userId": user_id,
        "category": category,
        "key": key,
        "content": legacy.get("content", ""),
        "value": value,
        "domains": [domain] if domain in DOMAINS else ["tourism"],
        "sensitivity": _sensitivity_of(key),
        "state": STATE_CANDIDATE,
        "sourceRefs": [{"type": "TRIP", "id": trip_id,
                        "dataSource": source_ref.get("dataSource") or "MOCK"}],
        "evidence": legacy.get("evidence") or [],           # 溯源：v3 没禁，保留有用
        "confidence": legacy.get("confidence", "MEDIUM"),
        "createdAt": _iso(created_at),
        "expiresAt": _iso(created_at + timedelta(days=CANDIDATE_TTL_DAYS)),
        "legacyDedupeKey": legacy.get("dedupeKey"),
    }


def build_v3_candidates(user_id: str, trip_id: str, facts: dict[str, Any],
                        created_at: datetime | None = None) -> dict[str, Any]:
    """游后事实 → v3 形状的候选列表。老的生成规则完全复用。"""
    legacy = generate_candidates(user_id, trip_id, facts)
    created = created_at or _now()

    converted: list[dict[str, Any]] = []
    unsupported: list[dict[str, str]] = []
    for item in legacy["candidates"]:
        v3 = _to_v3(item, user_id, trip_id, created)
        if v3 is None:
            unsupported.append({
                "legacyType": item.get("type", ""),
                "legacyDedupeKey": item.get("dedupeKey", ""),
                "reason": "v3 首批 category 只允许 LONG_TERM_PREFERENCE / EXPERIENCE，"
                          "这条没有可映射的规范化 key，不硬塞",
            })
            continue
        converted.append(v3)

    return {
        "userId": user_id,
        "tripId": trip_id,
        "generatedAt": _iso(created),
        "candidateTtlDays": CANDIDATE_TTL_DAYS,
        "candidates": converted,
        "skipped": legacy["skipped"],
        "unsupported": unsupported,
        "dedupe": {
            "v3KeyRule": "userId + 规范化 key + domains",
            "legacyNote": "v2 的 dedupeKey(ruleId:tripId) 保留在 legacyDedupeKey 里，仅作追溯",
        },
        "writePolicy": "候选由 P2 保存；A3 只出候选和审核建议，不能写库、不能准备确认",
    }


def review_all(candidates: list[dict[str, Any]],
               existing: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """对一批候选逐条出审核建议，返回 MEMORY_REVIEW 列表（已过 Schema 自检）。"""
    return [review_candidate(c, existing or []) for c in candidates]


# ------------------------------------------------------------------ 自测
_FACTS = {
    "routeId": "r-001", "routeName": "省力线",
    "startedAt": "2026-10-29T01:00:00Z", "endedAt": "2026-10-29T01:40:00Z",
    "visitedSpots": ["迎客松", "清风湖"],
    "feedback": "走40分钟就累，最好少走台阶",
    "restStops": 2, "source": "GPS",
}


def _selftest() -> int:
    print("=" * 66)
    print(" 一次游后事实 → v3 候选")
    print("=" * 66)
    built = build_v3_candidates("u100", "t-demo-001", _FACTS)
    for c in built["candidates"]:
        print(f"  {c['category']:<22} {c['key']:<32} value={c['value']!r:<8} "
              f"domains={c['domains']} {c['sensitivity']}")
        print(f"     id={c['candidateId']}  expires={c['expiresAt']}  state={c['state']}")
    if built["unsupported"]:
        print("  未转换：", built["unsupported"])

    print()
    print("=" * 66)
    print(" 同一条候选再生成一次（验证候选 ID 稳定，重试不产生两条）")
    print("=" * 66)
    again = build_v3_candidates("u100", "t-demo-001", _FACTS,
                                created_at=datetime(2026, 10, 29, tzinfo=timezone.utc))
    same = [a["candidateId"] == b["candidateId"]
            for a, b in zip(built["candidates"], again["candidates"])]
    print(f"  候选 ID 是否稳定：{all(same)}")

    print()
    print("=" * 66)
    print(" 接审核：假设 P2 里已有一条 '避开台阶'")
    print("=" * 66)
    existing = [{
        "memoryId": "memory-001", "version": 2, "key": "mobility.avoidSteps",
        "content": "尽量避开台阶路线", "value": True,
        "domains": ["tourism"], "state": "ACTIVE",
    }]
    for review in review_all(built["candidates"], existing):
        print(f"  {review['recommendation']:<8} 需确认={str(review['needsUserConfirmation']):<5} "
              f"候选={review['candidateId']}")
        print(f"     {review['explanation'][:70]}")

    print()
    print("结论：事实 → v3 候选 → 审核建议，全链路本地可跑，不依赖 P2 接口。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
