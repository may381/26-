# A2 领域智能体服务（v3 · 竞赛级实现）

A2 是「老人数字分身平台」的领域智能体之一，负责 **适老关怀（care）** 域的语义理解与回复生成。
本服务严格对齐《Agent 统一交互协议 v3.0》，由 P2 后端通过 HTTP 派活，返回协议模板 D 结果单。

> **与 demo 的区别（竞赛标准）**
> - ❌ 不使用标准库 `http.server` / `urllib` 手写 HTTP（教学演示级）。
> - ✅ 使用 **FastAPI + httpx 异步**：出站 LLM / P2 工具调用全部 `async/await`，**不阻塞事件循环**。
> - ✅ **共享异步连接池**（`httpx.AsyncClient`，连接复用 + 超时 + 异常细分）。
> - ✅ **结构化日志**（控制台 + 文件，统一格式），替代散落的 `print`。
> - ✅ **测试套件**（pytest）：模板 D 14 字段严格校验 + 服务集成测试（鉴权 / 回执往返 / 取消 / 404）。
> - ✅ **回执持久化**（sqlite，跨重启可找回，满足协议「超时恢复」硬要求）。
> - ✅ **企业级 8 模块补齐（A 阶段）**：品牌提示词 + 版本化、输入/输出安全护栏、缓存降本、模型路由、可观测指标、改提示词必测的测评 harness。详见文末「企业级 8 模块合规进度」。

## 目录结构

```
a2_service/
├── main.py            # FastAPI 入口：路由 / 鉴权 / 校验 / 统一信封 / /metrics 端点
├── http_client.py     # 共享异步 HTTP 客户端（连接池 + 超时）
├── llm_client.py      # 调统一大模型（校内 qwen，httpx 异步，主/备模型路由）
├── p2_client.py       # 调 P2 内部工具（knowledge.search 等，httpx 异步）
├── agent_logic.py     # 领域推理入口：仅做「护栏→分发→组装模板 D」，具体能力在 capabilities/
├── capabilities/      # 八大业务能力包（详见文末「八项业务能力合规进度」）
│   ├── router.py      # 能力路由：P2 下发 intent 或关键词自识别 → 8 个 handler
│   ├── base.py        # CapabilityResult 底座 + 转模板 D（14 字段）
│   ├── _core.py       # 共用管线：缓存→RAG→MCP→真实 LLM→输出护栏→跨用户隔离
│   ├── help_human.py  # c1 求助与人工（handoff 路由 + results 填实）
│   ├── reminder.py    # c2 健康提醒（规则解析 + 落库 + WAIT_CONFIRMATION）
│   ├── memory.py      # c3 记忆反馈（抽取 + 落库 + usedMemoryRefs）
│   └── placeholder.py # c4~c8 占位处理器（真实识别 + 结构化占位，诚实标注阶段）
├── demo_trigger.py    # 投屏演示控制台：4 基础设施 + 八项能力逐一触发（纯数据，不含提词）
├── schemas.py         # 协议模板 C/D 的 pydantic 模型与构造器
├── settings.py        # 配置层（环境变量 > .env > 默认），含日志配置
├── store.py           # sqlite 回执持久化（线程安全 + 幂等）
├── exceptions.py      # 统一错误码
├── guardrails.py      # ⑥ 安全护栏：输入注入检测 + 输出脱敏/拦截
├── cache.py           # ⑦ 回复缓存：TTL 命中，省重复 LLM 调用降本
├── metrics.py         # ⑧ 可观测性：请求/缓存/LLM/护栏/延迟等指标（线程安全）
├── prompts.py         # ② 提示词管理：SYSTEM_PROMPT_VERSION + 变更记录
├── prompts/           # system prompt 外部化（品牌规则，可改，不必动代码）
├── knowledge.py       # ③ 本地 RAG 检索（sklearn TF-IDF，零额外依赖）
├── knowledge_base/    # ③ 占位品牌/景区知识 .txt（**待替换为真实业务资料**）
├── mcp_client.py      # ④ MCP client（最小 JSON-RPC over stdio，零依赖）
├── servers/           # ④ 本地 mock 工单 MCP server（验证协议用，非真实后端）
├── docs/              # OpenAPI / 能力声明 / 测试用例 / 提示词
├── tests/             # pytest 单元 + 集成测试
│   ├── eval/          # ⑨ 测评 harness：cases.json + run_eval.py（改提示词必测）
│   ├── test_guardrails.py     # 护栏单测
│   └── test_eval_regression.py# 把「改提示词必测」接入 pytest
└── .env.example       # 配置样例
```

