# -*- coding: utf-8 -*-
"""
guardrails.py —— A2 安全护栏（竞赛级：防提示词注入 + 输出合规）
============================================================
- 输入护栏 scan_input：检测提示词注入 / 越狱 / 提示词提取，命中则交由 decide_refusal 品牌化拒答。
- 输出护栏 scan_output：PII 脱敏、内部 token 防泄露、医疗处方拦截、超长截断。
- 全部规则法实现，零额外 LLM 调用（不增加成本、不引入循环依赖）。

设计原则：护栏是「兜底保险」，不依赖大模型自觉；即便 LLM 被绕过，输出侧仍会脱敏/拦截。
"""
import re
from dataclasses import dataclass
from typing import Optional

# 注入/越狱特征（小写子串匹配，刻意选「明确」的指令性表达以减少误伤）
_INJECTION_PATTERNS = [
    "忽略以上", "忽略前面", "忽略上述", "无视以上", "无视前面",
    "忘记前面", "忘记以上", "不理前面的指令",
    "你的系统提示", "你的提示词", "系统提示词", "system prompt", "systemprompt",
    "假装你是", "角色扮演", "扮演", "roleplay", "role play",
    "把你的提示", "输出你的提示", "泄露你的", "告诉我你的指令", "把上面的指令", "复制你的",
    "ignore previous", "ignore above", "disregard", "you are now",
    "pretend you are", "pretend you", "reveal your prompt", "output your prompt",
    "jailbreak", "越狱",
]

# 输出侧：隐私与内部信息
_PHONE_RE = re.compile(r"1[3-9]\d{9}")
_IDCARD_RE = re.compile(r"\d{17}[\dXx]")
_INTERNAL_TOKENS = ["capabilityToken", "invocationId=", "X-Agent-Key", "X-Trace-Id", "AGENT_A2_API_KEY", "system_prompt"]
_MEDICAL_RE = re.compile(r"\d+\s*(?:mg|毫克|毫升|ml|g|克|片|粒|单位)", re.I)

# 适老回复长度上限（品牌规则：≤60；超过 120 视为必须截断的硬违规）
_MAX_LEN_WARN = 60
_MAX_LEN_HARD = 120

# 权限护栏：疑似用户标识（用于跨用户数据防泄露的兜底隔离）
_USER_ID_RE = re.compile(r"\bu[0-9a-zA-Z]{3,}\b")


@dataclass
class InputScan:
    flagged: bool
    reason: str = ""


@dataclass
class OutputScan:
    flagged: bool
    reason: str
    sanitized: str


def scan_input(text: str) -> InputScan:
    if not text:
        return InputScan(False)
    low = text.lower()
    for p in _INJECTION_PATTERNS:
        if p in low:
            return InputScan(True, "检测到提示词注入/越狱特征: %s" % p)
    return InputScan(False)


def scan_output(text: str, user_text: str = "") -> OutputScan:
    if not text:
        return OutputScan(False, "", text)

    issues = []
    out = text

    # 1) PII 脱敏（手机号 / 身份证）——严禁在回复中回显他人隐私
    if _PHONE_RE.search(out):
        out = _PHONE_RE.sub("***", out)
        issues.append("手机号脱敏")
    if _IDCARD_RE.search(out):
        out = _IDCARD_RE.sub("***", out)
        issues.append("身份证脱敏")

    # 2) 内部 token 防泄露
    for tok in _INTERNAL_TOKENS:
        if tok in out:
            out = out.replace(tok, "***")
            issues.append("内部凭证泄露拦截")

    # 3) 医疗处方拦截（模型不应给出具体剂量）
    if _MEDICAL_RE.search(out):
        out = "为了用药安全，请遵医嘱或联系景区医疗点，我无法给出具体用药剂量。"
        issues.append("医疗处方拦截")

    # 4) 超长截断（适老语音播报不宜过长）
    if len(out) > _MAX_LEN_HARD:
        out = out[:_MAX_LEN_HARD] + "…"
        issues.append("超长截断")
    elif len(out) > _MAX_LEN_WARN:
        issues.append("超长提醒(未截断)")  # 仅提醒，不阻断

    flagged = bool([i for i in issues if i not in ("超长提醒(未截断)",)])
    return OutputScan(flagged, "; ".join(issues), out)


def decide_refusal(scan: InputScan) -> str:
    """输入命中注入护栏时的品牌化安全拒答（仍贴合适老关怀语气）。"""
    return "抱歉，这个要求我没法照做，但我很乐意帮您在景区里解决实际的困难，您想查路线、找休息区还是联系工作人员呢？"


def check_scope(reply_text: str, expected_user_id: Optional[str] = None) -> OutputScan:
    """⑤ A2 侧权限护栏：基于已知 caller 的 userId，防止回复泄漏「非本用户」的数据标识。

    说明（诚实边界）：完整的「角色级 RBAC」（如家属不能查看他人老人的实时位置/健康）
    需要 P2 在派发体（WireMessage）中携带 role/actor 字段。当前 WireMessage 仅含 userId，
    不含 role，因此 A2 侧只能做 userId 级的跨用户数据隔离兜底，角色级隔离需 P2 配合。
    """
    if not reply_text or not expected_user_id:
        return OutputScan(False, "", reply_text)
    out = reply_text
    issues = []
    for m in _USER_ID_RE.findall(out):
        if m != expected_user_id and not m.startswith(expected_user_id):
            out = out.replace(m, "***")
            issues.append("跨用户数据标识脱敏")
    flagged = bool(issues)
    return OutputScan(flagged, "; ".join(issues), out)
