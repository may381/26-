# P2 后端独立基线

本目录保存已实现并在本地验证的 P2 后端。它与仓库原 `server/` 并行保留，尚未统一技术栈或业务接口。原 `server/`、`admin/`、`mobile/` 保持现状。

## 与原工程的区别

| 内容 | 原 `server/` | 本目录 |
|---|---|---|
| Java / Spring Boot | Java 17 / Boot 4.1.1 | Java 21 / Boot 3.5.16 |
| 数据库 | H2 文件库，预留 MySQL | MySQL 8.4、Flyway、MyBatis-Plus |
| 接口 | 原景点维护与 `/api/health` | 下表 20 个 P2 操作；不包含原景点 CRUD |
| 身份 | 原骨架无认证 | local 模式固定 mock 身份及业务权限校验 |
| 健康检查 | 8080 `/api/health` | 8081 `/actuator/health` |

两套后端默认都使用业务端口 8080，不能同时按默认配置启动。原前端仍按旧接口调用，尚未改造为 P2 页面；不能将前端代理切到本服务后就认定前端已接入。原 CI 仍只检查原 `server/` 和前端，不代表本目录已纳入 CI。

本目录 MySQL 独立使用 Compose 项目 `silver-tourism-p2-baseline` 和本机端口 **3308**，数据库为 `silver_tourism_demo`。不会复用开发者旧工程的 `silver-tourism-local` 容器/卷/密码，也不读取原 `server/data/`。不要把旧 `.env`、H2 文件或 MySQL 数据卷随代码提交。

## Windows 本地启动

需要 PowerShell 7、JDK 21、Docker Desktop Linux 引擎；Python HTTP mock 模式另需 Python 3。首次 Maven 构建需联网。

从仓库根目录进入：

```powershell
cd p2-backend
# 生成本机随机数据库密码与三个独立 Agent Key，不打印密钥。
.\scripts\init-env.ps1
# 将路径替换为自己的 JDK21 根目录，不是 bin。
.\scripts\dev.ps1 -JdkHome 'C:\实际路径\jdk-21'
# 或用三个本地 Python 协议 mock（两种启动方式选一种）：
# .\scripts\dev.ps1 -PythonMock -JdkHome 'C:\实际路径\jdk-21'
```

`.env` 留在本机且已忽略。已有值不覆盖。高德需要自己的 Web 服务 Key，填写 `AMAP_WEB_SERVICE_KEY`；不要把 Key 发到群里或前端。启动前确认原后端/旧 P2 未占用 8080、Python mock 未占用 18001～18003。本服务主端口仅监听 IPv4 回环地址。

启动后：

- Swagger：`http://127.0.0.1:8080/swagger-ui/index.html`，选择 p2 分组。
- Authorize 两项都要确认：actorId=`u100`，actorRole=`ELDER`。
- 首次先测 GET `/api/routes`，不填 userId，避免未建档 404。
- 健康：`http://127.0.0.1:8081/actuator/health`；不是 `/api/health`。
- Ctrl+C 停止 Java 与本脚本启动的 Python 子进程。MySQL 保留，可用 `.\scripts\database.ps1 -Task stop` 停止，不删卷。

服务器、HTTPS、真实登录和多机构隔离不在当前本地基线内。127.0.0.1 代表各自电脑，代码推上 GitHub 不等于发布公网服务。

## 当前公开操作

| 模块 | 操作 |
|---|---|
| 档案 | GET/PATCH `/api/profile?userId=` |
| 家属 | GET/POST `/api/family-relations?userId=`；POST `/{id}/approve`、`/{id}/revoke`；PATCH `/{id}/permissions` |
| 路线/地图 | GET `/api/routes`；GET `/api/routes/{id}/map` |
| 游览 | POST `/api/trips?userId=`；GET `/api/trips/{id}?userId=`；POST `/api/trips/{id}/finish?userId=` |
| 求助 | POST/GET `/api/help-events`；GET `/{id}`；POST `/{id}/acknowledge`、`/{id}/resolve` |
| Agent | POST `/api/agent/messages` |
| 语音 | POST `/api/speech/transcriptions`、`/api/speech/syntheses` |

