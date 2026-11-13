"""支付前确认：在老人真的转钱之前，把"先停一下"摆到他面前。

定位
    - 这是**确定性规则**，不调模型、不联网、不代替反诈分析。
    - 它只做一件事：命中"要先付钱/要验证码/被施压"这类话术时，返回一张
      "暂停确认"卡的数据；没命中就返回 None，不打扰正常对话。
    - 永不输出概率、永不声称已拦截、永不执行任何资金动作。

边界
    - 不监控其他 App、来电和短信（系统权限做不到，也不该假装做到）。
    - 高风险时只给"官方渠道"和"问子女"，不替老人决定打不打电话。
"""
import re

# 每类只在"前面没有否定词"时才算命中，避免把"不用转账"判成风险。
PATTERNS = {
    "先付款": ("转账", "打款", "汇款", "付款", "保证金", "押金", "手续费", "解冻费", "充值", "扫码"),
    "索要敏感信息": ("验证码", "银行卡号", "密码", "身份证号", "人脸识别", "远程控制"),
    "施压话术": ("逾期", "否则", "冻结", "起诉", "拘留", "通缉", "马上", "最后机会"),
    "冒充身份": ("客服", "公检法", "公安局", "检察院", "安全账户", "税务局", "平台专员"),
}

NEGATIONS = ("不要", "不用", "不需要", "切勿", "别", "无需", "不收", "没有任何", "没有", "不会")

CHANNELS = (
    {"name": "96110 反诈专线", "note": "官方反诈号码，点一下拨号", "tel": "96110"},
    {"name": "银行官方客服", "note": "用卡片背面的号码，不要用对方给的", "tel": None},
    {"name": "家里人", "note": "把这页给子女或邻居看，请他们一起判断", "tel": None},
)

NOT_EXECUTED = (
    "未执行任何转账、支付或汇款",
    "未联系银行、家属或警方",
    "未冻结、未追回，也不承诺能追回",
)


def _hit(text, word):
    """命中判断：出现且前面 6 个字里没有否定词。"""
    start = text.find(word)
    if start < 0:
        return False
    window = text[max(0, start - 6):start]
    return not any(neg in window for neg in NEGATIONS)


def check(text):
    """返回待展示的"暂停确认"数据；不命中返回 None。"""
    if not isinstance(text, str) or not text.strip() or len(text) > 5000:
        return None
    body = text.strip()
    matched, groups = [], []
    for group, words in PATTERNS.items():
        hits = [w for w in words if _hit(body, w)]
        if hits:
            groups.append(group)
            matched.extend(hits)
    if not matched:
        return None

    risk = "high" if len(groups) >= 2 or "先付款" in groups else "medium"
    return {
        "triggered": True,
        "risk": risk,
        "groups": groups,
        "matched": sorted(set(matched)),
        "headline": "先停一下：这件事需要你先付钱或先给信息",
        "riskPoints": [
            "真实机构不会要求先交保证金、解冻费、手续费才办事。",
            "验证码、银行卡号、密码只要给出去，钱就不再由你控制。",
            "对方越强调\"马上\"\"否则\"，越说明它在催你做决定。",
        ],
        "pauseSteps": [
            "先不要转账，也不要点对方发来的链接或二维码。",
            "挂断后，用你自己找到的官方号码回拨核实；不要用对方给的号码。",
            "把这条消息原样发给子女或拨打 96110，请第三人一起看。",
        ],
        "channels": list(CHANNELS),
        "notExecuted": list(NOT_EXECUTED),
        "note": "这是辅助提醒，不是警方的认定；真正处理仍要找银行和公安。",
    }