## 配置（.env.example）

| 变量 | 说明 | 默认 |
|---|---|---|
| `A2_API_KEY` / `AGENT_A2_API_KEY` | 与 P2 约定的身份密钥（≥16 位） | 从 P2 仓库借用 |
| `A2_HOST` / `A2_PORT` | 监听地址 / 端口 | `127.0.0.1:18002` |
| `P2_BASE_URL` | P2 内部回调基地址 | `http://127.0.0.1:8080` |
| `A2_LLM_BASE_URL` | 校内 qwen 地址 | `http://10.138.50.151:8000` |
| `A2_LLM_MODEL` | 主模型名 | `qwen3.8-27b` |
| `A2_LLM_MODEL_SECONDARY` | ⑦ 备用模型（主模型彻底失败后再切，留空不切换） | 空 |
| `A2_LLM_ENABLED` | 关闭则走规则兜底 | `true` |
| `A2_LLM_TIMEOUT` | 单次 LLM 调用超时（秒） | `20` |
| `A2_LLM_MAX_RETRIES` | 瞬时网络错误的重试次数（5xx 才重试，4xx 不重试） | `2` |
| `A2_LLM_RETRY_BACKOFF` | 重试间隔（秒） | `1.0` |
| `A2_CACHE_ENABLED` | ⑦ 回复缓存开关（降本） | `true` |
| `A2_CACHE_TTL` | 缓存有效期（秒） | `300` |
| `A2_DB_PATH` | 回执 sqlite 路径 | `a2_receipts.db` |
| `A2_LOG_LEVEL` / `A2_LOG_FILE` | 日志级别 / 文件 | `INFO` / `a2_service.log` |

## 运行

```bash
pip install fastapi uvicorn httpx pydantic
cd a2_service
cp .env.example .env   # 按需修改
python main.py
```

## 测试

```bash
pip install pytest
cd a2_service
python -m pytest -q
```

测试不依赖真实 LLM / P2：通过 `TestClient` 驱动，mock 外部依赖，覆盖
健康检查、结果单 14 字段严格校验、鉴权失败、回执往返与取消、缺失回执 404。

## 与 P2 协议对齐要点

- 入站 `POST /internal/v3/messages`：校验 `protocolVersion=3.0`、必填字段、身份头 `X-Agent-Key`。
- 出站结果单：恰好 **14 个顶层字段**，且原样回传 `taskId/baseTaskVersion/invocationId/
  conversationId/messageId`，否则 P2 `finish()` 拒收。
- `GET /internal/v3/invocations/{id}`：按 invocationId 找回执（超时恢复 / 取消用）。
- `POST /internal/v3/invocations/{id}/cancel`：取消某次派活。

## 端到端验证结论（竞赛就绪度）

- **意图路由已打通**：P2 在 `AgentTaskExecutor.claim()` 中对「根任务」按意图关键词路由——
  求助类（`求助/帮助/help/迷路/紧急/需要帮助` 等）→ **a2**；其余 → a1。实测用户从
  `/api/v3/agent/messages` 发的求助消息，invocation 的 `agentId` 确为 `a2`，任务最终 `SUCCEEDED`，
  回执为合法 14 字段模板 D。
- **真实 A2 服务**：A2(18002) 接收 P2 派活 → 调真实大模型（校内 qwen）→ 返回老人友好回复 +
  适老语速；模型不可用时**自动重试（默认 2 次，仅重试 5xx/网络错误）**并降级。
- **外部依赖说明**：统一大模型 `10.138.50.151:8000` 为学校内网服务，偶发不可达；届时 A2 会
  记录 `WARNING/ERROR` 日志并优雅降级为关怀话术，不会让调用方超时或崩溃。模型可用时已实测
  返回真实语义回复（如"景区设有电梯和无障碍通道…"）。
