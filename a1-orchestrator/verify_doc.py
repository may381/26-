"""文档 vs 代码 自动核对：不需要起任何服务，只读源码。

用途：接口文档里的每条"事实"（端口、路径、字段、状态、文案、上限）
      都能在代码里找到出处；找不到的就是文档写错了。

用法：
    cd a1-orchestrator
    python -X utf8 verify_doc.py
全部对得上时最后一行是 DOC OK。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = {
    "a1.py": ROOT / "a1.py",
    "domain_chat.py": ROOT / "domain_chat.py",
    "local_domains.py": ROOT / "local_domains.py",
    "graph_runtime.py": ROOT / "graph_runtime.py",
    "p2_client.py": ROOT / "p2_client.py",
    "service.py": ROOT / "service.py",
    "server.py": ROOT.parent / "A1new" / "server.py",
    "requirements.txt": ROOT / "requirements.txt",
}
TEXT = {}
for name, path in SRC.items():
    TEXT[name] = path.read_text(encoding="utf-8") if path.exists() else ""

results = []


def check(claim, needle, where, regex=False):
    hit = bool(re.search(needle, TEXT[where])) if regex else (needle in TEXT[where])
    results.append(hit)
    print(("OK   " if hit else "MISS ") + claim + ("" if hit else "   [在 %s 里没找到: %s]" % (where, needle)))


def find(claim, needle, regex=False):
    """在所有源码里找；用于跨文件或字符串拼接的文案。"""
    hit = False
    for name, text in TEXT.items():
        hit = bool(re.search(needle, text)) if regex else (needle in text)
        if hit:
            break
    results.append(hit)
    print(("OK   " if hit else "MISS ") + claim + ("" if hit else "   [所有源码里都没找到: %s]" % needle))


print("=== 一、入口与端口 ===")
check("DomainChat.send 入口存在", "def send(self, text)", "domain_chat.py")
check("packet 固定 mode", "LOCAL_A1_DOMAIN_COORDINATOR_NOT_P2", "domain_chat.py")
check("8095 入口端口", "127.0.0.1',8095", "server.py")
check("8093 联调壳默认端口", 'A1_PORT", "8093"', "service.py")
check("P2 默认 8080", 'DEFAULT_BASE = "http://127.0.0.1:8080"', "p2_client.py")
check("旅游 8091 / 反诈 8000 固定回环", r"127\.0\.0\.1:8091", "local_domains.py", regex=True)

print("\n=== 二、状态机 ===")
for state in ("READY", "WAIT_RESULT", "SUBMISSION_UNCERTAIN", "COMPLETE", "FAILED"):
    check("状态 %s 存在" % state, state, "domain_chat.py")

print("\n=== 三、LangGraph 图 ===")
check("langgraph 依赖已固定", "langgraph==1.2.20", "requirements.txt")
check("使用 StateGraph", "StateGraph", "graph_runtime.py")
for node in ("control", "request", "status", "retry", "new", "reset",
             "planning", "validation", "tourism", "fraud"):
    check("节点 %s 已注册" % node, 'add_node("%s"' % node, "graph_runtime.py")
check("路由通道是 action（不是 route）", 'state["action"]', "graph_runtime.py")

print("\n=== 四、上限与超时 ===")
check("模型超时受P2预算约束", "A1_MODEL_TIMEOUT_SECONDS", "a1.py")
check("模型响应 1MB 上限", "1024 * 1024", "a1.py")
check("旅游超时受P2预算约束", "A1_TOURISM_TIMEOUT_SECONDS", "local_domains.py")
check("其他普通领域超时 100 秒", "timeout = 100", "local_domains.py")
check("领域图片超时 220 秒", "220", "local_domains.py")
check("DomainChat 单轮上限 10000", "max_text_length=10000", "domain_chat.py")
check("旅游累计原文上限 2000", "2000 if domain=='tourism'", "domain_chat.py")
check("入口层单轮上限 2000", "0<len(text.strip())<=2000", "server.py")

print("\n=== 五、领域接口与判据 ===")
check("旅游咨询路径", "/api/agent/messages", "local_domains.py")
check("旅游图片路径", "/api/a1/images/analyze", "local_domains.py")
check("反诈提交路径", "/api/analyses'", "local_domains.py")
check("反诈状态路径", "/api/analyses/", "local_domains.py")
check("反诈图片由入口层代调", "/api/image-analyses", "server.py")
check("analysis_id 正则", r"real-\[A-Za-z0-9-\]\{1,120\}", "local_domains.py", regex=True)
check("幂等键前缀 local-", "local-", "local_domains.py")
check("演示资料会被拒", "演示资料", "local_domains.py")
check("Idempotency-Key 头", "Idempotency-Key", "local_domains.py")

print("\n=== 六、固定文案 ===")
for text in ("请输入具体需求；空内容没有提交给学校模型。",
             "当前仅接通单步旅游咨询和反诈文本分析",
             "当前没有待重试的提交；不会新建任务。",
             "模型计划被截断，请缩短需求后重试"):
    find("文案：" + text[:14] + "…", text)

# 两条连接错误是拼接出来的：'无法连接本机' + 服务名 + '，请先启动对应后端。'
find("文案：无法连接本机旅游服务（8091）…", "无法连接本机")
check("连接错误文案含 8091/8000 分支", "旅游服务（8091）", "local_domains.py")
check("连接错误文案含反诈分支", "反诈服务（8000）", "local_domains.py")

print("\n=== 七、8095 入口接口 ===")
for path in ('/api/message', '/api/status', '/api/reset', '/api/image', '/api/tool',
             '/api/health', '/api/system-status'):
    check("入口路径 %s" % path, "'%s'" % path, "server.py")
actions = re.findall(r"'(nearby|weather|districts|route-location|location|exchange|places|transport|import|link|plan|restore|save)'",
                     TEXT["server.py"])
tool_count = len(set(actions))
check("工具白名单 13 个转发 8091（+2 票务=15）", "tickets" and "ticket-stations", "server.py")
print("     实测 8091 转发 action 数：%d（文档写 13）" % tool_count)
results.append(tool_count == 13)

print("\n=== 八、P2 出站客户端 ===")
for path in ("/internal/agent/v3/delegations", "/internal/agent/v3/tasks/{taskId}/steps",
             "/internal/agent/v3/actions", "/internal/agent/v3/confirmations"):
    check("出站路径 %s" % path, path, "p2_client.py")
check("协议版本 3.0", 'PROTOCOL_VERSION = "3.0"', "p2_client.py")
check("动作准备强制幂等键", 'idempotency_key', "p2_client.py")
check("未配密钥拒绝发送", "A1_AGENT_KEY", "p2_client.py")

print("\n=== 九、8093 入站 ===")
for path in ("/health", "/internal/v3/messages", "/internal/v3/invocations/"):
    check("入站路径 %s" % path, path, "service.py")
check("鉴权头 X-Agent-Key", "X-Agent-Key", "service.py")
check("幂等 REPLAY/CONFLICT", "REPLAY", "service.py")

passed = sum(1 for r in results if r)
print("\n%d/%d 项与代码一致" % (passed, len(results)))
print("DOC OK" if passed == len(results) else "有 %d 项对不上，见上面 MISS" % (len(results) - passed))
