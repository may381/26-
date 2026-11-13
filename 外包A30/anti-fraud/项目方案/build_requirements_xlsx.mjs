import { Workbook, SpreadsheetFile } from "file:///C:/Users/dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";
const out = "D:/Desktop/外包A30/anti-fraud/项目方案/详细需求分析.xlsx";
const wb = await Workbook.create();
const navy="#FFFFFF", purple="#F2F2F2", bg="#FFFFFF", line="#D9D9D9", text="#222222";
const sectionFill="#F2F2F2";
function setup(ws, widths){ ws.showGridLines=false; for (const [c,w] of Object.entries(widths)) ws.getRange(`${c}:${c}`).format.columnWidth=w; }
function title(ws, range, value){ const r=ws.getRange(range); r.merge(); r.values=[[value]]; r.format={fill:navy,font:{name:"Microsoft YaHei",bold:true,color:"#FFFFFF",size:15},horizontalAlignment:"left",verticalAlignment:"center",borders:{bottom:{style:"medium",color:"#666666"}}}; r.format.rowHeight=34; }
function header(ws, range){ const r=ws.getRange(range); r.format={fill:purple,font:{name:"Microsoft YaHei",bold:true,color:"#222222",size:10},wrapText:true,verticalAlignment:"center",horizontalAlignment:"center",borders:{preset:"all",style:"thin",color:line}}; r.format.rowHeight=28; }
function body(ws, range){ const r=ws.getRange(range); r.format={font:{name:"Microsoft YaHei",color:text,size:10},wrapText:true,verticalAlignment:"top",borders:{preset:"all",style:"thin",color:line}}; }
function statusColor(ws, col, start, end){ const r=ws.getRange(`${col}${start}:${col}${end}`); r.format.wrapText=true; }

