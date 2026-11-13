#!/usr/bin/env python3
"""A3 非遗文化 —— 文化课候选与推荐（纯函数，零依赖，不联网）。

队友已经确认：**文化课先用假数据**。所以这里所有课程都是造出来的，
但造得很认真 —— 因为"假数据"最容易出的问题不是不好看，是**假装是真的**。

三条底线（每一条都对应 v3 的具体要求）：
1. `availability` 恒为 `DEMO`，而且 `sources` 里写明数据来源是演示集。
   v3 原文：「A2/A3可先给固定测试案例，必须标DEMO」。
2. `businessRef` 恒为 `null`。假课程没有真实的业务对象，
   编一个 `courseId: "c-001"` 塞进去，P2 那边真去查就会 404。
3. **只查不报名**。v3 样例 30 里 A1 给 A3 的指令写得很清楚：
   「查询演示文化活动，不报名不通知」。所以本文件没有任何写操作，
   输出的卡片里也没有 `actionId` —— 想报名必须走 A1→确认→P2。

为什么排期用「周几 + 几点」而不是写死日期？
    写死 "2026-11-05" 的假数据，过两周就全过期了，演示时一个都匹配不上。
    用 `weekdays + timeOfDay` 现算下一次上课时间，永远不会过期。

自测：
    python culture_courses.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

# v3：演示数据集的版本号，写进 sources，方便以后换真数据时区分
DATASET_ID = "a3-culture-demo-v1"
AVAILABILITY_DEMO = "DEMO"

# 非遗课程的类别（A3 只管文化这一块，别的领域不碰）
KINDS = ("papercut", "embroidery", "calligraphy", "taichi", "opera", "folk_music")

KIND_LABELS = {
    "papercut": "剪纸",
    "embroidery": "刺绣",
    "calligraphy": "书法",
    "taichi": "太极",
    "opera": "戏曲",
    "folk_music": "民乐",
}

# 记忆里的兴趣词 → 课程类别。老人说的是"剪纸"，库里存的是 papercut。
_INTEREST_ALIASES: dict[str, tuple[str, ...]] = {
    "papercut": ("剪纸", "窗花", "纸艺"),
    "embroidery": ("刺绣", "绣花", "苏绣", "十字绣"),
    "calligraphy": ("书法", "写字", "毛笔"),
    "taichi": ("太极", "太极拳", "八段锦"),
    "opera": ("戏曲", "京剧", "越剧", "唱戏"),
    "folk_music": ("民乐", "二胡", "琵琶", "笛子", "唱歌"),
}

# 默认上限（适老：走得太远、坐得太久都不合适）
DEFAULT_MAX_WALK_MINUTES = 20
DEFAULT_MAX_DURATION_MIN = 120
DEFAULT_LIMIT = 3

# ------------------------------------------------------------------ 演示数据
# 全部编造，但字段都按真实课程该有的样子给。
# `weekdays` 用 ISO 编号：1=周一 … 7=周日。
DEMO_COURSES: list[dict[str, Any]] = [
    {"courseId": "demo-papercut-01", "kind": "papercut", "title": "剪纸入门班",
     "venue": "阳光社区活动室", "walkMinutes": 5, "durationMin": 90,
     "weekdays": [4], "timeOfDay": "09:30", "level": "入门",
     "seatsLeft": 8, "hasSteps": False, "liftAvailable": True,
     "tags": ["非遗", "手工", "坐着上课"],
     "note": "工具现场提供，带一副老花镜就行"},
    {"courseId": "demo-papercut-02", "kind": "papercut", "title": "窗花剪纸提高班",
     "venue": "区文化馆三楼", "walkMinutes": 18, "durationMin": 120,
     "weekdays": [2], "timeOfDay": "14:00", "level": "进阶",
     "seatsLeft": 2, "hasSteps": True, "liftAvailable": True,
     "tags": ["非遗", "手工"], "note": "楼里有电梯，但要先上三级台阶"},
    {"courseId": "demo-embroidery-01", "kind": "embroidery", "title": "苏绣基础",
     "venue": "老年大学东教室", "walkMinutes": 12, "durationMin": 100,
     "weekdays": [1, 5], "timeOfDay": "10:00", "level": "入门",
     "seatsLeft": 5, "hasSteps": False, "liftAvailable": True,
     "tags": ["非遗", "手工", "坐着上课"], "note": "绣绷和丝线由老师统一准备"},
    {"courseId": "demo-calligraphy-01", "kind": "calligraphy", "title": "楷书入门",
     "venue": "社区书屋", "walkMinutes": 8, "durationMin": 60,
     "weekdays": [3], "timeOfDay": "15:00", "level": "入门",
     "seatsLeft": 10, "hasSteps": False, "liftAvailable": False,
     "tags": ["静心", "坐着上课"], "note": "每次只练两个字，不赶进度"},
    {"courseId": "demo-taichi-01", "kind": "taichi", "title": "八段锦晨练",
     "venue": "和平公园东门广场", "walkMinutes": 15, "durationMin": 45,
     "weekdays": [1, 2, 3, 4, 5], "timeOfDay": "07:00", "level": "入门",
     "seatsLeft": 30, "hasSteps": False, "liftAvailable": False,
     "tags": ["室外", "站着", "晨练"], "note": "全程站立，地面平整，有长椅可休息"},
    {"courseId": "demo-opera-01", "kind": "opera", "title": "京剧票友会",
     "venue": "区文化馆小剧场", "walkMinutes": 20, "durationMin": 150,
     "weekdays": [6], "timeOfDay": "14:30", "level": "不限",
     "seatsLeft": 40, "hasSteps": True, "liftAvailable": False,
     "tags": ["听戏", "坐着"], "note": "主要听唱段，不用上台"},
    {"courseId": "demo-folk-01", "kind": "folk_music", "title": "二胡零基础",
     "venue": "老年大学音乐教室", "walkMinutes": 12, "durationMin": 90,
     "weekdays": [2], "timeOfDay": "09:00", "level": "入门",
     "seatsLeft": 0, "hasSteps": False, "liftAvailable": True,
     "tags": ["乐器", "坐着上课"], "note": "本期名额已满，可登记下期候补"},
    {"courseId": "demo-papercut-03", "kind": "papercut", "title": "亲子剪纸体验日",
     "venue": "图书馆一楼大厅", "walkMinutes": 25, "durationMin": 60,
     "weekdays": [7], "timeOfDay": "10:00", "level": "入门",
     "seatsLeft": 15, "hasSteps": False, "liftAvailable": True,
     "tags": ["非遗", "手工", "可带孙辈"], "note": "适合带孙辈一起来"},
]


# ------------------------------------------------------------------ 筛选
def has_interest_info(interests: Any) -> bool:
    """老人的偏好信息到底有没有。

    必须和「有偏好但对不上」分开：
        interests=None      → 不知道老人喜欢什么 → 不按兴趣筛，全给
        interests="喜欢跳伞" → 知道，但我们没有这类班 → 该返回空，并说明白
    把这两种混成一种，就会出现「老人想看跳伞，系统硬塞剪纸班」，
    或者「老人喜欢剪纸，系统说没找到」。
    """
    if interests is None:
        return False
    if isinstance(interests, (list, tuple, set)):
        return any(str(x).strip() for x in interests)
    return bool(str(interests).strip())


def kinds_from_interests(interests: Any) -> list[str]:
    """把记忆里的"喜欢剪纸和刺绣"翻成 ['papercut', 'embroidery']。

    正常情况下面向的是记忆里 `culture.interests` 的 content 文本。
    认不出来就返回空列表 —— 宁可不筛，也不要瞎猜老人的喜好。
    """
    if not interests:
        return []
    text = " ".join(str(x) for x in interests) if isinstance(interests, (list, tuple, set)) \
        else str(interests)

    hits: list[str] = []
    for kind, aliases in _INTEREST_ALIASES.items():
        if any(alias in text for alias in aliases):
            hits.append(kind)
    return hits


def filter_courses(courses: list[dict[str, Any]], *,
                   interests: Any = None,
                   max_walk_minutes: int | None = DEFAULT_MAX_WALK_MINUTES,
                   max_duration_min: int | None = DEFAULT_MAX_DURATION_MIN,
                   need_step_free: bool = False,
                   only_with_seats: bool = True,
                   exclude_kinds: list[str] | None = None) -> list[dict[str, Any]]:
    """按老人的条件筛课程。**只筛不排**，排序交给 rank_courses。

    参数为 None 表示这一条不限制。默认值偏保守（走路 20 分钟内、时长 2 小时内），
    因为适老场景下"给多了"比"给少了"更糟 —— 一堆选项摆在面前，老人反而选不出来。
    """
    wanted = kinds_from_interests(interests)
    informed = has_interest_info(interests)
    # 知道老人喜欢什么，但我们的课程里一门对口的都没有 → 老实返回空。
    # 这时候返回全部课，就是在拿不相关的东西凑数。
    if informed and not wanted:
        return []

    blocked = set(exclude_kinds or ())

    picked: list[dict[str, Any]] = []
    for course in courses:
        if course["kind"] in blocked:
            continue
        if wanted and course["kind"] not in wanted:
            continue
        if max_walk_minutes is not None and course["walkMinutes"] > max_walk_minutes:
            continue
        if max_duration_min is not None and course["durationMin"] > max_duration_min:
            continue
        if need_step_free and course["hasSteps"]:
            continue
        if only_with_seats and course["seatsLeft"] <= 0:
            continue
        picked.append(course)
    return picked


def rank_courses(courses: list[dict[str, Any]], *,
                 interests: Any = None,
                 max_walk_minutes: int = DEFAULT_MAX_WALK_MINUTES,
                 max_duration_min: int = DEFAULT_MAX_DURATION_MIN) -> list[dict[str, Any]]:
    """打分排序。分数越高越靠前，**分数和理由都要能讲给老人听**。

    打分维度只有三个，因为再多老人也理解不了：
        兴趣对口   +100（最要紧 —— 不喜欢的话再近也不去）
        走得近     -1/分钟
        时间合适   -0.5/超出的分钟，没超不加不减
    """
    wanted = set(kinds_from_interests(interests))
    scored: list[tuple[float, dict[str, Any]]] = []

    for course in courses:
        score = 0.0
        reasons: list[str] = []

        if wanted and course["kind"] in wanted:
            score += 100
            reasons.append(f"您喜欢{KIND_LABELS.get(course['kind'], course['kind'])}")

        score -= course["walkMinutes"]
        if course["walkMinutes"] <= 10:
            reasons.append(f"走过去只要 {course['walkMinutes']} 分钟")

        over = max(0, course["durationMin"] - max_duration_min)
        score -= over * 0.5

        if course["seatsLeft"] > 0:
            score += 5
        if not course["hasSteps"]:
            score += 3
            reasons.append("不用爬台阶")

        scored.append((score, {**course, "score": round(score, 1), "reasons": reasons}))

    # 同分时按 courseId 排，保证每次运行结果一样（可复现才好排查）
    scored.sort(key=lambda pair: (-pair[0], pair[1]["courseId"]))
    return [item for _, item in scored]


# ------------------------------------------------------------------ 排期
def next_session(course: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """算出下一次上课的实际时间。

    不用写死日期，是为了让演示数据永远不过期。
    返回 {"startAt": ISO, "endAt": ISO, "weekdayLabel": "周四"}
    """
    base = now or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)

    hour, minute = (int(part) for part in course["timeOfDay"].split(":"))
    weekdays = sorted(course["weekdays"])

    for offset in range(0, 8):
        day = base + timedelta(days=offset)
        if day.isoweekday() not in weekdays:
            continue
        start = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start <= base:
            continue
        end = start + timedelta(minutes=course["durationMin"])
        return {
            "startAt": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endAt": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "weekdayLabel": "周" + "一二三四五六日"[start.isoweekday() - 1],
        }

    # 八个课程都是每周固定，走不到这里；真到了说明数据配错了
    return {"startAt": None, "endAt": None, "weekdayLabel": None}


# ------------------------------------------------------------------ 输出卡片
def to_result_card(courses: list[dict[str, Any]], *,
                   query: dict[str, Any] | None = None,
                   now: datetime | None = None,
                   limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """产出 v3 的 Result 卡片（结构见 control.schema.json 的 Result）。

    这是 P2 能直接转给前端的形状。四个必须做对的地方：
        1. availability = "DEMO"，不能写 REAL
        2. businessRef = null，假数据不编业务 ID
        3. sources 里写明数据来自演示集
        4. pendingChecks 里写明"报名前要核实"，不能替老人做主
    """
    base = now or datetime.now(timezone.utc)
    kept = courses[:limit]

    items: list[dict[str, Any]] = []
    for course in kept:
        session = next_session(course, base)
        items.append({
            "courseId": course["courseId"],
            "title": course["title"],
            "kind": course["kind"],
            "kindLabel": KIND_LABELS.get(course["kind"], course["kind"]),
            "venue": course["venue"],
            "walkMinutes": course["walkMinutes"],
            "durationMin": course["durationMin"],
            "level": course["level"],
            "seatsLeft": course["seatsLeft"],
            "hasSteps": course["hasSteps"],
            "tags": list(course["tags"]),
            "note": course["note"],
            "nextSession": session,
            "reasons": list(course.get("reasons") or []),
        })

    seed = json.dumps([item["courseId"] for item in items], ensure_ascii=False)
    digest = hashlib.sha1(f"{DATASET_ID}|{seed}|{query}".encode()).hexdigest()[:12]

    return {
        "resultId": f"culture-courses-{digest}",
        "type": "culture.course_candidates",
        "schemaVersion": "1.0",
        "title": "附近可以参加的非遗文化活动" if items else "这次没找到合适的课程",
        # 假课程没有真实业务对象，编一个 ID 会让 P2 去查一个不存在的课
        "businessRef": None,
        "availability": AVAILABILITY_DEMO,
        "generatedAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [{
            "type": "DEMO_DATASET",
            "id": DATASET_ID,
            "note": "演示数据集，课程、场馆、名额均为虚构，仅用于联调与演示",
        }],
        "pendingChecks": [
            "课程为演示数据，实际开课以场馆公告为准",
            "名额为演示值，报名前需向场馆确认",
            "A3 不代办报名，报名需经本人确认后由平台执行",
        ],
        "payload": {
            "query": dict(query or {}),
            "totalCandidates": len(items),
            "courses": items,
            # 让前端和 P2 一眼看出：这不是报名，只是查
            "readOnly": True,
            "booked": False,
            "notified": False,
        },
    }


def build_reply_text(courses: list[dict[str, Any]], *, limit: int = DEFAULT_LIMIT,
                     now: datetime | None = None) -> str:
    """给老人看的话。短句、具体、不堆信息。

    适老三条：先说"找到了几个"，再说"最近的那个怎么样"，
    最后给一个明确的下一步。一次不超过 3 个选项。
    """
    if not courses:
        return "这次没找到走路能到、时间也合适的班。要不我换个范围再帮您找找？"

    base = now or datetime.now(timezone.utc)
    kept = courses[:limit]
    first = kept[0]
    session = next_session(first, base)

    head = f"找到 {len(kept)} 个可以去的班。" if len(kept) > 1 else "找到一个可以去的班。"
    when = f"{session['weekdayLabel']}{_cn_time(first['timeOfDay'])}" \
        if session["weekdayLabel"] else ""

    detail = (f"最近的是{first['venue']}的{first['title']}，"
              f"走过去大概 {first['walkMinutes']} 分钟，{when}上课。")
    tail = f"还有 {len(kept) - 1} 个备选，我念给您听？" if len(kept) > 1 else "要去的话我帮您问问还有没有名额。"
    return head + detail + tail


def _cn_time(text: str) -> str:
    """"09:30" → "上午九点半"。

    老人听数字容易串，"14:30" 念成"十四点半"他能听懂，
    但"下午两点半"是他自己说话的方式。能转就转。
    """
    hour, minute = (int(part) for part in text.split(":"))

    if hour < 6:
        period = "凌晨"
    elif hour < 9:
        period = "早上"
    elif hour < 12:
        period = "上午"
    elif hour == 12:
        period = "中午"
    elif hour < 18:
        period = "下午"
    else:
        period = "晚上"

    hour_cn = _cn_hour(hour)
    if minute == 0:
        return f"{period}{hour_cn}点"
    if minute == 30:
        return f"{period}{hour_cn}点半"
    return f"{period}{hour_cn}点{minute}分"


def _cn_hour(hour: int) -> str:
    """1~12 → 一~十二；13 点以后按下午算，减 12。

    2 点要念「两点」不是「二点」—— 中文里说钟点用「两」不用「二」。
    """
    if hour == 0:
        return "十二"
    if hour > 12:
        hour -= 12
    if hour == 2:
        return "两"
    digits = "零一二三四五六七八九十"
    if hour <= 10:
        return digits[hour]
    return "十一" if hour == 11 else "十二"


# ------------------------------------------------------------------ 自测
def _selftest() -> int:
    now = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)   # 周五早上八点

    print("=" * 70)
    print(" 1) 记忆说「喜欢剪纸和刺绣，走路别超过一刻钟」")
    print("=" * 70)
    picked = filter_courses(DEMO_COURSES, interests="喜欢剪纸和刺绣",
                            max_walk_minutes=15)
    ranked = rank_courses(picked, interests="喜欢剪纸和刺绣", max_walk_minutes=15)
    print(f"  筛出 {len(picked)} 个：")
    for course in ranked:
        print(f"    {course['courseId']:<20} {course['title']:<10} "
              f"走{course['walkMinutes']:>2}分  {course['durationMin']:>3}分钟  "
              f"分数={course['score']}")
    print(f"  被排除的：")
    for course in DEMO_COURSES:
        if course not in picked:
            why = []
            if course["kind"] not in kinds_from_interests("喜欢剪纸和刺绣"):
                why.append("不对口")
            if course["walkMinutes"] > 15:
                why.append(f"要走{course['walkMinutes']}分钟")
            if course["seatsLeft"] <= 0:
                why.append("没名额")
            print(f"    {course['courseId']:<20} {','.join(why)}")

    print()
    print("=" * 70)
    print(" 2) 老人腿脚不便：要求不用爬台阶")
    print("=" * 70)
    step_free = filter_courses(DEMO_COURSES, need_step_free=True)
    print(f"  不用爬台阶的有 {len(step_free)} 个")
    print(f"  被排除的：")
    for course in DEMO_COURSES:
        if course["hasSteps"]:
            print(f"    {course['courseId']:<20} {course['note']}")

    print()
    print("=" * 70)
    print(" 3) 生成 v3 卡片（availability 必须是 DEMO）")
    print("=" * 70)
    card = to_result_card(ranked, now=now, query={"interests": "剪纸刺绣", "maxWalkMinutes": 15})
    print(f"  resultId={card['resultId']}")
    print(f"  availability={card['availability']}   businessRef={card['businessRef']!r}")
    print(f"  卡片条数={card['payload']['totalCandidates']}  readOnly={card['payload']['readOnly']}")
    print(f"  第一条：{card['payload']['courses'][0]['title']}  "
          f"{card['payload']['courses'][0]['nextSession']}")

    print()
    print("=" * 70)
    print(" 4) 说给老人听的话")
    print("=" * 70)
    print(f"  「{build_reply_text(ranked, now=now)}」")

    print()
    print("=" * 70)
    print(" 5) 老人说想学跳伞 —— 我们有剪纸班，但这不是他想要的")
    print("=" * 70)
    none = filter_courses(DEMO_COURSES, interests="喜欢跳伞")
    print(f"  知道偏好但对不上 → 筛出 {len(none)} 个")
    print(f"  卡片 availability={to_result_card(none, now=now)['availability']}"
          f"（还是 DEMO，不是 UNAVAILABLE）")
    print(f"  话术：「{build_reply_text(none, now=now)}」")
    print("  说明：不能因为「不知道给什么」就把剪纸班硬塞过去")
    print()
    unknown = filter_courses(DEMO_COURSES, interests=None)
    print(f"  完全不知道偏好（interests=None）→ 筛出 {len(unknown)} 个（先全给，靠排序和 limit 收）")
    print("  说明：这两种必须分开 —— 「不知道」和「知道但没有」是两件事")

    print()
    print("=" * 70)
    print(" 6) 排期永远不过期：同一个课，隔三个月再看")
    print("=" * 70)
    course = DEMO_COURSES[0]
    for shift in (0, 90, 180):
        moment = now + timedelta(days=shift)
        print(f"  {moment:%Y-%m-%d} → {next_session(course, moment)['startAt']}"
              f"（{next_session(course, moment)['weekdayLabel']}）")
    print("  说明：写死日期的话，过两周演示时就全过期了")

    print()
    print("结论：只查不报名、假数据标 DEMO、排期不过期、话术适老 —— 这四条守住了才算能用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
