# Agent 协议 v3.0 联调格式包

日期：2026-10-29。配合上一级《Agent统一交互协议_v3.0.md》使用。

**这些JSON格式已纳入v3.0协议基线，但接口尚未上线，也不是实际业务成功记录。不要向当前v2服务发送。** 使用mock服务跑完整流程；Schema校验不代替业务状态、权限和幂等验收。

## 这次只定什么

1. 任务与协作：消息接收、任务查询、A1委派、子任务追问与答案回传。
2. 确认与恢复：步骤登记、动作准备、确认决定、失败/未知、调用收据和取消。
3. 共享记忆：先固定“A3交审核建议，A1准备确认，P2执行”的控制关系，并登记记忆审核结果和变更动作Schema。

不加入自动任务转交、SSE、真实报名、复杂多日行程、支付或真实外部通知。

## 文件怎么用

- `control.schema.json`：JSON Schema Draft-07，所有命名格式在definitions里。
- `examples.json`：38份正常格式和14份应拒绝的格式。覆盖问题ID唯一性格式、A1原样转呈子问题、问题版本由P2分配、依赖先完成竞态和MEMORY_REVIEW结果。method/path说明该报文所属接口；响应条目可以没有path，不代表存在空路径接口。headers仅示例额外的幂等头，不代表可以不鉴权。
- `validate.cjs`：使用Ajv校验Schema及上述样例。只读取本地文件，不访问接口、不写业务数据。

调用方引用：`urn:silver-travel:agent:v3:r3#/definitions/InvocationRequest`等命名结构。不要只校验Schema根对象；根对象是定义集合，并不等于任意接口正文。

本包固定控制层。工具args、卡片payload、来源对象、历史片段仍依赖各自登记的业务Schema，不能把允许object理解成允许任意执行命令。未登记能力仍不得开放。服务端要检查schema之外的身份、状态、版本、幂等、归属与执行结果。

## 请求头约定

前端请求沿用当前演示身份头；后续真实登录另定，不把Agent密钥交前端。

内部请求使用对应服务的X-Agent-Key、X-Trace-Id；Agent调用P2还携带X-Agent-Context任务凭证。P2查询或取消Agent调用使用对应Agent服务密钥。样例文件没有真实密钥。

消息提交、动作准备和用户确认决定必须带Idempotency-Key；步骤登记使用程序持久化的requestKey；取消调用使用P2生成的cancelRequestId。原任务取消入口首批也要求Idempotency-Key。正文里不重复传这些HTTP头。

成功外层统一HTTP200、code=OK；失败data=null。确认执行结果未知可以HTTP200/OK查询成功，同时data.state=EXECUTION_UNKNOWN。

## 接口与格式对应

| 调用方向 | 接口定义 | 请求定义 | 返回定义 |
|---|---|---|---|
| P1→P2 | POST /api/v3/agent/messages | MessageRequest | MessageAcceptedResponse |
| P1→P2 | GET /api/v3/agent/tasks/{id} | 无正文 | TaskQueryResponse |
| P1→P2 | POST /api/v3/agent/tasks/{id}/cancel | TaskCancelRequest | TaskCancelResponse |
| P2→Agent | POST /internal/v3/messages | InvocationRequest | AgentResponse |
| A1→P2 | POST /internal/agent/v3/delegations | DelegationRequest | DelegationResponse |
| Agent→P2 | POST /internal/agent/v3/tasks/{id}/steps | StepRegisterRequest | StepRegisterResponse |
| Agent→P2 | POST /internal/agent/v3/actions | ActionPrepareRequest | ActionPrepareResponse |
| 有权限的Agent→P2 | POST /internal/agent/v3/confirmations | ConfirmationPrepareRequest | ConfirmationResponse |
| P1→P2 | GET /api/v3/agent/confirmations/{id} | 无正文 | ConfirmationResponse |
| P1→P2 | POST /api/v3/agent/confirmations/{id}/decision | ConfirmationDecisionRequest | ConfirmationResponse |
| P2→Agent | GET /internal/v3/invocations/{id} | 无正文 | InvocationReceiptResponse |
| P2→Agent | POST /internal/v3/invocations/{id}/cancel | InvocationCancelRequest | InvocationCancelResponse |

普通业务tools入口和领域卡片继续按v3.0协议及各工具登记规范处理，本包不定义全部领域Schema。步骤、动作、问题和确认ID都由程序/P2维护，不让模型自由生成授权。

## 本轮补充的四项边界

- **问题ID与版本**：新问题由产生它的Agent程序生成UUID v4，并在重试/重放时保持不变；P2对ID做全局唯一性校验。Agent的`control.inputRequest`不传`ownerTaskId`和`version`；P2登记时补上归属并分配版本，之后由P2返回给P1和答案引用。
- **A1转呈子问题**：A1逐字保留A2/A3问题的ID和问题字段；P2把它当作当前任务树中已登记问题的引用，核验归属/版本/状态，不另建问题、不改owner或version。A1新提出的问题才生成新的UUID。
- **回答问题不等于改任务**：有效`responseTo`触发`INPUT_PROVIDED`，只恢复问题所属任务。独立子任务和无关确认保持有效；答案若改变某个动作参数或权限范围，只使受影响分支重新校验或失效。
- **子任务先完成**：父任务返回`WAIT_DEPENDENCIES`时，P2登记依赖并立即读取当前状态。若全部完成，立刻携带现有结果调度一次父恢复；并发完成与登记由唯一恢复代次去重。
- **记忆能力登记**：`MEMORY_REVIEW`已作为`Result.payload`类型校验；`memory.change`有专用`MemoryChangeArgs`，只能引用已保存候选/审核ID和版本。P2内部执行器`memory.apply`不开放给Agent。

