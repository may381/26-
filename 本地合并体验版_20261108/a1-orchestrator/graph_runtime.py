"""A1 的每轮 LangGraph：显式节点 + 显式 action 路由。

设计约定（读代码前先看这四条）
1. **路由只看一个通道**：`action`。节点负责把"下一步是谁"写进 action，
   边只读 action，不再用"state 里有没有 packet"这种隐式判断。
2. **节点返回增量**：每个节点只返回它更新的通道，不读写别人的内部字段。
3. **副作用只在 owner 里**：模型调用、领域调用、状态机、证据都归 DomainChat；
   图只负责决定顺序，不重放、不缓存、不让模型选工具。
4. **不存检查点**：每轮新建 state。会话证据由 DomainChat 持有，
   恢复语义要等 P2 的任务归属与去重规则确定后再加。

节点与 action 对照：
    control    → done / request / status / retry / new / reset
    request    → done / plan
    planning   → （无条件进入 validation）
    validation → done / tourism / fraud
    tourism    → 结束
    fraud      → 结束
"""
from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END

# 结束标记：所有"这一轮到此为止"的节点都写它。
DONE = "done"

# 一轮对话的通道集合。total=False 表示每个节点只写自己负责的那几个。
class TurnState(TypedDict, total=False):
    text: Any          # 本轮用户原文（已 strip）
    plan: dict         # 模型产出的计划（已过 validate_plan + enforce_location）
    domain: str        # 决定委派的领域：tourism / fraud
    source: str        # 交给领域的原文（用户原话累积，不是模型改写）
    packet: dict       # 对外返回体
    action: str        # 路由唯一依据


def _finish(packet):
    """统一的"这一轮结束"返回：带 packet，并把 action 置为 done。"""
    return {"packet": packet, "action": DONE}


def build_graph(owner):
    """owner 是 DomainChat；图只调它公开的 _ 方法，不碰它的状态字段。"""

    def control(state):
        text = state.get("text")
        if not isinstance(text, str) or not text.strip():
            return _finish(owner.packet("请输入具体需求；空内容没有提交给学校模型。", executed=False))
        text = text.strip()
        action = {
            "/status": "status",
            "/retry": "retry",
            "/new": "new",
            "/reset": "reset",
        }.get(text, "request")
        return {"text": text, "action": action}

    def request(state):
        # 图片、/overview、未知命令、等待中拦截、超长，都在 _prepare 里判定。
        result = owner._prepare(state["text"])
        if result is not None:
            return _finish(result)
        return {"action": "plan"}

    def planning(state):
        # 模型在这里被调用；失败由 _planning 抛 PlanningError，交给 send 兜底。
        return {"plan": owner._planning(state["text"]), "action": "planned"}

    def validation(state):
        result = owner._validation(state["text"], state["plan"])
        # _validation 有两个返回形状：
        #   {"domain","source"} → 允许委派，继续往下走
        #   其他 → 它本身就是 packet（ASK/REPLY/拒绝/超长），本轮到此结束
        if "domain" in result and "source" in result:
            return {
                "domain": result["domain"],
                "source": result["source"],
                "action": result["domain"],
            }
        return _finish(result)

    def tourism(state):
        return _finish(owner._dispatch("tourism", state["source"]))

    def fraud(state):
        return _finish(owner._dispatch("fraud", state["source"]))

    graph = StateGraph(TurnState)
    graph.add_node("control", control)
    graph.add_node("request", request)
    graph.add_node("status", lambda state: _finish(owner._status()))
    graph.add_node("retry", lambda state: _finish(owner._retry()))
    graph.add_node("new", lambda state: _finish(owner._reset()))
    graph.add_node("reset", lambda state: _finish(owner._reset()))
    graph.add_node("planning", planning)
    graph.add_node("validation", validation)
    graph.add_node("tourism", tourism)
    graph.add_node("fraud", fraud)

    graph.add_edge(START, "control")
    graph.add_conditional_edges(
        "control",
        lambda state: state["action"],
        {
            DONE: END,
            "request": "request",
            "status": "status",
            "retry": "retry",
            "new": "new",
            "reset": "reset",
        },
    )
    for command in ("status", "retry", "new", "reset"):
        graph.add_edge(command, END)

    graph.add_conditional_edges(
        "request", lambda state: state["action"], {DONE: END, "plan": "planning"}
    )
    graph.add_edge("planning", "validation")
    graph.add_conditional_edges(
        "validation",
        lambda state: state["action"],
        {DONE: END, "tourism": "tourism", "fraud": "fraud"},
    )
    graph.add_edge("tourism", END)
    graph.add_edge("fraud", END)

    return graph.compile()


# ---- 可验证性：让图和文档能互相校对，而不是靠手画 ----

NODE_NAMES = (
    "control",
    "request",
    "status",
    "retry",
    "new",
    "reset",
    "planning",
    "validation",
    "tourism",
    "fraud",
)

# 每个分叉节点允许跳到的**目标节点**（不含 END；END 只表示"这一轮结束"）。
# 对应的 action 取值见模块开头注释。
ROUTES = {
    "control": ("request", "status", "retry", "new", "reset"),
    "request": ("planning",),
    "validation": ("tourism", "fraud"),
}


def mermaid(app) -> str:
    """把**编译产物**导出成 Mermaid；文档里的图应以此为准。"""
    return app.get_graph().draw_mermaid()


def topology(app):
    """返回 (节点集合, 分叉映射)，供测试锁定图形状。"""
    drawing = app.get_graph()
    nodes = set(drawing.nodes)
    branches = {}
    for edge in drawing.edges:
        if getattr(edge, "conditional", False):
            branches.setdefault(edge.source, set()).add(edge.target)
    return nodes, branches