- **已知边界（非缺陷）**：A2 独立部署时，兜底路径调 P2 的 `knowledge.search` 需走动作账本
  （stepId/actionId）注册，当前未接，故该兜底分支返回 400 后直接走关怀话术；主路径（LLM）不受影响。

## 企业级 8 模块合规进度（对照"企业 AI 搭建"标准）

| # | 模块 | 本服务状态 | 实现位置 |
|---|---|---|---|
| ① | 基础大模型 | ✅ 已接真实 qwen（httpx 异步 + 重试） | `llm_client.py` |
| ② | 系统提示词 | ✅ **品牌化 + 版本化**（v1.0.0，附变更记录） | `prompts/system_prompt.txt` + `prompts.py` |
| ③ | RAG 知识库 | ✅ **A2 本地自建**（sklearn TF-IDF 检索，知识源在 A2 本地，不依赖 P2） | `knowledge.py` + `knowledge_base/` |
| ④ | MCP 工具调用 / 工单 | ✅ **A2 侧接入**（最小 MCP client 连本地 mock 工单 server；接真实工单只需改 server_cmd 指向 P2 的 MCP server） | `mcp_client.py` + `servers/ticket_server.py` |
| ⑤ | 角色权限管控 | ⚠️ **A2 侧部分完成**：输出护栏（PII/内部 token/医疗/跨用户脱敏）+ 基于 userId 隔离已做；**角色级 RBAC 隔离因 P2 派发体（WireMessage）未带 role 字段，A2 侧暂无法做，需 P2 配合** | `guardrails.py`(`check_scope`) |
| ⑥ | 安全护栏 | ✅ **已完成**（输入注入检测 + 输出脱敏/拦截/医疗拦截） | `guardrails.py` |
| ⑦ | 缓存 + 模型路由 | ✅ **已完成**（TTL 缓存降本 + 主/备模型路由） | `cache.py` + `llm_client.py` |
| ⑧ | 可观测性 | ✅ **已完成**（指标快照 + `/metrics` 端点 + 结构化留痕） | `metrics.py` + `main.py` |
| ⑨ | 改提示词必测 | ✅ **已完成**（测评 harness 接入 pytest，阻断回归） | `tests/eval/` + `tests/test_eval_regression.py` |

> **A2 自控范围（不碰 P2）已交付**：A 阶段 ②⑥⑦⑧⑨ + B 阶段 ③④⑤ 的 A2 侧部分（本地 RAG / MCP 接入 / 输出护栏与 userId 隔离）。
> **唯一未达标项**：角色级 RBAC（家属不能看他人老人数据）因 P2 派发体未携带 `role` 字段，A2 侧无法判断调用者角色，需 P2 在 `WireMessage` 增加 `role` 后由 A2 落地——此条非 A2 职责范围，已向负责人说明。

## 八项业务能力合规进度

A2 统一承载「适老关怀（care）」域的 **八项业务能力**。契约 4.1 规定第一阶段仅 `tourism`+`help` 真做，
其余意图「必须能被识别并返回统一的演示占位结果」——因此 c2~c8 实现为**真实识别意图 + 结构化占位
结果（诚实标注阶段2 骨架已就绪）**，不冒充十成落地。其中 c1 求助与人工为真实闭环（P2 全链路），
c2 健康提醒 / c3 记忆反馈按 2026-11-07 评审决议**回归占位口径**（与 c4~c8 一致），以严格满足
验收清单 C1/C3 工具白名单约束，不越界调用 `memory.write` 或落库。

