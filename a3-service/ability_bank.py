#!/usr/bin/env python3
"""A3 能力银行 —— 老人登记技能、表达传授意愿、供需匹配、服务流程。

分工文档第 9 节：「技能、传授意愿、供需匹配与服务流程」，
返回「发布、审核、报名、打卡、佐证、评价、贡献记录」。

⚠️ 一条边界必须记牢（文档第 10 节）：
    老人**登记技能、提供帮助意愿** → 归 A3（供给侧）
    为老人**找帮助** → 归 A2（需求侧）
    两边复用同一份后端记录。所以 A3 这里不实现"帮老人找护工/找陪同"。

⚠️ 另一条更要紧（文档第 9 节原话）：
    「不由模型自行审核通过、增加时长或创造贡献」
    所以本文件里：
      - 没有任何函数能把状态从 REVIEWING 改成 PUBLISHED（那必须是 P2/社区的动作）
      - 没有任何函数能写时长（时长只能来自打卡事实）
      - 匹配结果只是"推荐"，不是"已安排有人来"

自测：
    python ability_bank.py
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

# 服务流程的六个阶段。A3 只负责推进和解释，不负责"批准"。
STAGE_SUBMITTED = "SUBMITTED"      # 老人刚登记
STAGE_REVIEWING = "REVIEWING"      # 等社区/P2 审核（A3 不能自己过）
STAGE_PUBLISHED = "PUBLISHED"      # 已发布，可参与匹配
STAGE_MATCHING = "MATCHING"        # 有需求方在对接
STAGE_SERVING = "SERVING"          # 服务进行中，等打卡
STAGE_FINISHED = "FINISHED"        # 已完成，可整理贡献
STAGE_REJECTED = "REJECTED"        # 审核未通过

STAGES = (STAGE_SUBMITTED, STAGE_REVIEWING, STAGE_PUBLISHED,
          STAGE_MATCHING, STAGE_SERVING, STAGE_FINISHED, STAGE_REJECTED)

# 传授意愿。分三档而不是"愿意/不愿意"，因为现实里很多老人只愿意教熟人。
WILL_PUBLIC = "TEACH_PUBLIC"           # 愿意公开教，谁都可以报名
WILL_ACQUAINTANCE = "TEACH_ACQUAINTANCE"  # 只愿意教认识的邻居/熟人
WILL_NONE = "NOT_TEACH"                # 只是自己会，不想教

WILLINGNESS = (WILL_PUBLIC, WILL_ACQUAINTANCE, WILL_NONE)

WILLINGNESS_LABEL = {
    WILL_PUBLIC: "愿意公开教",
    WILL_ACQUAINTANCE: "只愿意教熟人",
    WILL_NONE: "暂时不想教",
}

MAX_SKILLS_PER_USER = 20
MAX_SLOTS_PER_WEEK = 21      # 一周最多 21 个时段，超过说明填错了

# 从老人话里认技能。只列常见、边界清楚的；认不出来就不生成登记，
# 宁可让 A1 再问一句，也不要瞎猜老人会什么。
_SKILL_WORDS = {
    "剪纸": ("纸艺", ["剪纸", "窗花", "刻纸"]),
    "刺绣": ("纸艺", ["刺绣", "绣花", "十字绣"]),
    "书法": ("书画", ["书法", "毛笔字", "写毛笔"]),
    "绘画": ("书画", ["画画", "国画", "绘画"]),
    "太极": ("健身", ["太极", "太极拳", "八段锦"]),
    "广场舞": ("健身", ["广场舞", "跳舞"]),
    "戏曲": ("表演", ["唱戏", "戏曲", "京剧", "越剧"]),
    "民乐": ("表演", ["二胡", "琵琶", "笛子", "弹琴"]),
    "烹饪": ("生活", ["做饭", "厨艺", "烧菜", "做菜"]),
    "裁缝": ("生活", ["缝纫", "裁缝", "做衣服"]),
    "理发": ("生活", ["理发", "剪头发"]),
    "修理": ("生活", ["修电器", "修东西", "维修"]),
}

_WILL_PUBLIC_WORDS = ("愿意教", "可以教", "教大家", "带大家一起", "愿意带")
_WILL_ACQ_WORDS = ("教教邻居", "熟人", "认识的人", "街坊", "只教身边")
_WILL_NONE_WORDS = ("不想教", "不教别人", "自己玩玩", "不教")

# 必须出现"我已经会这个"的说法，才认为是在登记技能。
# 不加这道判断，"想学剪纸" 会被认成"会剪纸"，给老人凭空生成一条技能登记 ——
# 他会收到"您已登记剪纸技能"的确认，可他明明是想学。
_HAVE_WORDS = ("我会", "我会做", "擅长", "做过", "干过", "以前是做", "以前是干",
               "懂一点", "会一点", "我做过", "年轻时做", "干这行", "我做")

# 否定说法要挡掉："我做不了饭" 里有"我做"，但不是会做饭。
_NEG_WORDS = ("做不了", "不会", "没有会", "不擅长", "不懂")

# 反过来，"想学""能不能教教我"这类是在表达需求，不是供给
_WANT_WORDS = ("想学", "要学", "学一下", "教我", "能不能学", "怎么学")


class AbilityBankError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# ---------------------------------------------------------------- 技能识别
def parse_skill(text: str) -> dict[str, Any] | None:
    """从一句话里认出"会什么 + 愿不愿意教"。

    认不出技能就返回 None —— 不生成登记。生成一条错的技能比不生成更糟：
    老人会收到"您已登记剪纸技能"的确认，可他从没说过。
    """
    body = (text or "").strip()
    if not body:
        return None

    # 先分清"我会"和"我想学"。这是在表达需求（归 A2 找帮助）还是供给（归 A3 登记）。
    if any(w in body for w in _NEG_WORDS):
        return None
    if any(w in body for w in _WANT_WORDS) and not any(w in body for w in _HAVE_WORDS):
        return None
    if not any(w in body for w in _HAVE_WORDS):
        return None

    skill = category = None
    for name, (cat, aliases) in _SKILL_WORDS.items():
        if any(alias in body for alias in aliases) or name in body:
            skill, category = name, cat
            break
    if skill is None:
        return None

    if any(w in body for w in _WILL_NONE_WORDS):
        willingness = WILL_NONE
    elif any(w in body for w in _WILL_ACQ_WORDS):
        willingness = WILL_ACQUAINTANCE
    elif any(w in body for w in _WILL_PUBLIC_WORDS):
        willingness = WILL_PUBLIC
    else:
        # 说了会什么但没说愿不愿意教 —— 默认最保守的一档，等老人明确
        willingness = WILL_ACQUAINTANCE

    slots = 1
    # "一周能安排两次" / "一周两次" / "一周可以教三次" 都要认。
    # 数字前面可能夹着"能安排""可以教"这类动词，所以用 [^数字]{0,4} 跳过。
    match = re.search(r"一周[^一二两三四五六七\d]{0,4}([一二两三四五六七\d]+)\s*(?:次|个时段)", body)
    if match:
        raw = match.group(1)
        table = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
        slots = table.get(raw, int(raw) if raw.isdigit() else 1)

    return {
        "skillName": skill,
        "category": category,
        "willingness": willingness,
        "weeklySlots": max(1, min(slots, MAX_SLOTS_PER_WEEK)),
    }


def build_skill_record(user_id: str, parsed: dict[str, Any], *,
                       note: str = "", skill_id: str | None = None,
                       now: datetime | None = None) -> dict[str, Any]:
    """把识别结果做成一条待审核的技能登记。

    注意 state 起点是 SUBMITTED，不是 PUBLISHED ——
    A3 没有权力让一条技能直接上线，那要社区或 P2 审核（文档第 9 节）。
    """
    if not user_id or not str(user_id).strip():
        raise AbilityBankError(400, "INVALID_ARGUMENT", "userId 必填")
    if not parsed or not parsed.get("skillName"):
        raise AbilityBankError(400, "INVALID_ARGUMENT", "没有识别出技能")
    if parsed.get("willingness") not in WILLINGNESS:
        raise AbilityBankError(400, "INVALID_ARGUMENT", "传授意愿取值不合法")

    base = now or datetime.now(timezone.utc)
    skill = parsed["skillName"]
    sid = skill_id or hashlib.sha1(f"{user_id}|{skill}".encode()).hexdigest()[:12]

    return {
        "skillId": f"skill-{sid}",
        "userId": str(user_id),
        "skillName": skill,
        "category": parsed.get("category") or "其他",
        "willingness": parsed["willingness"],
        "willingnessLabel": WILLINGNESS_LABEL[parsed["willingness"]],
        "weeklySlots": int(parsed.get("weeklySlots") or 1),
        "note": (note or "")[:200],
        "state": STAGE_SUBMITTED,
        "createdAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
        # 只记来源，不记"已审核通过"之类的事实 —— 那是 P2 的字段
        "sourceRefs": [{"type": "USER_MESSAGE", "id": ""}],
    }


# ---------------------------------------------------------------- 流程
def next_action(record: dict[str, Any]) -> dict[str, Any]:
    """告诉调用方：这条登记现在卡在哪、下一步该谁做什么。

    这是 A3 在这块最实在的价值 —— 把"流程走到哪一步、谁该动"讲清楚，
    而不是含糊地说"已提交"。
    """
    state = record.get("state")
    if state not in STAGES:
        raise AbilityBankError(400, "INVALID_ARGUMENT", f"未知状态：{state}")

    table = {
        STAGE_SUBMITTED: ("等社区审核", "社区或 P2 审核技能真实性", "P2"),
        STAGE_REVIEWING: ("审核中", "等审核结果，A3 不能自己通过", "P2"),
        STAGE_PUBLISHED: ("已发布", "可以参与供需匹配了", "A3"),
        STAGE_MATCHING: ("对接中", "等需求方确认，不承诺一定有人报名", "需求方"),
        STAGE_SERVING: ("服务中", "等打卡和佐证，时长以打卡记录为准", "P1/P2"),
        STAGE_FINISHED: ("已完成", "可以整理贡献记录了", "A3"),
        STAGE_REJECTED: ("未通过", "可以补充材料后重新提交", "老人本人"),
    }
    label, todo, owner = table[state]
    return {"state": state, "stageLabel": label, "todo": todo, "owner": owner,
            # 明确写出来，防止上层误以为 A3 能批准
            "a3CanAdvance": state in (STAGE_PUBLISHED, STAGE_FINISHED)}


def match_supply_demand(supplies: list[dict[str, Any]],
                        demands: list[dict[str, Any]], *,
                        limit: int = 3) -> list[dict[str, Any]]:
    """把"老人会的手艺"和"有人想学的需求"配对。

    只输出**推荐**，不输出"已安排"。文档写得很清楚：
    不能承诺自动有人接单。所以结果里带 `confirmed=false`。
    """
    if not (1 <= limit <= 10):
        raise AbilityBankError(400, "INVALID_ARGUMENT", "limit 必须是 1~10")

    results: list[dict[str, Any]] = []
    for demand in demands:
        want = (demand.get("skillName") or "").strip()
        if not want:
            continue
        best: tuple[float, dict[str, Any]] | None = None
        for supply in supplies:
            if supply.get("skillName") != want:
                continue
            if supply.get("state") != STAGE_PUBLISHED:
                continue          # 没发布的不参与匹配
            if supply.get("willingness") == WILL_NONE:
                continue

            score, reasons = 0.0, []
            score += 60
            if supply["willingness"] == WILL_PUBLIC:
                score += 20
                reasons.append("愿意公开教")
            else:
                score += 8
                reasons.append("只愿意教熟人，需要先认识")

            slots = int(supply.get("weeklySlots") or 1)
            score += min(slots, 5) * 3
            reasons.append(f"一周能安排 {slots} 个时段")

            supply_region = supply.get("region")
            demand_region = demand.get("region")
            if supply_region and demand_region and supply_region == demand_region:
                score += 10
                reasons.append(f"同在{supply_region}")

            if best is None or score > best[0]:
                best = (score, {**supply, "_score": round(score, 1), "_reasons": reasons})

        if best:
            score, pick = best
            results.append({
                "demandId": demand.get("demandId") or "",
                "demandSkill": want,
                "supplySkillId": pick["skillId"],
                "supplyUserId": pick.get("userId"),
                "score": score,
                "reasons": pick["_reasons"],
                # 只是推荐；确认要由需求方和平台完成
                "confirmed": False,
            })

    results.sort(key=lambda x: (-x["score"], x["supplySkillId"]))
    return results[:limit]


def to_skill_card(record: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """技能登记 / 匹配结果做成 v3 Result 卡片。"""
    base = now or datetime.now(timezone.utc)
    seed = f"{record.get('skillId')}|{record.get('state')}"
    digest = hashlib.sha1(seed.encode()).hexdigest()[:12]
    action = next_action(record)

    return {
        "resultId": f"ability-skill-{digest}",
        "type": "ability.skill_registration",
        "schemaVersion": "1.0",
        "title": f"技能登记：{record.get('skillName')}（{action['stageLabel']}）",
        "businessRef": None,
        "availability": "DEMO",
        "generatedAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [{"type": "USER_MESSAGE", "id": "",
                     "note": "由老人本人口述整理，未经社区核实"}],
        "pendingChecks": [
            "技能真实性由社区或平台审核，A3 不代替审核通过",
            "实际服务时长以打卡记录为准，A3 不计算、不增加时长",
            "匹配结果只是推荐，不承诺一定有人报名",
        ],
        "payload": {
            "skill": {
                "skillId": record["skillId"],
                "skillName": record["skillName"],
                "category": record["category"],
                "willingness": record["willingness"],
                "willingnessLabel": record["willingnessLabel"],
                "weeklySlots": record["weeklySlots"],
                "note": record["note"],
                "state": record["state"],
            },
            "nextAction": action,
        },
    }


def to_match_card(matches: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    base = now or datetime.now(timezone.utc)
    seed = "|".join(m["supplySkillId"] + m["demandId"] for m in matches) or "none"
    digest = hashlib.sha1(seed.encode()).hexdigest()[:12]

    return {
        "resultId": f"ability-match-{digest}",
        "type": "ability.supply_demand_match",
        "schemaVersion": "1.0",
        "title": "可以对接的技能" if matches else "暂时没有可对上的技能",
        "businessRef": None,
        "availability": "DEMO",
        "generatedAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [{"type": "ABILITY_BANK", "id": "demo", "note": "演示数据"}],
        "pendingChecks": [
            "只是推荐配对，需要双方都同意才算成",
            "不承诺自动有人接单",
        ],
        "payload": {
            "totalCandidates": len(matches),
            "matches": matches,
            "autoAssigned": False,
        },
    }


def build_reply_text(record: dict[str, Any] | None, matches: list[dict[str, Any]] | None = None) -> str:
    """说给老人听的话。"""
    if record is None:
        return "您说的这个我记下了。不过具体会什么，您能再说得细一点吗？"
    action = next_action(record)
    if record["state"] == STAGE_SUBMITTED:
        return (f"您会{record['skillName']}，这个记下来了。"
                f"我先帮您报给社区，等他们核实过就能挂出去。")
    if record["state"] == STAGE_PUBLISHED and matches:
        return (f"您会{record['skillName']}这事已经挂出去了，"
                f"现在有 {len(matches)} 位想学的，要不要帮您联系一下？")
    return f"您会{record['skillName']}，{action['stageLabel']}，{action['todo']}。"


# ---------------------------------------------------------------- 自测
def _selftest() -> int:
    now = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)

    print("=" * 68)
    print(" 1) 老人说「我会剪纸，愿意教大家，一周能安排两次」")
    print("=" * 68)
    parsed = parse_skill("我会剪纸，愿意教大家，一周能安排两次")
    print(f"  识别：{parsed}")
    rec = build_skill_record("u100", parsed, now=now)
    print(f"  登记状态：{rec['state']}（注意不是 PUBLISHED）")
    print(f"  下一步：{next_action(rec)}")
    print(f"  话术：{build_reply_text(rec)}")

    print()
    print("=" * 68)
    print(" 2) 只说会什么，没说愿不愿意教 → 取最保守那档")
    print("=" * 68)
    p2 = parse_skill("我以前是做裁缝的")
    print(f"  {p2}")
    print(f"  → 意愿：{WILLINGNESS_LABEL[p2['willingness']]}（等老人明确再说）")

    print()
    print("=" * 68)
    print(" 3) 认不出技能 → 不生成登记")
    print("=" * 68)
    print(f"  「我喜欢听戏」→ {parse_skill('我喜欢听戏')}")
    print(f"  「今天天气不错」→ {parse_skill('今天天气不错')}")
    print("  说明：宁可让 A1 再问一句，也不能生成一条老人没说过的技能")

    print()
    print("=" * 68)
    print(" 4) 供需匹配（需求侧归 A2，这里只做配对推荐）")
    print("=" * 68)
    supplies = [
        dict(rec, state=STAGE_PUBLISHED, region="广东"),
        {"skillId": "skill-x", "userId": "u200", "skillName": "剪纸", "category": "纸艺",
         "willingness": WILL_ACQUAINTANCE, "willingnessLabel": "只愿意教熟人",
         "weeklySlots": 1, "note": "", "state": STAGE_PUBLISHED, "region": "广东"},
        {"skillId": "skill-y", "userId": "u300", "skillName": "剪纸", "category": "纸艺",
         "willingness": WILL_PUBLIC, "willingnessLabel": "愿意公开教",
         "weeklySlots": 2, "note": "", "state": STAGE_REVIEWING, "region": "广东"},
    ]
    demands = [{"demandId": "d-1", "skillName": "剪纸", "region": "广东"}]
    ms = match_supply_demand(supplies, demands)
    for m in ms:
        print(f"  需求 {m['demandSkill']} → {m['supplySkillId']}  分数={m['score']}")
        print(f"    理由：{m['reasons']}")
        print(f"    已确认：{m['confirmed']}（只是推荐）")
    print("  说明：skill-y 状态是 REVIEWING 未发布，不参与匹配")

    print()
    print("=" * 68)
    print(" 5) 卡片过一遍结构")
    print("=" * 68)
    card = to_skill_card(rec, now=now)
    print(f"  {card['title']}")
    print(f"  availability={card['availability']}  businessRef={card['businessRef']}")
    print(f"  待核实 {len(card['pendingChecks'])} 条：{card['pendingChecks'][0][:30]}…")

    print()
    print("结论：能登记、能解释流程、能配对，但**不能自己审核通过、不能加时长**。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