字段/校验见运行中的 Swagger 与 `api/P2.openapi.json`；可复制请求在 `server/requests/*.http`。家属状态操作同样传 userId；求助/Agent 创建的 userId 放正文。Profile.id 是 UUID，u100 是 mock 老人标识，两者不能互换。

公共信封 `{code,message,data}`，成功为 HTTP 200。常见错误 400 参数、401 身份、403 权限、404 资源、409 状态/重复冲突、502 上游故障。角色与 ID 必须匹配，不能只改 query userId 代替认证。

- 老人：u100/ELDER 或 u101/ELDER，只能操作本人资料。
- 求助工作人员：scenic-operator-001/SCENIC、scenic-operator-002/SCENIC、official-operator-001/OFFICIAL。
- 求助管理员：admin-operator-001/ADMIN；不因此能读取所有老人档案。
- 家属：family-operator-001/FAMILY 仅预留角色，尚未关联具体老人，不能任意读取资料。

求助创建可传稳定 `Idempotency-Key`，24小时内同请求重放返回首次快照；新求助用新 Key，最新状态用 GET。接单用工作人员身份，解决须实际接单人或管理员。家属 PENDING→ACTIVE→REVOKED，不允许重复批准；Trip 结束后再次 finish 返回 409。

## 模拟边界与后续缺口

- 景区点位/设施/路线为 MOCK，来源明确；高德请求可真实执行，但未核实道路适老可达性。
- Java mock 或三个 Python 协议 stub 可运行；它们不是三位负责人的真实模型服务。内部协议需与 A1/A2/A3 确认，服务 Key 不能代替老人授权。
- ASR 固定演示转写，TTS audioUrl=null；不识别真实录音、不产生真实音频。
- 通知仅模拟，未触达家属/景区/官方；送达不等于接单。
- 七个二期 intent 返回明确未开放结果。长期记忆写入禁用，不能信任 Agent 自报 confirmed。
- 实际进度、途中调整、家属关联/视图、游后记录与可信偏好确认待补；不宣称完整一期/二期均已完成。

## 验证

在本目录运行：

```powershell
.\scripts\server.ps1 -Task verify -JdkHome 'C:\实际路径\jdk-21'
# 服务已运行时，另一个 PowerShell 执行只读 HTTP 检查：
.\scripts\smoke.ps1
```

verify 包括独立 Testcontainers MySQL、业务测试、Jar 打包、Spotless 格式检查。不会重置本地演示库。smoke 不创建档案或求助，验证 Swagger、路线、mock 语音/Agent 链路及错误权限。

Postman 导入 `api/P2.postman_collection.json`、`api/P2.local.postman_environment.json`。00～08 会覆盖 u101 的演示档案并创建记录，必须使用可写测试数据；90 的高德与 ASR 为手动依赖测试，先从 Runner 取消选择。集合有28个请求，其中26个可自动跑，自动保存各步 ID；完成后会结束游览、撤回关系、解决求助，但不删除历史记录。

原开发目录最近基线为156项测试通过、26个Postman请求/75项断言通过。迁入本目录后的结果应以本次执行为准，不能只引用旧记录。迁入后的专用本机检查不等于已通过仓库 CI 或前端联调。

迁入验证（2026-10-27）：在本目录执行156项测试，0失败、0错误、0跳过；按团队 Git 规则统一 LF 后，Spotless 校验和最终 Jar 打包通过。PowerShell 语法、独立 Compose 配置及暂存文件密钥检查通过。此次未重跑 Postman，也未启动第二套业务服务覆盖原本机8080；没有把旧目录的 HTTP 结果当作新目录的实测结果。

## 备份与重置

```powershell
.\scripts\backup.ps1
.\scripts\reset-demo.ps1   # 只预览
```

备份保存在忽略的 backups。只有确实需要清空专用演示库时，停止所有相关 Java 后显式用 `reset-demo.ps1 -Execute`；会先备份并检查容器归属。不可删除卷来处理一般启动问题。

## 合并边界

本次仅提交独立 P2 基线，不更改原前端、原 server、其 Java17 CI 或仓库文档策略。旧景点 API、技术栈和用户身份的统一需另做迁移方案与联调，不能用直接覆盖替代。过程文档、Word、备份与本机配置不在本目录共享范围内。
