"""LangGraph router for P2 v3 invocation reasons.

The graph owns callback routing only.  Protocol validation and side effects stay
in ``v3_adapter`` so a route change cannot replay a P2 action implicitly.
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


REASONS = (
    "USER_MESSAGE",
    "INPUT_PROVIDED",
    "CHILDREN_FINISHED",
    "CHILD_INPUT_REQUIRED",
    "CHILD_CONFIRMATION_REQUIRED",
    "CONFIRMATION_DECIDED",
    "RECOVERY",
)


class ReasonState(TypedDict, total=False):
    reason: str
    branch: str


def build_reason_graph():
    graph = StateGraph(ReasonState)

    def choose(state):
        return {"branch": state["reason"]}

    graph.add_node("choose", choose)
    for reason in REASONS:
        graph.add_node(reason.lower(), lambda state, value=reason: {"branch": value})

    graph.add_edge(START, "choose")
    graph.add_conditional_edges(
        "choose", lambda state: state["branch"],
        {reason: reason.lower() for reason in REASONS},
    )
    for reason in REASONS:
        graph.add_edge(reason.lower(), END)
    return graph.compile()


REASON_GRAPH = build_reason_graph()


def route_reason(reason):
    if reason not in REASONS:
        raise ValueError("unsupported v3 reason")
    return REASON_GRAPH.invoke({"reason": reason})["branch"]

