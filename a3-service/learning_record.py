#!/usr/bin/env python3
"""A3 学习记录 —— 学习计划、进度解读、作品索引。

分工文档第 9 节：「学习计划、进度、作品和技艺发布；签到/报名工具适配」，
返回「P2 保存事实，P1 展示或上传作品」。

⚠️ 边界（很重要，容易写错）：
    出勤、时长、作品上传这些**事实由 P2 保存**，A3 只做两件事：
      1. 帮老人**拟一个学习计划**（这是建议，不是事实）
      2. 把 P2 给的真实打卡**解读成人话**（这是解释，不是数据）
    A3 不产生任何一条出勤记录，也不上传作品。

所以本文件里没有任何"记录出勤"的函数 —— 只有 plan（计划）和 summarize（解读）。

自测：
    python learning_record.py
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

PLAN_DRAFT = "DRAFT"
PLAN_ACTIVE = "ACTIVE"
PLAN_PAUSED = "PAUSED"
PLAN_FINISHED = "FINISHED"
PLAN_STATES = (PLAN_DRAFT, PLAN_ACTIVE, PLAN_PAUSED, PLAN_FINISHED)

# 打卡状态：只有 ATTENDED 算出勤
ATTENDED = "ATTENDED"
ABSENT = "ABSENT"
CANCELLED = "CANCELLED"

MAX_WEEKLY = 7
MAX_SESSIONS_WARN = 200


class LearningRecordError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def build_plan(course: dict[str, Any], *, weekly_times: int = 1,
               total_sessions: int | None = None, goal: str = "",
               now: datetime | None = None) -> dict[str, Any]:
    """根据一门课拟一个学习计划。

    这是**建议**，不是承诺。老人可能上两次就不去了，
    所以状态起点是 DRAFT，要老人确认后才变 ACTIVE —— 由 P1/P2 改。
    """
    if not isinstance(course, dict) or not course.get("courseId"):
        raise LearningRecordError(400, "INVALID_ARGUMENT", "course 里缺 courseId")
    if not (1 <= weekly_times <= MAX_WEEKLY):
        raise LearningRecordError(400, "INVALID_ARGUMENT", f"weekly_times 必须是 1~{MAX_WEEKLY}")

    duration = int(course.get("durationMin") or 0)
    if duration <= 0:
        raise LearningRecordError(400, "INVALID_ARGUMENT", "课程时长必须大于 0")

    if total_sessions is None:
        # 按每周次数粗估一个合理期数：默认 8 周
        total_sessions = weekly_times * 8
    if not (1 <= total_sessions <= 200):
        raise LearningRecordError(400, "INVALID_ARGUMENT", "total_sessions 必须是 1~200")

    base = now or datetime.now(timezone.utc)
    seed = f"{course['courseId']}|{weekly_times}|{total_sessions}"
    digest = hashlib.sha1(seed.encode()).hexdigest()[:12]

    return {
        "planId": f"plan-{digest}",
        "courseId": course["courseId"],
        "courseTitle": course.get("title") or "",
        "venue": course.get("venue") or "",
        "walkMinutes": int(course.get("walkMinutes") or 0),
        "sessionDurationMin": duration,
        "weeklyTimes": weekly_times,
        "totalSessions": total_sessions,
        "plannedTotalMinutes": duration * total_sessions,
        "goal": (goal or "")[:200],
        # 计划是建议，等老人确认；A3 不替老人定下来
        "state": PLAN_DRAFT,
        "createdAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def summarize_progress(plan: dict[str, Any], sessions: list[dict[str, Any]] | None = None,
                       *, now: datetime | None = None) -> dict[str, Any]:
    """把 P2 给的打卡记录解读成"学得怎么样"。

    没有记录就是没有记录 —— 不能按"计划上过几次"倒推实际出勤，
    那等于替老人编考勤。
    """
    if not isinstance(plan, dict) or not plan.get("planId"):
        raise LearningRecordError(400, "INVALID_ARGUMENT", "plan 里缺 planId")

    records = sessions or []
    if len(records) > MAX_SESSIONS_WARN:
        raise LearningRecordError(400, "INVALID_ARGUMENT", "打卡记录过多，请分页查询")

    attended = [r for r in records if str(r.get("status")).upper() == ATTENDED]
    absent = [r for r in records if str(r.get("status")).upper() == ABSENT]
    cancelled = [r for r in records if str(r.get("status")).upper() == CANCELLED]

    total = int(plan.get("totalSessions") or 0)
    done = len(attended)
    # 时长只累加真实打卡过的，不按计划时长×次数估
    actual_minutes = sum(int(r.get("durationMin") or 0) for r in attended)

    base = now or datetime.now(timezone.utc)
    has_data = bool(records)

    if not has_data:
        summary = "还没有打卡记录，等上过课之后才能看进度。"
    elif done == 0:
        summary = f"约了 {len(absent) + len(cancelled)} 次但都还没上成，要不要调整一下时间？"
    else:
        pct = round(done / total * 100) if total else 0
        summary = (f"已经上了 {done} 次课，累计 {actual_minutes} 分钟，"
                   f"计划里完成了 {pct}%。")
        if absent:
            summary += f" 有 {len(absent)} 次没去。"

    return {
        "planId": plan["planId"],
        "courseTitle": plan.get("courseTitle") or "",
        "hasRecords": has_data,
        "attendedCount": done,
        "absentCount": len(absent),
        "cancelledCount": len(cancelled),
        "actualMinutes": actual_minutes,
        "plannedMinutes": int(plan.get("plannedTotalMinutes") or 0),
        "totalSessions": total,
        "remainingSessions": max(0, total - done),
        "completionPercent": (round(done / total * 100) if total else 0),
        "summaryText": summary,
        # 明确标注：数字来自 P2 打卡，A3 没有估算成分
        "dataOrigin": "P2_ATTENDANCE_RECORDS" if has_data else "NO_RECORDS",
        "generatedAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def to_plan_card(plan: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    base = now or datetime.now(timezone.utc)
    return {
        "resultId": f"learning-plan-{plan['planId'][-12:]}",
        "type": "culture.learning_plan",
        "schemaVersion": "1.0",
        "title": f"学习计划：{plan.get('courseTitle') or '课程'}",
        "businessRef": None,
        "availability": "DEMO",
        "generatedAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [{"type": "COURSE", "id": plan["courseId"], "note": "演示课程数据"}],
        "pendingChecks": [
            "计划是建议，需老人确认后才生效",
            "实际开课时间以场馆公告为准",
        ],
        "payload": {
            "plan": plan,
            "confirmRequired": True,
        },
    }


def to_progress_card(summary: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    base = now or datetime.now(timezone.utc)
    return {
        "resultId": f"learning-progress-{summary['planId'][-12:]}",
        "type": "culture.learning_progress",
        "schemaVersion": "1.0",
        "title": "学习进度" if summary["hasRecords"] else "还没有打卡记录",
        "businessRef": None,
        "availability": "DEMO",
        "generatedAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [{"type": summary["dataOrigin"], "id": summary["planId"]}],
        "pendingChecks": [
            "出勤与时长以 P2 打卡记录为准，A3 只做解读不做估算",
            "作品由老人本人或家属通过 P1 上传",
        ],
        "payload": dict(summary),
    }


# ---------------------------------------------------------------- 自测
def _selftest() -> int:
    now = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
    course = {"courseId": "demo-papercut-01", "title": "剪纸入门班",
              "venue": "阳光社区活动室", "walkMinutes": 5, "durationMin": 90}

    print("=" * 68)
    print(" 1) 给剪纸班拟个计划：每周两次")
    print("=" * 68)
    plan = build_plan(course, weekly_times=2, goal="学会剪窗花", now=now)
    print(f"  {plan['planId']}  {plan['courseTitle']}")
    print(f"  每周 {plan['weeklyTimes']} 次 × {plan['totalSessions']} 次 = "
          f"{plan['plannedTotalMinutes']} 分钟")
    print(f"  状态：{plan['state']}（计划是建议，等老人确认）")

    print()
    print("=" * 68)
    print(" 2) 还没打卡 —— 不能倒推成「没去」")
    print("=" * 68)
    s = summarize_progress(plan, [], now=now)
    print(f"  hasRecords={s['hasRecords']}  数据来源={s['dataOrigin']}")
    print(f"  话术：{s['summaryText']}")

    print()
    print("=" * 68)
    print(" 3) 有真实打卡：去 3 次、缺 1 次")
    print("=" * 68)
    sessions = [
        {"date": "2026-11-05", "durationMin": 90, "status": ATTENDED},
        {"date": "2026-11-07", "durationMin": 90, "status": ATTENDED},
        {"date": "2026-11-09", "durationMin": 90, "status": ATTENDED},
        {"date": "2026-11-11", "durationMin": 0, "status": ABSENT},
    ]
    s = summarize_progress(plan, sessions, now=now)
    print(f"  上了 {s['attendedCount']} 次，实际 {s['actualMinutes']} 分钟"
          f"（不是 {plan['plannedTotalMinutes']} 分钟 —— 只算真上过的）")
    print(f"  完成度 {s['completionPercent']}%  还剩 {s['remainingSessions']} 次")
    print(f"  话术：{s['summaryText']}")
    print(f"  数据来源：{s['dataOrigin']}")

    print()
    print("=" * 68)
    print(" 4) 全缺勤")
    print("=" * 68)
    s = summarize_progress(plan, [{"durationMin": 0, "status": ABSENT}] * 2, now=now)
    print(f"  话术：{s['summaryText']}")

    print()
    print("结论：计划是建议、进度是解读、出勤是 P2 的事实 —— 三者不能混。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
