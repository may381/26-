# A1 核心目录导航与 LangGraph 迁移状态

当前实现：LangGraph 1.2.20 显式状态图 + 原有标准库模型/领域客户端。
当前回归：214 项通过（2026-11-07）；P2 首轮旅游文本链路已接入
`8093 → 学校模型规划 → 8091 → v3 Result`，仍需与真实 P2 执行器完成跨机器冒烟。

## 保留的有效文件

- a1.py：模型请求、提示词、计划校验、地点门禁、Conversation。
- graph_runtime.py：StateGraph 节点、条件路由与编译。
- v3_reason_graph.py：P2 v3 七类调用/恢复原因的 StateGraph 路由。
- LangGraph迁移计划.md：总体计划、已完成范围、后续 P2 恢复边界。
- requirements.txt：LangGraph 直接依赖版本。
- domain_chat.py：统一入口、执行白名单、五态协调、重试、失败 packet。
- local_domains.py：固定回环领域客户端、超时、响应限制、幂等键。
- test_*.py：全部回归测试；包含核心、mock 演示和协议服务壳测试。
- service.py、v3_adapter.py：P2 v3 入站、回执/取消、首轮旅游文本及 A2/A3 委派适配。
- 启动A1联调服务.ps1：跨电脑 8093 联调入口；密钥仅进入当前进程环境，不写入磁盘。
- demo.py、mock_flow.py、smoke_http.py、example_invocation.json：开发演示、冒烟及协议示例，保留且不冒充真实业务。
- 运行说明_V0.6.md、本地mock运行示例.txt：仅历史 mock 演练说明。
- archive/README_迁移前历史.md：旧 README 版本记录，不是当前运行规范。

## 当前验收

在本目录执行：

```powershell
python -X utf8 -m unittest -v
```

当前基线 219 项 OK，接口/代码自检 69/69。测试不等于真实 P2 跨机器端到端联调。

## 迁移方案与分工

保留 ask_model、validate_plan、enforce_location、DomainClient 作为可复用模块。
已将控制处理、规划、执行校验、旅游与反诈委派组织为显式 LangGraph 节点和条件边；等待与重试仍使用原状态机。
现有 DomainChat.send 和 packet 保持兼容；当前单步白名单、地点证据和幂等约束必须保留。

A1 管理图内执行状态；P2 管正式任务 ID、版本、确认和业务执行账本。
检查点用于内部恢复，不是长期共享记忆；必须关联 P2 任务，避免重复业务执行。
A2/A3 通过团队约定接口接入，不因采用 LangGraph 自动接通，也不要求队友同时迁移框架。
已完成图路径与隔离测试。检查点恢复、暂停继续、重复恢复尚未启用；须在 P2 去重协议对齐后实现和验收。

## 本轮清理

删除仅生成的 __pycache__ 和四份旧验收/调试日志（实际存在的文件）。
保留所有业务源码、测试、队友服务、原始需求、XMind 和 UI 资料。
没有改动 8091/8000 内部实现。最终队友接口交付文档待用户明确要求后整理。

## 独立命令节点更新

2026-11-05：status、retry、new、reset 已拆成独立图节点，control 仅检查输入并路由；request 负责其他请求准备。A1new 入口兼容测试 8 项通过。原文、幂等键、五态与 packet 保持兼容。

## 任务证据隔离（2026-11-05）

本轮核心完整回归 132 项、A1new/test_server 8 项通过。
Conversation.history 保存已接受的会话轮次；inputs 只保存当前 task_domain 的用户原文。
普通 REPLY 不进入领域证据。同领域 ASK 补充保留限制。
切换领域时先以当前输入重新规划，重新校验通过才提交新范围；可能增加一次模型请求。
模型失败、结构错误、白名单拒绝或领域长度校验失败均不提交候选上下文。
终态的新任务也延迟到校验通过才清旧引用。领域调用失败后保留已通过校验的原文以便查询/重试。
等待或提交不确定时仍阻止新任务；幂等键生成与复用逻辑未改变。
可单独验收：`python -X utf8 -m unittest test_task_evidence -v`。
领域分类仍依赖模型，不宣称能够可靠识别所有隐含任务切换；同领域新任务可用 /new 明确开始。