| # | 能力（key） | 阶段 | 状态 | 结构化字段落地 | 实现位置 |
|---|---|---|---|---|---|
| c1 | 求助与人工（help_human） | 真做 | ✅ 真实落地 | `handoff`（家人→family / 现场→scenic 路由）、`results`（已通知/处理建议/匹配状态）填实；真实 LLM+RAG；可走 P2 全链路 | `help_human.py` + `_core.py` |
| c2 | 健康提醒（health_reminder） | 占位 | ⚠️ 阶段2 占位 | 真实识别意图 + 结构化占位（契约4.1 口径）；`results` 诚实标注演示占位；`tools` 用白名单内 `knowledge.search`；不落库、不调 `memory.write`（合规 C1/C3） | `reminder.py` |
| c3 | 记忆反馈（memory_feedback） | 占位 | ⚠️ 阶段2 占位 | 真实识别意图 + 结构化占位（契约4.1 口径）；`results` 诚实标注演示占位；`tools` 用白名单内 `knowledge.search`；不写长期记忆、不调 `memory.write`（合规 C1/C3） | `memory.py` |
| c4 | 健康生活（health_life） | 占位 | ⚠️ 阶段2 骨架 | `results` 标注「演示占位（阶段2 骨架已就绪）」，从知识库取相关内容，结构化字段按契约填充 | `placeholder.py` |
| c5 | 家庭照护（family_care） | 占位 | ⚠️ 阶段2 骨架 | 同上 | `placeholder.py` |
| c6 | 家庭协同（family_coord） | 占位 | ⚠️ 阶段2 骨架 | 同上 | `placeholder.py` |
| c7 | 社区活动（community） | 占位 | ⚠️ 阶段2 骨架 | 同上 | `placeholder.py` |
| c8 | 志愿服务（volunteer） | 占位 | ⚠️ 阶段2 骨架 | 同上 | `placeholder.py` |

**关键事实（如实说明，不吹成十成）**

- 八项能力**全部返回恰好 14 字段模板 D**；契约 4.2/4.3/4.4 的 `handoff` / `results` / `usedMemoryRefs`
  从「恒空」改为「按契约填充」，`tools` 由字符串数组升级为对象数组（`{tool,args,result}`）。
- c1 走 **P2 全链路**（真实派活 → A2 → 回执）；c2~c8 走 **A2 内部带 intent 分发**（演示可直接触发，
  无需等 P2 路由）。注意：P2 侧目前仅对「求助类」加了路由关键词，对 c2~c8 的 7 项非求助能力尚未加
  路由关键词——按契约 4.1 占位口径处理，待 P2 配合补齐（非 A2 职责）。
- 测试：pytest **32 passed**（含 `tests/test_capabilities.py` 逐能力审验 14 字段 + 结构化字段非空 +
  tools 对象数组 + handoff 路由 + c2/c3 占位断言 + A5 协议版本码断言）。
- **验收清单补齐（2026-11-07）**：对照 `a2_acceptance_checklist.md` 修 A5（协议版本错误码
  `UNSUPPORTED_PROTOCOL_VERSION`）、E2（补 `UNSUPPORTED_PROTOCOL_VERSION`/`UPSTREAM_TIMEOUT` 码）、
  C1/C3（c2/c3 回归占位、不调 `memory.write`）。F1「无自动重试」对 A2→P2 成立；**A2→LLM 保留自动重试
  作为韧性例外**（模型抖动时必需），已在清单 F1 注明。
- 投屏演示：`python demo_trigger.py caps` 逐一触发 c1~c8（纯数据输出，不含提词文字）。

## ⑨ 改提示词必测（测评 harness）

每次修改 `prompts/system_prompt.txt`、护栏或路由后，**必须先跑测评**，否则无法证明品牌规则没被破坏：

```bash
cd a2_service
python -m pytest -q                 # 全量（含改动必测的回归测评 + 护栏单测）
python tests/eval/run_eval.py       # 仅跑确定性测评（不依赖实时大模型）
python tests/eval/run_eval.py --live  # 额外跑真实 LLM 语义测评（模型不可达自动跳过）
```

`tests/eval/cases.json` 内置品牌/安全/注入/隐私四类用例，覆盖：14 字段格式、长度≤60、
品牌关键词、注入抗性（输入护栏命中 → 品牌化拒答）、隐私不回显。当前 25 个测试全部通过（含 RAG 检索、MCP 协议、权限护栏用例）。

> **为何这是第⑨条**：即便 ①~⑧ 全做了，改提示词忘了跑测评仍会出问题——本 harness 就是为阻断这类回归而建。