const req=[
["账户与角色","登录/注册","手机号+验证码模拟登录；无真实鉴权，登录后进入工作台。","P0","已实现","输入手机号和验证码后进入仪表盘","原型态；正式版需接入鉴权"],
["账户与角色","角色设置","老人、儿童、青壮年、自定义；年龄、职业、性别、风险偏好、大字号模式。","P0","已实现","保存后刷新仍保留设置","localStorage/SQLite"],
["账户与角色","监护人管理","新增、删除、默认通知监护人，支持姓名、关系、电话、邮箱。","P0","已实现","可新增监护人并在预警中选择","QQ邮箱通知需授权码"],
["工作台","仪表盘","安全评分、检测次数、拦截风险、待处理预警、最近预警和7日趋势。","P0","已实现","数据卡片和趋势图可正常展示","使用模拟/数据库数据"],
["智能助手","文本输入","输入聊天记录、短信内容，最大10000字符并提交分析。","P0","已实现","空内容拦截；成功返回结构化风险结果","后端调用本地Ollama"],
["智能助手","图片上传与OCR","上传jpg/png/webp截图，预览并提取文字后进行风险分析。","P0","已实现","文件校验、缩略图、OCR结果展示","PaddleOCR/本地模型；大图需限制"],
["智能助手","音频上传与转写","上传wav/mp3/m4a等音频，转写为文本并分析话术。","P0","已实现","显示上传状态、转写结果、风险判断","Faster-Whisper本地模型"],
["智能助手","音频录制","浏览器MediaRecorder录音后提交分析。","P1","部分实现","获得麦克风权限后可录音并上传","需HTTPS或localhost"],
["智能助手","视频入口","保留上传占位，提示视频分析开发中。","P2","后续迭代","不展示虚假分析结果","需要抽帧和多模态模型"],
["风险引擎","风险分级","低/中/高三级，统一输出风险等级、诈骗类型、置信度。","P0","已实现","每次分析返回标准JSON","模型异常时使用规则兜底"],
["风险引擎","证据定位","保留命中原文、OCR文本、音频时间段等证据。","P0","部分实现","结果中显示证据摘录","坐标/时间戳视解析能力逐步补齐"],
["风险引擎","诈骗类型识别","覆盖投资理财、刷单、AI语音、虚假征信、公检法、贷款、购物、游戏、客服、婚恋。","P0","已实现","类型命中可在结果与预警中查看","需持续增加案例"],
["风险引擎","RAG相似案例","检索知识库案例并在分析结果中引用来源。","P0","已实现","返回相似案例和匹配摘要","本地向量库；当前以轻量检索为主"],
["风险引擎","多模态融合","文本、OCR、音频转写结果合并后综合判断。","P0","已实现","一次任务可关联多种证据","视频暂不参与融合"],
["风险引擎","个性化提醒","根据角色和风险偏好调整提醒方式，不改变风险事实。","P1","已实现","不同角色显示不同防御建议","角色策略可配置"],
["预警中心","自动建预警","中高风险分析自动生成预警并保存。","P0","已实现","分析成功后预警列表新增记录","SQLite持久化"],
["预警中心","筛选与详情","按等级、类型、时间筛选；查看完整证据、建议和通知记录。","P0","已实现","筛选结果正确，详情可关闭","前端路由/模态框"],
["预警中心","处置状态","支持标记已处理、批量处理和处理备注。","P0","已实现","状态更新后列表和统计同步","需保留审计时间"],
["监护人联动","站内通知","点击通知监护人后显示发送状态并写入通知日志。","P0","已实现","通知记录含时间、方式、结果","模拟通知可用"],
["监护人联动","QQ邮箱通知","通过QQ SMTP发送带Token的预警链接。","P1","已接入待配置","配置授权码后可发送测试邮件","需要QQ邮箱SMTP授权码和公网/局域网地址"],
["监护人联动","监护人确认页","监护人查看受限事件详情并确认、核实中或确认风险。","P1","已实现","Token有效期内状态可更新","Token默认24小时"],
["报告中心","安全报告","按时间范围生成风险趋势、类型分布、等级分布报告。","P0","已实现","报告列表可查看历史记录","支持模拟数据和真实预警"],
["报告中心","导出与打印","报告详情支持打印/导出当前页面。","P1","已实现","浏览器打印预览正常","PDF导出可后续增强"],
["知识库","案例管理","按诈骗类型维护关键词、案例数和更新时间。","P0","已实现","列表可查看知识条目","SQLite本地持久化"],
["知识库","文本/文件上传","支持粘贴文本和txt/json/csv文件，选择诈骗类型。","P0","已实现","文件大小和扩展名校验","单文件建议≤2MB"],
["知识库","清洗去重","去除空白、HTML和乱码，按哈希去重。","P0","已实现","重复案例不重复入库","保留原文与清洗结果"],
["知识库","向量化检索","案例分段后写入本地向量库，用于相似案例检索。","P0","部分实现","新增案例可被检索或显示索引状态","Embedding模型和Chroma可继续增强"],
["知识库","版本与回归","知识库版本隔离，更新后运行回归验证再发布。","P2","后续迭代","版本可回滚且有评估记录","适合比赛后续迭代"],
["数字人","形象展示","右侧显示小安数字人/安全助手，区分待机、分析、高风险状态。","P1","已实现","风险状态变化时形象状态变化","当前为SVG/CSS轻量形象"],
["数字人","语音播报","播报风险摘要和防御建议，支持停止和声音开关。","P1","部分实现","有TTS时可播放，无TTS时保留文字","浏览器SpeechSynthesis兜底"],
["系统基础","后端API","FastAPI+Uvicorn提供健康检查、分析、预警、知识库、报告接口。","P0","已实现","接口返回统一JSON并有错误码","前后端分离"],
["系统基础","数据库","SQLite保存用户、监护人、分析、预警、通知、知识库等。","P0","已实现","重启服务数据不丢失","正式版可迁移PostgreSQL"],
["系统基础","媒体存储","上传文件写入data/uploads，数据库只存路径和元数据。","P0","已实现","不把二进制直接塞入SQLite","需定期清理"],
["系统基础","本地模型","Ollama qwen3.5:4b负责文本/图片；Faster-Whisper负责音频转写。","P0","已接入","检查模型连接后可执行分析","首次调用需等待模型加载"],
["系统基础","隐私与安全","密钥只放后端.env；上传内容本地处理；输出明确能力边界。","P0","已实现","前端不暴露密钥，错误不泄露敏感内容","公网部署需HTTPS"],
["测评评估","标准测评集","不少于20案例，黑白1:1，黑样本覆盖不少于10种类型。","P0","已实现","可批量运行并生成统计","需持续补充音频/图片样本"],
["测评评估","指标统计","计算Accuracy、Precision、Recall、F1、FPR和平均时延。","P0","部分实现","报告包含混淆矩阵和分组指标","需补齐模型推理压力测试"],
["测评评估","压力测试","连续运行记录成功率、错误码、时延和资源峰值。","P1","部分实现","可导出压力测试结果","模型资源占用需在本机验证"],
["部署交付","启动脚本","提供前端、后端、模型检查和初始化脚本。","P0","已实现","Windows按文档可启动","端口被占用时需提示"],
["部署交付","使用说明","说明安装、启动、模型下载、配置、测试和常见故障。","P0","已实现","新用户可按README运行","持续同步功能变更"],
["能力边界","不替代官方反诈","不承诺自动报警、冻结资金、阻断通话或替代公安判断。","P0","已实现","高风险建议拨打110/96110并人工核实","必须在演示和文档中声明"]
];
const ws=wb.worksheets.add("需求总览"); setup(ws,{A:16,B:20,C:46,D:10,E:16,F:38,G:34}); title(ws,"A1:G1","安知·多模态反诈智能助手｜详细需求分析"); ws.getRange("A2:G2").merge(); ws.getRange("A2").values=[["来源：项目方案/详细需求分析.md  | 版本：迭代版  |  更新时间：2026-09-29"]]; ws.getRange("A2").format={font:{name:"Microsoft YaHei",color:"#64748B",italic:true,size:10}}; ws.getRange("A4:G4").values=[["模块","功能点","功能说明","优先级","当前状态","验收标准","依赖/限制"]]; header(ws,"A4:G4"); ws.getRange(`A5:G${4+req.length}`).values=req; body(ws,`A5:G${4+req.length}`); ws.freezePanes.freezeRows(4); ws.tables.add(`A4:G${4+req.length}`,true,"RequirementsTable");
const iface=[
["GET","/api/health","系统","健康检查","已实现","返回服务状态与模型配置摘要"],["GET","/api/alerts","预警","查询预警列表","已实现","支持等级、类型和状态筛选"],["POST","/api/analyze/text","智能助手","文本风险分析","已实现","返回结构化风险、证据、建议"],["POST","/api/analyze/image","智能助手","图片OCR与风险分析","已实现","multipart上传并返回OCR和风险结果"],["POST","/api/analyze/audio","智能助手","音频转写与风险分析","已实现","返回转写、时长和风险结果"],["POST","/api/alerts/{id}/email","监护人","邮件通知监护人","已接入待配置","QQ SMTP授权码后发送"],["POST","/api/guardian/alerts/{token}/confirm","监护人","监护人确认处置","已实现","Token有效期内更新状态"],["POST","/api/knowledge/cases","知识库","上传案例并清洗入库","已实现","文本或txt/json/csv"],["GET","/api/reports","报告","查询报告列表","已实现","返回报告摘要"],["POST","/api/reports","报告","生成安全报告","已实现","按时间范围汇总统计"]
];
const wi=wb.worksheets.add("接口清单"); setup(wi,{A:12,B:34,C:16,D:30,E:18,F:48}); title(wi,"A1:F1","接口与服务清单"); wi.getRange("A2:F2").merge(); wi.getRange("A2").values=[["用于开发联调、演示和后续部署检查"]]; wi.getRange("A4:F4").values=[["方法","路径","模块","用途","状态","说明"]]; header(wi,"A4:F4"); wi.getRange(`A5:F${4+iface.length}`).values=iface; body(wi,`A5:F${4+iface.length}`); wi.freezePanes.freezeRows(4); wi.tables.add(`A4:F${4+iface.length}`,true,"ApiTable");
const acc=[
["P0","登录与角色设置","手机号验证码登录，角色和大字号设置可保存并恢复","已实现","手动回归"],["P0","文本分析闭环","提交诈骗话术，10秒级返回风险等级、类型、证据和建议","已实现","接口+页面"],["P0","图片OCR闭环","上传截图，返回OCR文字和风险结论；失败有明确提示","已实现","样例图片"],["P0","音频转写闭环","上传音频，返回转写文本并生成风险结论","已实现","样例音频"],["P0","预警与处置","中高风险自动生成预警，可查看详情并标记已处理","已实现","页面回归"],["P0","知识库入库","文本/文件清洗去重后可查询，新增内容有日志","已实现","文件样例"],["P1","监护人联动","站内通知可记录；QQ邮箱配置后可收到Token链接","已接入待配置","SMTP配置后验证"],["P1","报告与评估","报告含趋势、类型、等级统计；评估含F1和准确率","部分实现","批量测评"],["P1","数字人反馈","分析中、高风险、播报状态有视觉或语音反馈","部分实现","浏览器验证"],["P2","知识版本回滚","新知识版本可回归验证并切换/回滚","后续迭代","开发测试"]
];
const wa=wb.worksheets.add("验收标准"); setup(wa,{A:10,B:28,C:55,D:18,E:24}); title(wa,"A1:E1","验收标准与测试记录"); wa.getRange("A4:E4").values=[["优先级","验收项","通过条件","当前状态","验证方式"]]; header(wa,"A4:E4"); wa.getRange(`A5:E${4+acc.length}`).values=acc; body(wa,`A5:E${4+acc.length}`); wa.freezePanes.freezeRows(4); wa.tables.add(`A4:E${4+acc.length}`,true,"AcceptanceTable");
const roadmap=[["V0.1 原型","登录、仪表盘、预警、报告、知识库、文本分析","已完成","可演示核心链路","无"],["V0.2 多模态","图片OCR、音频转写、本地Ollama联调","已完成","验证多模态输入","模型首次加载较慢"],["V0.3 闭环","监护人邮件、Token确认、通知日志","已接入待配置","配置QQ邮箱后验收","需要SMTP授权码"],["V0.4 评估","混淆矩阵、时延埋点、压力测试报告","进行中","形成比赛评估材料","依赖固定测评集"],["V1.0 迭代","知识版本、回归发布、视频分析、声学鉴伪","后续迭代","增强创新点和稳定性","模型与算力成本"]];
const wr=wb.worksheets.add("版本规划"); setup(wr,{A:18,B:52,C:18,D:38,E:32}); title(wr,"A1:E1","版本规划与实施顺序"); wr.getRange("A4:E4").values=[["版本","范围","状态","目标","依赖/风险"]]; header(wr,"A4:E4"); wr.getRange(`A5:E${4+roadmap.length}`).values=roadmap; body(wr,`A5:E${4+roadmap.length}`); wr.freezePanes.freezeRows(4); wr.tables.add(`A4:E${4+roadmap.length}`,true,"RoadmapTable");
const risks=[["模型","本地模型首次加载慢、输出格式可能不稳定","前端显示加载态；后端JSON校验与规则兜底","中","已处理"],["邮箱","QQ邮箱SMTP暂未授权，无法真实发信","先使用站内模拟通知；配置授权码后联调","中","待配置"],["隐私","聊天截图和录音包含敏感信息","本地处理、限制上传、提供删除入口，不保存无关原文件","高","持续检查"],["能力边界","无法替代公安黑名单、冻结资金和自动报警","结果页明确提示拨打110/96110并人工核实","高","已声明"],["部署","端口5173/8000可能被其他项目占用","启动脚本检查端口并提示改端口","中","已处理"],["数据","测评集过少或样本泄漏会导致指标失真","区分开发、回归、最终测试集并记录来源","中","进行中"]];
const wk=wb.worksheets.add("风险与边界"); setup(wk,{A:14,B:42,C:58,D:10,E:16}); title(wk,"A1:E1","项目风险、限制与应对"); wk.getRange("A4:E4").values=[["类别","风险/限制","应对措施","等级","状态"]]; header(wk,"A4:E4"); wk.getRange(`A5:E${4+risks.length}`).values=risks; body(wk,`A5:E${4+risks.length}`); wk.freezePanes.freezeRows(4); wk.tables.add(`A4:E${4+risks.length}`,true,"RiskTable");
await wb.recalculate();
for (const s of ["需求总览","接口清单","验收标准","版本规划","风险与边界"]) { await wb.inspect({kind:"table",sheetId:s,range:"A1:G12",include:"values,formulas",tableMaxRows:12,tableMaxCols:8}); }
const xlsx=await SpreadsheetFile.exportXlsx(wb); await xlsx.save(out);
console.log(`saved ${out}`);



