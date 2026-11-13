"""把**编译后**的 LangGraph 图导出成 Mermaid，供文档替换手画的那张。

为什么要有这个：手画的图和代码会漂移；`get_graph()` 拿到的是编译产物，
节点漏连、条件边写错，导出的图立刻就能看出来。

用法：
    cd a1-orchestrator
    python -X utf8 export_graph.py
输出：
    控制台：拓扑摘要
    文件：  ../交付文档/图示/graph_actual.mmd     ← 原始导出，与代码逐字对应
            ../交付文档/图示/graph_labeled.mmd    ← 同一张图，加中文标签，便于讲解
"""
from pathlib import Path

from domain_chat import DomainChat
from graph_runtime import mermaid, topology

OUT_DIR = Path(__file__).resolve().parent.parent / "交付文档" / "图示"

# 讲解用标签：只影响显示，不改变图的结构。
LABELS = {
    "control": "control\n入口与命令",
    "request": "request\n预检/图片/overview",
    "planning": "planning\n学校模型规划",
    "validation": "validation\n校验+白名单",
    "tourism": "tourism\n委派 8091",
    "fraud": "fraud\n委派 8000",
    "status": "status\n查反诈任务",
    "retry": "retry\n原键重试",
    "new": "new\n清本地",
    "reset": "reset\n清本地",
}


def labeled_mermaid(app):
    """用编译产物的**全部边**重建一张带中文标签的同构图（不手工增删边）。"""
    drawing = app.get_graph()
    nodes = sorted(n for n in drawing.nodes if not n.startswith("__"))
    lines = ["graph TD"]
    for node in nodes:
        lines.append('  %s["%s"]' % (node, LABELS.get(node, node).replace("\n", "<br/>")))
    for edge in drawing.edges:
        source, target = edge.source, edge.target
        if source == "__start__":
            continue
        if target == "__end__":
            lines.append("  %s --> END_%s([结束])" % (source, source))
        else:
            lines.append("  %s --> %s" % (source, target))
    return "\n".join(lines) + "\n"


def main():
    app = DomainChat().graph
    nodes, branches = topology(app)
    visible = sorted(n for n in nodes if not n.startswith("__"))

    print("节点（%d 个）：%s" % (len(visible), "、".join(visible)))
    for source, targets in sorted(branches.items()):
        print("  分叉 %-10s → %s" % (source, "、".join(sorted(t for t in targets if not t.startswith("__")))))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = mermaid(app)
    (OUT_DIR / "graph_actual.mmd").write_text(raw, encoding="utf-8")
    (OUT_DIR / "graph_labeled.mmd").write_text(labeled_mermaid(app), encoding="utf-8")
    print("\n已写入：graph_actual.mmd（%d 行）、graph_labeled.mmd" % len(raw.splitlines()))
    print("渲染：python -X utf8 render_graph_image.py graph_labeled")


if __name__ == "__main__":
    main()
