# 银龄数字分身平台｜纯代码版

本目录只保留项目运行、测试和联调需要的源码、配置模板与必要静态资源，不包含设计稿、答辩材料、截图、XMind、Excel、测试报告、依赖缓存和编译产物。

## 代码目录

- `a1-orchestrator/`：A1 总智能体核心，包含 LangGraph 编排、P2 v3 入站服务、领域委派、回执/取消和测试。
- `A1new/`：统一问答入口、演示页面及 P2 公开接口过渡客户端。
- `a1-guide/`：旅游服务的 Spring Boot 源码、浏览器端代码和语音处理脚本。
- `anti-fraud/`：反诈服务的 FastAPI 后端与 React/Vite 前端源码。
- `.github/workflows/a1-ci.yml`：GitHub 自动执行的 A1 回归测试。

## A1 合并前验证

需要 Python 3.12、Node.js 22，并先安装 A1 依赖：

```powershell
python -m pip install -r .\a1-orchestrator\requirements.txt
pwsh -ExecutionPolicy Bypass -File .\合并前自检.ps1
```

当前基线：

- A1 LangGraph/P2 v3 核心测试：223 项。
- A1 接口与实现一致性检查：69/69 项。
- 统一入口测试：45 项。
- 关键浏览器脚本语法检查：全部通过。

准备三个模块一起合并时，先运行 `anti-fraud\setup-backend.bat` 创建反诈虚拟环境，再执行：

```powershell
pwsh -ExecutionPolicy Bypass -File .\全项目合并前自检.ps1
```

当前完整基线还包括旅游服务 106 项测试和反诈服务 38 项测试。

## 同机启动三个业务部分

先分别准备旅游服务和反诈服务的本地依赖环境，然后在仓库根目录运行：

```powershell
python .\A1new\统一启动\launcher.py all
```

该命令会启动 A1 总智能体（8093）、旅游服务（8091）、反诈服务（8000）和统一页面（8095），每项使用独立窗口，便于查看错误。只检查状态时执行：

```powershell
python .\A1new\统一启动\launcher.py status
```

四项均显示 `RUNNING` 后，在设置了与 A1 启动时相同的 `A1_SERVICE_KEY` 的终端运行真实链路自检：

```powershell
python -X utf8 .\三服务联调自检.py
```

该脚本会分别走 `P2 v3 入站格式 → A1 总智能体 → 旅游/反诈服务`。反诈返回 `PENDING` 时只代表真实任务已受理并仍在处理，不会被当成风险结论。

服务分布在不同电脑时不要使用统一启动器；应分别启动服务，并通过 `.env.example` 中的 `A1_TOURISM_URL`、`A1_FRAUD_URL`、`AGENT_A1_URL` 配置真实可访问地址。

## P2 联调

1. 根据 `.env.example` 在部署环境配置变量，不要提交真实密钥。
2. 启动旅游服务（默认 8091）。
3. 运行 `a1-orchestrator/启动A1联调服务.ps1`，启动 A1 v3 服务（默认 8093）。
4. P2 配置可访问的 A1 地址和相同的服务密钥。
5. 跨电脑联调不能使用 P2 电脑自己的 `127.0.0.1`，应填写 A1 电脑的局域网或虚拟局域网地址。

## 不应提交

- `.env`、`.a1-service-key` 及任何真实 API 密钥。
- `node_modules`、虚拟环境、Maven `target`、模型文件和依赖缓存。
- SQLite/数据库文件、日志、PID、浏览器测试配置和临时报告。
