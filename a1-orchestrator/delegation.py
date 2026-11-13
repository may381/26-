"""委派链的第一步：登记步骤（P2 → steps）。

为什么不一口气写到 delegation：
    DelegationRequest 需要 `actionId`，而 actionId 只能由 P2 在
    `POST /internal/agent/v3/actions` 之后返回；而 actions 又依赖 stepId。
    所以真实链路是「登记步骤 → 准备动作 → 委派」，中间两个 ID 必须由 P2 给。
    在没拿到《Agent内部接口文档》前，本模块只做**能确证的第一步**，
    并且工具名必须由配置给出（A1_DELEGATE_TOOL）——不猜。

schema 依据（agent-v3-r3/control.schema.json）：
    StepRegisterRequest.steps.items: {clientStepKey, tool, args}，三者必填，
    additionalProperties=false，1–20 条。
"""
import os

from p2_client import P2Client, P2Error

TOOL_ENV = "A1_DELEGATE_TOOL"


def register_delegation_step(p2: P2Client, *, task_id, plan_version, request_key,
                             tool=None, args=None, client_step_key="s1"):
    """登记一条"要委派给 A2/A3"的步骤；返回 P2 的信封 data。

    任何前置条件不满足时抛 P2Error，且**不发送任何请求**。
    """
    tool = tool or os.environ.get(TOOL_ENV)
    if not isinstance(tool, str) or not tool.strip():
        raise P2Error(
            "未配置委派工具名（环境变量 %s），未向 P2 发送任何请求；"
            "该名称需由 P2 在内部接口文档中给出，不能猜" % TOOL_ENV
        )
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise P2Error("args 无效：需为对象（可为空对象）")
    steps = [{
        "clientStepKey": client_step_key,
        "tool": tool.strip(),
        "args": args,
    }]
    # 先用与 schema 相同的规则自检，避免把明显不合法的报文发出去。
    for step in steps:
        if set(step) != {"clientStepKey", "tool", "args"}:
            raise P2Error("步骤字段必须正好是 clientStepKey / tool / args")
        for key in ("clientStepKey", "tool"):
            if not 0 < len(step[key]) <= 128:
                raise P2Error("%s 长度必须在 1–128 之间" % key)
    return p2.register_steps(task_id, request_key, plan_version, steps)
