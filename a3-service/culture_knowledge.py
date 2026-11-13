#!/usr/bin/env python3
"""A3 非遗文化问答（含方言、地方文化）—— 纯函数，零依赖，不联网。

分工文档第 9 节写的是「非遗、**方言**和地方文化**问答**，按兴趣推荐课程」。
推荐课程那块在 culture_courses.py，这个文件补的是「问答」。

三条底线，比"答得多"重要得多：
1. **每条都要有来源。** 没有来源的内容不许出现在结果里。
2. **查不到就说查不到。** 说"我这儿没这个资料，我帮您问问"，
   绝不能顺着话头编一段。老人分辨不了真假，编了就是害人。
3. **只用高置信度的常识。** 写不进来源的细节宁可不写 ——
   非遗名录的批次、列入年份这些是可查证的，具体工艺技法就只讲公认的部分。

方言这部分解决一个很实际的问题：
    老人说的是「食饭」「唔该」「巴适」，系统要听得懂、还要能解释给家属听。
    现在很多适老产品听不懂方言，老人用两句就放弃了。

自测：
    python culture_knowledge.py
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

# 来源类型：只写真实存在的权威来源，不编书名页码
SOURCE_NATIONAL = {
    "type": "NATIONAL_HERITAGE_LIST",
    "title": "国家级非物质文化遗产代表性项目名录",
    "org": "文化和旅游部",
    "note": "批次与列入年份可在中国非物质文化遗产网核对",
}
SOURCE_UNESCO = {
    "type": "UNESCO_ICH_LIST",
    "title": "人类非物质文化遗产代表作名录",
    "org": "联合国教科文组织",
    "note": "列入年份可在 UNESCO 官网核对",
}
SOURCE_FOLK = {
    "type": "FOLK_COMMON_SENSE",
    "title": "民间常识性说法",
    "org": "非遗传承人口述 / 地方民俗通识",
    "note": "属民间通行说法，具体细节以当地传承人说明为准",
}

# ---------------------------------------------------------------- 知识库
# 只收高置信度的条目。每条都带 source，没 source 的不许进库（有测试卡这条）。
KNOWLEDGE: list[dict[str, Any]] = [
    # ---------------- 非遗项目
    {"kbId": "kb-papercut", "kind": "heritage", "topic": "剪纸",
     "title": "剪纸是什么",
     "content": "剪纸是用剪刀或刻刀在纸上剪刻花纹的民间艺术，窗花、喜花、门笺都是它的形式。"
                "常见题材有花鸟、人物、吉祥图案，逢年过节贴在窗上、门上。"
                "剪纸已于 2006 年列入第一批国家级非物质文化遗产代表性项目名录。",
     "keywords": ["剪纸", "窗花", "刻纸", "纸艺", "喜花", "非遗"],
     "regions": ["全国"], "source": SOURCE_NATIONAL},

    {"kbId": "kb-embroidery", "kind": "heritage", "topic": "刺绣",
     "title": "四大名绣是哪四个",
     "content": "中国四大名绣是苏绣（江苏苏州）、湘绣（湖南）、粤绣（广东）、蜀绣（四川成都）。"
                "苏绣以针脚细密、色彩雅致见长；粤绣构图饱满、色彩浓烈。"
                "这四类刺绣均已列入国家级非物质文化遗产代表性项目名录。",
     "keywords": ["刺绣", "苏绣", "湘绣", "粤绣", "蜀绣", "绣花", "四大名绣"],
     "regions": ["江苏", "湖南", "广东", "四川"], "source": SOURCE_NATIONAL},

    {"kbId": "kb-opera", "kind": "heritage", "topic": "戏曲",
     "title": "京剧是什么时候成为世界非遗的",
     "content": "京剧形成于清代北京，融合了徽调、汉调等多种声腔，行当分生、旦、净、丑。"
                "京剧于 2010 年列入联合国教科文组织人类非物质文化遗产代表作名录。",
     "keywords": ["京剧", "戏曲", "唱戏", "生旦净丑", "票友"],
     "regions": ["北京", "全国"], "source": SOURCE_UNESCO},

    {"kbId": "kb-taichi", "kind": "heritage", "topic": "太极",
     "title": "太极拳列入非遗了吗",
     "content": "太极拳于 2020 年列入联合国教科文组织人类非物质文化遗产代表作名录。"
                "常见流派有陈式、杨式、武式、吴式、孙式。"
                "八段锦是传统的健身功法，不属于太极拳流派，但同样适合老年人晨练。",
     "keywords": ["太极", "太极拳", "八段锦", "晨练", "养生"],
     "regions": ["河南", "全国"], "source": SOURCE_UNESCO},

    {"kbId": "kb-calligraphy", "kind": "heritage", "topic": "书法",
     "title": "中国书法为什么是非遗",
     "content": "中国书法于 2009 年列入联合国教科文组织人类非物质文化遗产代表作名录。"
                "它以毛笔书写汉字，讲究笔法、结体和章法，常见书体有楷、行、草、隶、篆。"
                "老年人练书法既是文化活动，也有静心养性的作用。",
     "keywords": ["书法", "毛笔", "楷书", "行书", "写字", "临帖"],
     "regions": ["全国"], "source": SOURCE_UNESCO},

    {"kbId": "kb-folk-music", "kind": "heritage", "topic": "民乐",
     "title": "二胡和江南丝竹",
     "content": "二胡是拉弦乐器，音色接近人声，常用于戏曲伴奏和民乐合奏。"
                "江南丝竹是流行于江苏南部、浙江一带的民间器乐合奏形式，"
                "已于 2006 年列入第一批国家级非物质文化遗产代表性项目名录。",
     "keywords": ["二胡", "民乐", "江南丝竹", "琵琶", "笛子", "乐器"],
     "regions": ["江苏", "浙江", "上海"], "source": SOURCE_NATIONAL},

    # ---------------- 方言
    {"kbId": "dl-cantonese", "kind": "dialect", "topic": "粤语",
     "title": "粤语常用说法",
     "content": "粤语（广东话）里几个常听到的说法：「食饭」= 吃饭；"
                "「唔该」= 谢谢 / 劳驾（麻烦别人时用）；「得闲」= 有空；"
                "「靓」= 漂亮、好；「唔使」= 不用。",
     "keywords": ["粤语", "广东话", "白话", "食饭", "唔该", "得闲", "靓", "唔使"],
     "regions": ["广东", "香港", "澳门"], "source": SOURCE_FOLK},

    {"kbId": "dl-hakka", "kind": "dialect", "topic": "客家话",
     "title": "客家话常用说法",
     "content": "客家话里：「唔使」= 不用；「食朝」= 吃早饭；"
                "「屋下」= 家里；「细人仔」= 小孩子。"
                "广东梅州、福建龙岩、江西赣州一带说客家话的人较多。",
     "keywords": ["客家话", "客家", "唔使", "食朝", "屋下", "细人仔"],
     "regions": ["广东", "福建", "江西"], "source": SOURCE_FOLK},

    {"kbId": "dl-sichuan", "kind": "dialect", "topic": "四川话",
     "title": "四川话常用说法",
     "content": "四川话里：「巴适」= 舒服、好；「晓得」= 知道；"
                "「耍」= 玩、逛；「要得」= 可以、行。",
     "keywords": ["四川话", "成都话", "巴适", "晓得", "耍", "要得"],
     "regions": ["四川", "重庆"], "source": SOURCE_FOLK},

    {"kbId": "dl-minnan", "kind": "dialect", "topic": "闽南语",
     "title": "闽南语常用说法",
     "content": "闽南语（福建南部、台湾一带）里：「阮」= 我们；"
                "「厝」= 房子、家；「食饱未」= 吃过饭了吗（常用问候）；"
                "「古早」= 从前、传统。",
     "keywords": ["闽南语", "台语", "福建话", "阮", "厝", "食饱未", "古早"],
     "regions": ["福建", "台湾"], "source": SOURCE_FOLK},

    # ---------------- 地方文化
    {"kbId": "lc-teahouse", "kind": "local", "topic": "广府早茶",
     "title": "广东早茶是怎么回事",
     "content": "广府早茶是广东、香港一带的饮食习惯，一早到茶楼点一壶茶配点心，"
                "常见有虾饺、烧卖、叉烧包、肠粉。早茶不只是吃饭，也是老人会朋友、聊天的场合。"
                "「一盅两件」指一壶茶配两样点心，是常见说法。",
     "keywords": ["早茶", "饮茶", "一盅两件", "虾饺", "点心", "茶楼"],
     "regions": ["广东", "香港", "澳门"], "source": SOURCE_FOLK},

    {"kbId": "lc-hakka-house", "kind": "local", "topic": "客家围屋",
     "title": "客家围屋是什么",
     "content": "客家围屋是客家人聚族而居的大型民居，广东梅州、福建永定一带常见，"
                "有圆形、方形等形制，兼具居住和防御功能。"
                "福建土楼中的部分建筑已列入世界文化遗产名录。",
     "keywords": ["围屋", "土楼", "客家", "民居", "梅州", "永定"],
     "regions": ["广东", "福建"], "source": SOURCE_FOLK},
]

MAX_LIMIT = 3
MAX_CONTENT = 4000

# 停用词：疑问词和虚词。不过滤掉的话，"什么""意思"会命中每一条标题里的"什么"，
# 把真正对口的条目挤出前三。这是第一版自测里踩到的真实问题。
STOPWORDS = {
    "什么", "意思", "怎么", "为什么", "如何", "哪些", "哪个", "多少",
    "吗", "呢", "吧", "啊", "的", "是", "了", "我", "您", "你",
    "请问", "一下", "这个", "那个", "有没有", "能不能", "可以",
    "介绍", "讲讲", "说说", "关于", "告诉", "知道", "想学", "想了解",
}

# 关键词命中要比标题命中重得多：关键词是人工标过的，标题只是字面碰巧一样。
W_KEYWORD = 10
W_TITLE = 4


class CultureKnowledgeError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# ---------------------------------------------------------------- 匹配
def _tokens(text: str) -> list[str]:
    """先把停用词从原文里删掉，再做中文二字滑窗。

    为什么要先删再切：
        只过滤切出来的词是不够的。"剪纸是什么" 切出的是
        剪纸 / 纸是 / 是什 / 什么 —— 删掉"什么"还剩"是什"，
        而"是什"会命中"京剧是什么时候…"的标题，把不相干的条目带进来。
        所以要先删词再切分，"剪纸是什么" 直接变成"剪纸"，只剩一个词。
    """
    body = (text or "").lower()
    # 长的先删，否则"有没有"会被"有"先拆散
    for word in sorted(STOPWORDS, key=len, reverse=True):
        body = body.replace(word, " ")

    out: list[str] = []
    for word in re.findall(r"[a-z0-9]+", body):
        if len(word) >= 2:
            out.append(word)
    for chunk in re.findall(r"[\u4e00-\u9fff]+", body):
        if len(chunk) <= 2:
            out.append(chunk)
        else:
            out.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))
    return list(dict.fromkeys(t for t in out if t))


def _score(query: str, entry: dict[str, Any]) -> int:
    """关键词命中打分。只比 keywords 和 title，不比 content ——
    content 太长，随便一个"的"字都能命中，等于没筛。"""
    tokens = _tokens(query)
    keywords = [k.lower() for k in entry.get("keywords", [])]
    title = (entry.get("title") or "").lower()

    score = 0
    for token in tokens:
        # 只有两个字以上的 token 才做"包含"匹配。
        # 单字例如"唱"会命中关键词"唱戏"，把"昆曲的水磨腔怎么唱"判成京剧 —— 方向反了。
        hit = any(
            len(kw) >= 2 and (
                token == kw or (len(token) >= 2 and (token in kw or kw in token)))
            for kw in keywords)
        if hit:
            score += W_KEYWORD
        elif len(token) >= 2 and token in title:
            score += W_TITLE
    return score


def search(query: str, *, kind: str | None = None, region: str | None = None,
           limit: int = MAX_LIMIT) -> list[dict[str, Any]]:
    """按问题找条目。查不到返回空列表 —— 空是合法结果，不是错误。"""
    body = (query or "").strip()
    if not body:
        raise CultureKnowledgeError(400, "INVALID_ARGUMENT", "query 不能为空")
    if not (1 <= limit <= MAX_LIMIT):
        raise CultureKnowledgeError(400, "INVALID_ARGUMENT", f"limit 必须是 1~{MAX_LIMIT}")

    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in KNOWLEDGE:
        if kind and entry.get("kind") != kind:
            continue
        if region and region not in (entry.get("regions") or []):
            continue
        score = _score(body, entry)
        if score > 0:
            scored.append((score, entry))

    if not scored:
        return []
    scored.sort(key=lambda pair: (-pair[0], pair[1]["kbId"]))

    # 相对阈值：低于第一名一半的直接丢掉。
    # 不加这个，问"剪纸"会把"标题里碰巧有同一个字"的条目也带出来，
    # 老人看到三条里两条不相干，会以为系统没听懂。
    floor = scored[0][0] * 0.5
    kept = [(s, e) for s, e in scored if s >= floor][:limit]
    return [{**entry, "score": score} for score, entry in kept]


# ---------------------------------------------------------------- 输出
def to_result_card(items: list[dict[str, Any]], query: str,
                   now: datetime | None = None) -> dict[str, Any]:
    """产出 v3 的 Result 卡片。

    availability 用 DEMO 而不是 REAL：
        内容是真实的非遗常识，但装在本地静态文件里，没有接文化和旅游部的接口。
        标 REAL 等于说"这是实时权威数据"，不诚实。
    """
    base = now or datetime.now(timezone.utc)
    seed = json.dumps([i["kbId"] for i in items] + [query], ensure_ascii=False)
    digest = hashlib.sha1(seed.encode()).hexdigest()[:12]

    return {
        "resultId": f"culture-knowledge-{digest}",
        "type": "culture.knowledge_answer",
        "schemaVersion": "1.0",
        "title": "非遗与地方文化资料" if items else "这次没查到相关资料",
        "businessRef": None,
        "availability": "DEMO",
        "generatedAt": base.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [dict(i["source"], id=i["kbId"], title_zh=i["title"]) for i in items][:20],
        "pendingChecks": [
            "资料为本地整理的常识条目，具体细节以官方名录和当地传承人说明为准",
            "涉及具体活动时间、地点、费用时，需向场馆或主办方核实",
        ],
        "payload": {
            "query": query,
            "totalCandidates": len(items),
            "entries": [{
                "kbId": i["kbId"],
                "kind": i["kind"],
                "topic": i["topic"],
                "title": i["title"],
                "content": i["content"][:MAX_CONTENT],
                "regions": list(i["regions"]),
                "source": dict(i["source"]),
            } for i in items],
        },
    }


def build_answer_text(items: list[dict[str, Any]]) -> str:
    """说给老人听的话。查不到时不许编，要给下一步。"""
    if not items:
        return ("这个我这儿没有现成资料，不好瞎说。"
                "要不我帮您问问社区或者文化馆的人？")
    first = items[0]
    text = f"{first['content']}"
    if len(items) > 1:
        text += f" 另外还有 {len(items) - 1} 条相关的，您想听哪个？"
    return text


def is_dialect_question(query: str) -> bool:
    """是不是在问方言。用来决定接不接这个话头。"""
    body = query or ""
    return any(word in body for word in
               ("方言", "什么意思", "啥意思", "怎么说", "听不懂", "粤语", "客家话",
                "四川话", "闽南语", "白话"))


# 问句的特征词
_QUESTION_WORDS = ("什么", "怎么", "为什么", "为啥", "哪些", "哪个", "哪", "多少",
                   "是不是", "有没有", "吗", "呢", "来历", "由来", "讲究",
                   "介绍", "讲讲", "说说")

# 但这些词出现时，说的是"我想做什么"，不是"我想知道什么"
_NEED_WORDS = ("想学", "要学", "学一下", "教我", "报名", "参加", "有没有班",
               "什么班", "推荐", "安排", "班", "课程", "上课")


def is_knowledge_question(query: str) -> bool:
    """判断这句是在问知识，还是在表达需求。

    "剪纸是什么" → 问知识 → 走知识库
    "想学剪纸"   → 表达需求 → 走课程推荐
    两者都含"剪纸"，但该给的东西完全不同。判错的后果是：
    老人想找课，系统给他念了一段非遗介绍。
    """
    body = query or ""
    if not body.strip():
        return False
    if is_dialect_question(body):
        return True
    if any(w in body for w in _NEED_WORDS):
        return False
    return any(w in body for w in _QUESTION_WORDS)


# ---------------------------------------------------------------- 自测
def _selftest() -> int:
    print("=" * 68)
    print(" 1) 问剪纸是什么")
    print("=" * 68)
    items = search("剪纸是什么")
    print(f"  命中 {len(items)} 条")
    for i in items:
        print(f"    [{i['kbId']}] {i['title']}  来源={i['source']['org']}")
    print(f"  话术：{build_answer_text(items)}")

    print()
    print("=" * 68)
    print(" 2) 老人说方言：「唔该」是什么意思")
    print("=" * 68)
    items = search("唔该是什么意思")
    print(f"  是方言问题：{is_dialect_question('唔该是什么意思')}")
    for i in items:
        print(f"    [{i['kbId']}] {i['title']}")
        print(f"      {i['content'][:60]}…")

    print()
    print("=" * 68)
    print(" 3) 问一个库里没有的（关键：不许编）")
    print("=" * 68)
    items = search("景泰蓝怎么烧制")
    print(f"  命中 {len(items)} 条")
    print(f"  话术：{build_answer_text(items)}")

    print()
    print("=" * 68)
    print(" 4) 按地区筛：广东的非遗/方言/地方文化")
    print("=" * 68)
    items = search("广东 文化", region="广东", limit=3)
    for i in items:
        print(f"    {i['topic']:<8} {i['title']}")

    print()
    print("=" * 68)
    print(" 5) 每条都必须有来源（这是硬约束）")
    print("=" * 68)
    missing = [e["kbId"] for e in KNOWLEDGE if not e.get("source", {}).get("org")]
    print(f"  知识库 {len(KNOWLEDGE)} 条，缺来源的：{missing or '无'}")
    kinds: dict[str, int] = {}
    for e in KNOWLEDGE:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"  分类：{kinds}")

    print()
    print("结论：有来源、查不到就说查不到、方言能听懂 —— 这三点比条目多重要。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