## 用哪些样例跑一轮

### 子任务追问：05～09、34、35、38

1. A3返回WAIT_INPUT，问题ownerTaskId=child-001。
2. P2登记问题，经CHILD_INPUT_REQUIRED交给A1。
3. A1统一呈现，但必须原样保留全局inputRequestId、问题字段、版本和归属；38展示A1转呈的有效报文。P1查询根任务能得到pendingInputRequests。
4. 用户消息continueTaskId=root-001，responseTo却指向child-001的原问题，这是正确组合。
5. P2先恢复A3，不能把答案交给A1当作已完成的子结果。
6. A3结束后，P2把dependencyResults交给A1整合。

没有continueTaskId先追问、让用户选择，不自动转交。当前运行v2不能识别这些字段。Agent首提问题不带ownerTaskId/version；P2登记后的问题查询带二者。新问题ID必须为UUID v4；同一问题的重放保持ID不变。

### 依赖先完成竞态：36

36展示A3已经完成、但A1稍后才返回等待指令时，P2给A1的立即恢复调用。服务测试还要覆盖“依赖登记和完成事件同时发生”：只能创建一个有效恢复调用，不重新调用已完成的A3。

### 确认和故障恢复：01～04、10～18、21～24

1. 程序登记步骤拿stepId和prepareKey。
2. 准备具体动作拿actionId，再准备确认拿confirmationId。
3. 用户提交决定，P2执行绑定动作。
4. UNKNOWN先查询核查，不能再点一次同意来重新执行；明确失败也只能按P2允许的策略处理。
5. 核查成功后，actionLedger带真实结果恢复A1。
6. 最终回复丢失先查调用收据；取消返回CANCEL_REQUESTED不代表调用已经停止，更不代表外部业务撤销。

样例中的demo.action只用于未来独立mock联调，尚未实现；不报名、不支付、不发真实通知，不得在生产开放。

### 多项确认：25

每个新confirmationId或新版本可触发提示，按父任务串行合并。A2、A3先后产生两项确认不能漏后一项，已决定的旧项不能重复弹出。合并展示不等于合并授权。

### 记忆审核和恢复失效：20、26～28、37

A3返回候选与审核建议；A1引用已保存candidate/review的ID和版本准备动作，不能改内容或扩大领域。20是审核数据，37是包装为`MEMORY_REVIEW`的正式结果卡片。P2执行本人确认。

恢复时readSet.provenanceRefs继续关联旧卡片、子结果及记忆，即使本轮没有新memory.search，也必须校验。Schema只能确认字段存在，不能证明服务端真的过滤了失效资料。

## 本地校验

需要Node.js和支持Draft-07的Ajv。已有Ajv的环境执行：

```text
node validate.cjs
```

Ajv不在当前模块搜索路径时，传入已安装的Ajv模块目录：

```text
node validate.cjs <本机Ajv模块目录>
```

脚本不自动安装依赖。正常输出为38个正常样例通过、14个反例被拒绝。案例中的固定日期只用于格式校验，不表示当前仍在有效期。

## 服务实现以后还必须验收什么

以下不能靠JSON Schema证明，需要mock/真实服务运行测试：

| 案例 | 应有结果 |
|---|---|
| 回答别人的/其他根任务的问题 | 拒绝，不恢复子任务 |
| 同Key重复回答 | 不重复入队或生成消息 |
| 新Key回答已结束问题/旧问题版本 | 409/QUESTION_NOT_PENDING，要求刷新 |
| 子问题等待用户，父任务在等依赖 | 能提前通过A1提问，不发生相互等待 |
| 子任务先完成、父任务后登记等待 | P2用已完成结果立即恢复A1，只创建一次恢复记录，不重跑子任务 |
| 子任务完成与父依赖登记同时发生 | 同一resumeGeneration只允许一个调度者入队 |
| Agent首提问题带了version | Schema拒绝；问题版本由P2分配 |
| A1转呈有效的A2/A3问题 | 原样保留同一ID及内容；P2不新建问题、不改归属和版本 |
| 两个Agent创建问题发生ID碰撞 | P2全局唯一约束拒绝新问题，返回409/INPUT_REQUEST_ID_CONFLICT；不覆盖既有问题 |
| A1引用不属于当前任务树或已过期的问题ID | 返回409/QUESTION_NOT_PENDING，不泄露其他任务信息 |
| 回答一个子问题 | 只恢复ownerTaskId，不自动取消独立子任务/无关确认；受影响动作重新校验 |
| A2/A3先后各产生确认 | 两项均可提示，各自同意/拒绝 |
| A3尝试准备记忆确认 | 拒绝；由A1准备 |
| A1改变已审核候选的内容或范围 | 拒绝，要求新候选/审核版本 |
| memory.change缺少候选/审核版本或擅自传正文 | Schema或业务校验拒绝；仅P2内部memory.apply落库 |
| 恢复上下文引用已删除记忆或已撤权内容 | 不注入模型，旧回复不落地 |
| 同动作结果未知、用户重复点击 | 先核查，不产生第二次副作用 |
| Agent取消后迟到回复 | 不覆盖新任务状态，真实effects继续保留 |
| 进度更新和最终回复并发 | 序号去重，不把普通版本增长当作最终结果失效 |

各方确认这些控制格式后，第一步先交可运行测试服务；不要因为领域工具还没全部完成而继续扩写整体架构。
