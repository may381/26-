"""把 .mmd 渲染成 PNG（Edge 无头 + mermaid CDN）。

用法：
    python -X utf8 render_graph_image.py            # 默认渲染 graph_actual
    python -X utf8 render_graph_image.py graph_labeled
只用于生成答辩用的图；不参与运行时，也不影响测试。
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT_DIR = BASE / "交付文档" / "图示"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

TEMPLATE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<style>
  body {{ margin:0; background:#ffffff; font-family:"Microsoft YaHei",sans-serif; padding:24px 28px; }}
  .cap {{ font-size:15px; color:#33506b; margin:0 0 12px; }}
  .cap small {{ color:#7b8a99; font-weight:400; margin-left:10px; }}
  #out svg {{ max-width:100%; height:auto; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
</head><body>
<p class="cap">{title}<small>{subtitle}</small></p>
<div id="out"><pre class="mermaid">{graph}</pre></div>
<script>
  mermaid.initialize({{ startOnLoad: true, theme: "base",
    flowchart: {{ curve: "linear", nodeSpacing: 45, rankSpacing: 60 }},
    themeVariables: {{ fontFamily: "Microsoft YaHei", fontSize: "14px",
      primaryColor: "#eaf2f8", primaryBorderColor: "#8fb8d6",
      primaryTextColor: "#1f2933", lineColor: "#9aa7b4" }} }});
</script>
</body></html>
"""


def render(name="graph_actual", width=1500, height=900, title=None, subtitle=None):
    mmd = OUT_DIR / (name + ".mmd")
    if not mmd.exists():
        raise SystemExit("找不到 %s，先运行 export_graph.py" % mmd)
    html = OUT_DIR / ("_render_%s.html" % name)
    png = OUT_DIR / (name + ".png")
    html.write_text(TEMPLATE.format(
        graph=mmd.read_text(encoding="utf-8"),
        title=title or "A1 智能体：编译后的 LangGraph 状态图",
        subtitle=subtitle or "由 graph.get_graph() 自动导出，与代码一致（不是手画）",
    ), encoding="utf-8")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2", "--window-size=%d,%d" % (width, height),
                    "--virtual-time-budget=9000", "--screenshot=%s" % png, html.as_uri()],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not png.exists():
        raise SystemExit("没生成图片；可把 .mmd 贴到 https://mermaid.live 手动画出")
    print("OK  %s  (%d KB)" % (png, png.stat().st_size // 1024))


if __name__ == "__main__":
    render(sys.argv[1] if len(sys.argv) > 1 else "graph_actual")
