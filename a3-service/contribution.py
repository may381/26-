#!/usr/bin/env python3
"""A3 贡献整理 —— 把已确认的服务和时长，解释成老人和家属看得懂的话。

分工文档第 9 节：「解释确认后的服务和时长记录」，
返回「不由模型自行审核通过、增加时长或创造贡献」。

⚠️ 这个模块的职责边界窄得反常，但必须守住：
    A3 **只解释**，不产生、不增加、不修改任何一条贡献记录。
    记录从哪来？P2 的打卡 + 服务确认。
    为什么这么严？因为贡献记录直接关系到老人的荣誉和可能的积分奖励，
    模型随口加一句"您累计服务 20 小时"，就是在造一笔不存在的账。

所以本文件里没有 `add_contribution()` 这种函数，只有 `summarize()`。
未确认（PENDING / REJECTED）的记录一律不计入，并且要说清楚为什么没算。

自测：
    python contribution.py
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

# 记录状态。只有 CONFIRMED 才进统计。
CONFIRMED = "CONFIRMED"
PENDING = "PENDING"
REJECTED = "REJECTED"
STATUSES = (CONFIRMED, PENDING, REJECTED)

MAX_RECORDS = 500
MAX_MINUTES_PER_RECORD = 24 * 60      # 单条不可能超过一天，超了就是脏数据


class ContributionError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def summarize(records: list[dict[str, Any]] | None, *,
              now: datetime | None = None) -> dict[str, Any]:
    """汇总贡献记录。只算已确认的，未确认的单独说明。"""
    rows = records or []
    if len(rows) > MAX_RECORDS:
        raise ContributionError(400, "INVALID_ARGUMENT",
                                f"记录过多（{len(rows)} 条），请分批汇总")

    confirmed: list[dict[str, Any]] = []
    pending_count = rejected_count = 0
    dirty: list[str] = []

    for row in rows:
        status = str(row.get("status") or "").upper()
        if status not in STATUSES:
            dirty.append(str(row.get("recordId") or "?"))
            continue
        if status == PENDING:
            pending_count += 1
            continue
        if status == REJECTED:
            rejected_count += 1
            continue

        minutes = row.get("minutes")
        # 脏数据不进统计：宁可少算，不能多算。
        if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 0:
            dirty.append(str(row.get("recordId") or "?"))
            continue
        if minutes > MAX_MINUTES_PER_RECORD:
            dirty.append(str(row.get("recordId") or "?"))
            continue
        confirmed.append(row)

    total_minutes = sum(int(r["minutes"]) for r in confirmed)
    by_skill: dict[str, dict[str, Any]] = {}
    for row in confirmed:
        name = str(row.get("skillName") or "未标注")
        bucket = by_skill.setdefault(name, {"skillName": name, "times": 0, "minutes": 0})
        bucket["times"] += 1
        bucket["minutes"] += int(row["minutes"])

    skills = sorted(by_skill.values(), key=lambda x: (-x["minutes"], x["skillName"]))
    base = now or datetime.now(timezone.utc)
    has_data = bool(confirmed)

    if not has_data:
        text = ("还没有经过确认的服务记录。等社区确认之后，这里才会有显示。"
                if pending_count else "还没有服务记录。")
    else:
        hours, mins = divmod(total_minutes, 60)
        span = f"{hours} 小时 {mins} 分钟" if hours else f"{mins} 分钟"
        text = f"您一共提供了 {len(confirmed)} 次服务，累计 {span}。"
        if skills:
            top = skills[0]
            text += f" 其中{top['skillName']}最多，{top['times']} 次。"
        if pending_count:
            text += f" 还有 {pending_count} 次等社区确认，确认后才算进去。"

    return {
        "totalTimes": len(confirmed),
        "totalMinutes": total_minutes,
        "skills": skills,
        "pendingCount": pending_count,
        "rejectedCount": rejected_count,
        "dirtyRecordIds": dirty[:20],
        "hasData": has_data,
        "summaryText": text,
        # 这三个字段是给上层看的"我没有越权"的凭证
        "dataOrigin": "P2_CONFIRMED_RECORDS",
        "a3ModifiedAnything": False,
        "countedStatusesOnly": [CONFIRMED],
        "generatedAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def explain_one(record: dict[str, Any]) -> str:
    """解释单条记录为什么算 / 不算。老人问"这次怎么没算"时用得上。

    判断顺序要和 summarize() 完全一致，否则会出现
    「汇总说没算、单独问却说算数」这种自相矛盾。
    """
    status = str(record.get("status") or "").upper()
    name = str(record.get("skillName") or "这次服务")
    minutes = record.get("minutes")

    if status not in STATUSES:
        return f"{name}这条记录状态不明确，我先不往上报，等核对清楚再说。"

    # 已确认也要先过数据体检，跟 summarize 用同一把尺
    if status == CONFIRMED:
        if (not isinstance(minutes, int) or isinstance(minutes, bool)
                or minutes < 0 or minutes > MAX_MINUTES_PER_RECORD):
            return (f"{name}这条记录的时长看着不对，我先不算进去，"
                    f"得回去核对原始打卡。")
        return f"{name}算数，记了 {minutes} 分钟。"

    if status == PENDING:
        return f"{name}还在等社区确认，确认之后才会算进去。"
    return f"{name}这次没通过确认，所以没算。原因可以问社区。"


def to_card(summary: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    base = now or datetime.now(timezone.utc)
    seed = f"{summary['totalTimes']}|{summary['totalMinutes']}|{summary['pendingCount']}"
    digest = hashlib.sha1(seed.encode()).hexdigest()[:12]

    return {
        "resultId": f"contribution-{digest}",
        "type": "ability.contribution_summary",
        "schemaVersion": "1.0",
        "title": "服务贡献记录" if summary["hasData"] else "还没有确认过的贡献",
        "businessRef": None,
        "availability": "DEMO",
        "generatedAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [{"type": summary["dataOrigin"], "id": "p2",
                     "note": "来自 P2 已确认的打卡与服务记录"}],
        "pendingChecks": [
            "本页只做解释，A3 不新增、不修改、不增加任何时长",
            "未确认的记录不计入，等社区确认后自动出现",
            "如有异议请找社区核对原始打卡记录",
        ],
        "payload": {
            "summary": {
                "totalTimes": summary["totalTimes"],
                "totalMinutes": summary["totalMinutes"],
                "skills": summary["skills"],
                "pendingCount": summary["pendingCount"],
                "rejectedCount": summary["rejectedCount"],
            },
            "summaryText": summary["summaryText"],
            "readOnly": True,
            "a3ModifiedAnything": False,
        },
    }


# ---------------------------------------------------------------- 自测
def _selftest() -> int:
    now = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
    rows = [
        {"recordId": "c1", "skillName": "剪纸", "minutes": 90, "status": CONFIRMED},
        {"recordId": "c2", "skillName": "剪纸", "minutes": 90, "status": CONFIRMED},
        {"recordId": "c3", "skillName": "书法", "minutes": 60, "status": CONFIRMED},
        {"recordId": "c4", "skillName": "剪纸", "minutes": 90, "status": PENDING},
        {"recordId": "c5", "skillName": "太极", "minutes": 45, "status": REJECTED},
        {"recordId": "c6", "skillName": "剪纸", "minutes": 99999, "status": CONFIRMED},
    ]

    print("=" * 68)
    print(" 1) 六条记录：3 条已确认、1 条待确认、1 条被拒、1 条脏数据")
    print("=" * 68)
    s = summarize(rows, now=now)
    print(f"  计入 {s['totalTimes']} 次，共 {s['totalMinutes']} 分钟")
    print(f"  待确认 {s['pendingCount']} 条（不算）、被拒 {s['rejectedCount']} 条（不算）")
    print(f"  脏数据踢掉：{s['dirtyRecordIds']}")
    print(f"  话术：{s['summaryText']}")

    print()
    print("=" * 68)
    print(" 2) 按技能分组")
    print("=" * 68)
    for sk in s["skills"]:
        print(f"    {sk['skillName']:<6} {sk['times']} 次  {sk['minutes']} 分钟")

    print()
    print("=" * 68)
    print(" 3) 每条为什么算 / 不算")
    print("=" * 68)
    for row in rows:
        print(f"    {row['recordId']}: {explain_one(row)}")

    print()
    print("=" * 68)
    print(" 4) 一条确认记录都没有")
    print("=" * 68)
    empty = summarize([{"recordId": "x", "status": PENDING, "minutes": 30}], now=now)
    print(f"  话术：{empty['summaryText']}")

    print()
    print("=" * 68)
    print(" 5) 自证没改过任何东西")
    print("=" * 68)
    print(f"  a3ModifiedAnything={s['a3ModifiedAnything']}  "
          f"只统计={s['countedStatusesOnly']}  来源={s['dataOrigin']}")

    print()
    print("结论：只解释、不创造、不增加 —— 贡献记录是一笔账，模型不能经手。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
