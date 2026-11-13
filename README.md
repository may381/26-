# 银龄智游：P2 后端与 A1 智能体

本集成分支包含独立的 P2 平台后端，以及 A1 总智能体、旅游智能体、
反诈智能体和统一演示页面。

## P2 后端

P2 使用 Java 21、Spring Boot 和 MySQL 8.4。

- [本地启动与开发](p2-backend/README.md)
- [P2 后端接口文档](p2-backend/api/P2后端接口文档_v3.0.md)
- [本地语音服务](p2-backend/speech/README.md)

## A1 智能体

- `a1-orchestrator/`：基于 LangGraph 的 A1 总智能体与 v3 联调入口
- `a1-guide/`：旅游智能体服务
- `anti-fraud/`：反诈分析服务
- `A1new/`：统一演示页面与本地协调入口

A1 的启动方式、端口、环境变量及联调步骤见
[`README-A1.md`](README-A1.md)。合并前可在仓库根目录运行：

```powershell
.\全项目合并前自检.ps1
python -X utf8 .\三服务联调自检.py
```

## 当前联调边界

- P2 默认通过 v3 接口调用 A1 的 8093 服务。
- A1 默认调用旅游服务 8091 和反诈服务 8000。
- 真实旅游查询需要配置高德 Web 服务 Key。
- 密钥和本机地址只通过环境变量或本地配置提供，不提交到 Git。
- 当前统一页面仍可作为比赛演示入口；正式移动端接入需另行完成。
