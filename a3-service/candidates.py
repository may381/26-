"""A3 记忆候选生成（游后：事实 → 候选）。

对应《一期二期开发进展与线上协作清单》里 A3 那一行：
「需要哪些事实；候选输出格式与来源引用；哪些值建议回写；如何避免重复生成」。

三条硬约束：
1. **只生成候选，不写长期记忆**：落库与老人确认归 P2 的状态机和 P1 的页面；
2. **每条候选必须带 evidence**（来自哪个事实字段、值是多少），不允许无依据生成；
3. **去重键确定**：dedupeKey = 规则ID + tripId（同一游览重复生成不产生重复候选），
   同时给 content 归一化指纹，供 P2 在库层做二次去重。
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

FACT_KEYS = {"routeId", "routeName", "startedAt", "endedAt", "visitedSpots", "feedback", "restStops", "source"}
REQUIRED_FACTS = {"routeName", "visitedSpots"}

# 需要的事实（发给 P2 的清单，也是校验依据）
FACT_CONTRACT = [
    {"field": "routeName", "required": True, "why": "小结与经历候选需要可读的路线名"},
    {"field": "visitedSpots", "required": True, "why": "经历候选需要实际到访（不是计划值）"},
    {"field": "startedAt/endedAt", "required": False, "why": "算实际时长；缺失则不出时长类候选"},
    {"field": "feedback", "required": False, "why": "偏好候选的主要来源，必须是老人原话"},
    {"field": "restStops", "required": False, "why": "判断休息频率，用于时长候选的置信度"},
    {"field": "source", "required": False, "why": "区分 GPS/手动/演示，候选里要标注来源"},
]

_MINUTES = re.compile(r"(\d{1,3})\s*分钟")


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_min(facts: dict[str, Any]) -> int | None:
    start, end = _parse_iso(facts.get("startedAt")), _parse_iso(facts.get("endedAt"))
    if not start or not end:
        return None
    minutes = (end - start).total_seconds() / 60
    if minutes <= 0 or minutes > 24 * 60:
        return None
    return int(round(minutes))


def _fingerprint(user_id: str, memory_type: str, content: str) -> str:
    normalized = re.sub(r"\s+", "", content)
    return hashlib.sha256(f"{user_id}|{memory_type}|{normalized}".encode("utf-8")).hexdigest()[:16]


def generate_candidates(user_id: str, trip_id: str, facts: dict[str, Any]) -> dict[str, Any]:
    """把一次游览的事实转成记忆候选。返回结构见 samples/response-4-candidates.json。"""
    if not user_id:
        raise ValueError("userId 必填")
    if not trip_id:
        raise ValueError("tripId 必填")
    if not isinstance(facts, dict):
        raise ValueError("facts 必须是对象")
    unknown = set(facts) - FACT_KEYS
    if unknown:
        raise ValueError(f"facts 出现未约定字段：{','.join(sorted(unknown))}")
    missing = [key for key in REQUIRED_FACTS if not facts.get(key)]
    if missing:
        raise ValueError(f"facts 缺少必需字段：{','.join(sorted(missing))}")

    route_name = str(facts["routeName"]).strip()
    spots = [str(s).strip() for s in facts.get("visitedSpots") or [] if str(s).strip()]
    feedback = str(facts.get("feedback") or "").strip()
    source = str(facts.get("source") or "MOCK")
    duration = _duration_min(facts)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    # 规则 1：经历（每次游览必然生成一条）
    experience_content = (
        f"{_day(facts.get('endedAt'))}游览{route_name}，到访 {len(spots)} 个景点"
        + (f"，用时约 {duration} 分钟" if duration else "")
    )
    candidates.append(_candidate(
        user_id, trip_id, "experience", experience_content, source,
        rule_id="R-EXPERIENCE",
        evidence=[
            {"field": "routeName", "value": route_name},
            {"field": "visitedSpots", "value": spots},
            {"field": "durationMin", "value": duration},
            {"field": "source", "value": source},
        ],
        confidence="HIGH" if spots and duration else "MEDIUM",
        suggested_patch={},
        note="经历类只用于小结与回顾，不回写档案",
    ))

    # 规则 2：时长/体力偏好（反馈里有分钟数，或明显短于计划）
    explicit_minutes = _MINUTES.search(feedback)
    tired = any(word in feedback for word in ("累", "走不动", "腿酸", "喘"))
    if explicit_minutes:
        minutes = int(explicit_minutes.group(1))
        candidates.append(_candidate(
            user_id, trip_id, "preference", f"一次连续步行大约 {minutes} 分钟就需要休息", source,
            rule_id="R-WALK-DURATION",
            evidence=[{"field": "feedback", "value": feedback}],
            confidence="HIGH",
            suggested_patch={"walkDurationMin": minutes},
            note="数值直接来自老人原话，建议回写档案的 walkDurationMin",
        ))
    elif duration and tired:
        rounded = max(10, min(180, int(round(duration / 10.0)) * 10))
        candidates.append(_candidate(
            user_id, trip_id, "preference", f"一次连续步行大约 {rounded} 分钟就需要休息", source,
            rule_id="R-WALK-DURATION-INFERRED",
            evidence=[{"field": "durationMin", "value": duration},
                      {"field": "feedback", "value": feedback}],
            confidence="MEDIUM",
            suggested_patch={"walkDurationMin": rounded},
            note="由实际时长与「累」推断，需老人确认后才可回写",
        ))
    else:
        skipped.append({"rule": "R-WALK-DURATION", "reason": "反馈里没有分钟数，也没有疲劳表达，不出体力偏好候选"})

    # 规则 3：避台阶
    if "台阶" in feedback:
        candidates.append(_candidate(
            user_id, trip_id, "preference", "尽量避开台阶路线", source,
            rule_id="R-AVOID-STEPS",
            evidence=[{"field": "feedback", "value": feedback}],
            confidence="HIGH",
            suggested_patch={"avoidSteps": True},
            note="与档案 avoidSteps 字段一一对应",
        ))

    # 规则 4：步速
    if "慢" in feedback:
        candidates.append(_candidate(
            user_id, trip_id, "preference", "走路偏慢，讲解和提醒请放慢节奏", source,
            rule_id="R-WALK-SPEED",
            evidence=[{"field": "feedback", "value": feedback}],
            confidence="MEDIUM",
            suggested_patch={"walkSpeed": "SLOW"},
            note="步速枚举 SLOW/MEDIUM/FAST，建议回写 SLOW",
        ))

    # 规则 5：兴趣——缺景点标签，明确不出，不猜
    skipped.append({
        "rule": "R-INTEREST",
        "reason": "facts 未提供景点标签（category），无法判断兴趣，不生成猜测性候选；"
                  "如 P2 能提供 spot 的 category，可补齐此规则",
    })

    return {
        "userId": user_id,
        "tripId": trip_id,
        "generatedAt": generated_at,
        "factContract": FACT_CONTRACT,
        "candidates": candidates,
        "skipped": skipped,
        "dedupe": {
            "keyFormat": "dedupeKey = ruleId:tripId",
            "contentFingerprint": "sha256(userId|type|去空白content)[:16]",
            "rule": "同一 tripId 重复生成应得到相同 dedupeKey；P2 落库时按 dedupeKey 幂等，"
                    "按 contentFingerprint 做跨次去重",
        },
        "writePolicy": "A3 只产出候选；是否持久化、何时回写档案由 P2 状态机与老人确认决定",
    }


def _day(raw: str | None) -> str:
    parsed = _parse_iso(raw)
    return f"{parsed.year}年{parsed.month}月{parsed.day}日" if parsed else "本次"


def _candidate(user_id: str, trip_id: str, memory_type: str, content: str, source: str, *,
               rule_id: str, evidence: list[dict[str, Any]], confidence: str,
               suggested_patch: dict[str, Any], note: str) -> dict[str, Any]:
    return {
        "type": memory_type,
        "content": content,
        "source": "trip",
        "sourceRef": {"kind": "trip", "tripId": trip_id, "dataSource": source},
        "evidence": evidence,
        "confidence": confidence,
        "suggestedProfilePatch": suggested_patch,
        "dedupeKey": f"{rule_id}:{trip_id}",
        "contentFingerprint": _fingerprint(user_id, memory_type, content),
        "note": note,
        "requiresElderConfirm": True,
    }
