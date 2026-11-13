import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outDir = "D:/Desktop/外包A30/anti-fraud/项目方案";
const outFile = `${outDir}/安知与国家反诈中心APP对比及需求分析.xlsx`;
await fs.mkdir(outDir, { recursive: true });

const wb = Workbook.create();
const overview = wb.worksheets.add("项目总览");
const comparison = wb.worksheets.add("差异对比");
const requirements = wb.worksheets.add("功能需求");
const nonfunctional = wb.worksheets.add("非功能需求");
const acceptance = wb.worksheets.add("验收测试");
const sources = wb.worksheets.add("来源与边界");

const font = "Microsoft YaHei";
const colors = {
  navy: "#172554", blue: "#1D4ED8", cyan: "#0891B2", pale: "#EFF6FF",
  green: "#15803D", greenBg: "#DCFCE7", amber: "#B45309", amberBg: "#FEF3C7",
  red: "#B91C1C", redBg: "#FEE2E2", gray: "#475569", grayBg: "#F1F5F9",
  border: "#CBD5E1", white: "#FFFFFF", ink: "#0F172A"
};

function title(sheet, text, subtitle, endCol="J") {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${endCol}1`).merge();
  sheet.getRange("A1").values = [[text]];
  sheet.getRange("A1").format = { fill: colors.navy, font: { name: font, size: 20, bold: true, color: colors.white }, rowHeight: 38, verticalAlignment: "center" };
  sheet.getRange(`A2:${endCol}2`).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange("A2").format = { fill: colors.pale, font: { name: font, size: 10, color: colors.gray }, rowHeight: 30, verticalAlignment: "center", wrapText: true };
}

function header(sheet, range) {
  sheet.getRange(range).format = { fill: colors.blue, font: { name: font, size: 10, bold: true, color: colors.white }, verticalAlignment: "center", wrapText: true, borders: { bottom: { style: "continuous", color: colors.border } } };
}

function body(sheet, range) {
  sheet.getRange(range).format = { font: { name: font, size: 10, color: colors.ink }, verticalAlignment: "top", wrapText: true, borders: { bottom: { style: "continuous", color: colors.border } } };
}

function section(sheet, range, text) {
  sheet.getRange(range).merge();
  const anchor = range.split(":")[0];
  sheet.getRange(anchor).values = [[text]];
  sheet.getRange(range).format = { fill: colors.grayBg, font: { name: font, size: 11, bold: true, color: colors.navy }, rowHeight: 26, verticalAlignment: "center" };
}

title(overview, "安知·多模态反诈智能助手：需求分析", "基于赛题要求、现有原型能力和官方公开资料整理｜版本：V1.0｜日期：2026-09-23", "H");
section(overview, "A4:H4", "一、核心结论");
overview.getRange("A5:H8").merge();
overview.getRange("A5").values = [["国家反诈中心 App 是公安机关面向公众提供的权威反诈入口，核心能力来自公安涉诈线索、风险账号和处置体系。安知是面向比赛与校园演示场景的多模态 AI 风险辅助工具，优势在于用户主动提交文本、图片和音频后进行解释性分析、个性化提醒、监护人联动和报告生成。两者是补充关系，安知不能替代警方身份核验、涉诈账号查询、报案受理、电话拦截或执法处置。"]];
overview.getRange("A5:H8").format = { fill: "#F8FAFC", font: { name: font, size: 12, color: colors.ink }, wrapText: true, verticalAlignment: "center", borders: { top: { style: "continuous", color: colors.border }, bottom: { style: "continuous", color: colors.border }, left: { style: "continuous", color: colors.border }, right: { style: "continuous", color: colors.border } } };

section(overview, "A10:H10", "二、项目定位与差异化");
overview.getRange("A11:B15").values = [
  ["目标用户", "老人、学生、普通家庭、财会人员及其监护人"],
  ["核心场景", "用户收到可疑文本、聊天截图或语音后主动提交，系统给出风险等级、依据和建议"],
  ["差异化", "多模态统一分析、角色化阈值、监护人联动、可解释证据、知识库更新和比赛评估"],
  ["部署方式", "本地 Web 原型；Ollama + SQLite + Faster-Whisper，适合低成本演示"],
  ["明确边界", "不接入公安数据库，不验证真实身份和账户，不自动报警，不承诺代替国家反诈中心 App"]
];
overview.getRange("A11:A15").format = { fill: colors.grayBg, font: { name: font, bold: true, color: colors.navy }, wrapText: true };
overview.getRange("B11:H15").merge({ across: true });
body(overview, "A11:H15");

section(overview, "A17:H17", "三、需求完成情况（与“功能需求”工作表联动）");
overview.getRange("A18:H18").values = [["需求总数","已完成","部分完成","待开发","MVP 必须项","赛题指标项","当前建议","下一里程碑"]];
header(overview, "A18:H18");
overview.getRange("A19:F19").formulas = [[
  "=COUNTA('功能需求'!A5:A200)",
  "=COUNTIF('功能需求'!G5:G200,\"已完成\")",
  "=COUNTIF('功能需求'!G5:G200,\"部分完成\")",
  "=COUNTIF('功能需求'!G5:G200,\"待开发\")",
  "=COUNTIF('功能需求'!F5:F200,\"P0\")",
  "=COUNTIF('功能需求'!J5:J200,\"是\")"
]];
overview.getRange("G19:H19").values = [["先完成可验证闭环", "邮件通知 + 20例评估集 + RAG"]];
overview.getRange("A19:H19").format = { fill: colors.pale, font: { name: font, size: 12, bold: true, color: colors.navy }, rowHeight: 42, verticalAlignment: "center", horizontalAlignment: "center", wrapText: true };

section(overview, "A21:H21", "四、推荐开发顺序");
overview.getRange("A23:H27").values = [
  ["阶段 1", "补齐可演示闭环", "QQ 邮箱监护人通知、通知日志、真实报告数据", "P0", "低", "1–2 天", "未完成", "形成完整干预闭环"],
  ["阶段 2", "完成比赛评估", "20+ 黑白样本、10+诈骗类型、批量测试、F1/准确率/误报率/时延", "P0", "中", "2–4 天", "部分完成", "直接对应提交材料"],
  ["阶段 3", "增强知识检索", "案例切分、向量化、相似案例引用、来源展示", "P1", "中", "2–4 天", "部分完成", "降低模型幻觉"],
  ["阶段 4", "优化多模态体验", "浏览器录音、OCR 文字区、图片压缩、长任务状态", "P1", "中", "2–3 天", "部分完成", "提升演示稳定性"],
  ["阶段 5", "研究型增强", "合成语音辨伪基线、阈值校准、压力测试", "P2", "高", "5–10 天", "待开发", "作为创新点，不阻塞 MVP"]
];
header(overview, "A22:H22");
overview.getRange("A22:H22").values = [["阶段","目标","工作内容","优先级","难度","预计时间","当前状态","交付结果"]];
body(overview, "A23:H27");
overview.freezePanes.freezeRows(2);

title(comparison, "国家反诈中心 App 与安知项目差异对比", "官方能力依据见“来源与边界”；安知栏同时区分当前实现与规划能力。", "F");
comparison.getRange("A4:F4").values = [["对比维度","国家反诈中心 App","安知项目（当前/规划）","关键区别","安知应如何表述","风险提示"]];
header(comparison, "A4:F4");
const compRows = [
  ["建设主体与权威性","公安机关推出的官方反诈应用","学生团队开发的比赛原型","官方公共安全平台 vs 技术验证项目","定位为风险辅助与安全教育工具","不得宣传为警方官方产品"],
  ["核心目标","预警涉诈来电、短信、网址和 App；举报、身份核实、报案辅助、宣传教育","分析用户主动提交的文本、图片、音频，生成风险解释、干预建议和报告","官方治理与处置 vs 用户侧内容分析","强调“辅助判断”和“及时核实”","模型结论不能作为执法或定案依据"],
  ["数据基础","公安机关已确认涉诈线索及大数据核查的高风险信息","公开案例、自建知识库、用户提交内容、用户画像和本地历史记录","权威黑名单/治理数据 vs 公开数据/RAG","显示案例来源和分析依据","不能声称接入公安内部数据库"],
  ["输入渠道","系统级来电、短信、网址、App 风险预警及用户举报材料","文本、图片、音频上传；后续可加入浏览器录音","系统级监测 vs 主动提交","突出多模态主动检测","Web 页面无法获得手机系统级拦截权限"],
  ["诈骗预警","开启权限后对部分涉诈电话、短信、网址、App 提醒或拦截","按模型结果生成低/中/高风险和预警记录","已知涉诈线索识别 vs 内容语义推理","称为“内容风险提示”","不得使用“官方拦截成功”表述"],
  ["身份与账号核验","可提供身份核实请求及部分涉诈风险验证","无法核验真实身份、手机号、社交账号或交易账号","权威查询接口差异最大","引导用户到官方渠道核验","不得给出账号“安全认证”"],
  ["举报与报案","支持涉诈线索举报、报案助手和证据提交","可保存本地事件、导出报告；暂不向警方系统提交","官方业务受理 vs 本地记录","提供 110/96110 和国家反诈中心 App 操作指引","不可模拟“已报警成功”"],
  ["多模态理解","公开资料重点描述来电、短信、网址、App 预警与举报","LLM/VLM + Whisper 统一分析文本、截图和语音内容","安知的主要展示亮点","展示各模态证据和融合结论","语音内容识别不等于声音真伪鉴定"],
  ["个性化保护","以地区、账号及风险线索提供公共服务","按老人、学生、财会等角色及风险偏好调整提醒","安知更强调角色化交互","解释阈值变化原因","画像不能成为诈骗证据"],
  ["监护人联动","公开资料未将家庭监护人工作台作为核心能力","高风险时通知监护人并记录远程干预（规划邮件方式）","安知差异化功能","明确获得用户授权并允许撤销","涉及联系方式与隐私授权"],
  ["知识更新","举报线索经核实可进入治理与技术封堵体系；案例持续宣传","公开案例清洗入库、关键词检索，后续升级向量检索","官方闭环 vs 本地知识库维护","标注来源、版本和更新时间","未经核实案例不能当作事实"],
  ["离线与成本","依赖官方服务体系和手机权限","本地 Ollama、SQLite、Faster-Whisper，可低成本离线演示","部署资源不同","说明首次加载和本地 CPU 时延","图片分析当前约需 1–2 分钟"],
  ["效果验证","官方应用的治理效果不等同于公开可复现实验指标","须用自建 20+ 案例计算准确率、F1、误报率和时延","比赛必须自行验证","报告测试集构成和限制","不得直接引用他方准确率作为本项目指标"]
];
comparison.getRange(`A5:F${4+compRows.length}`).values = compRows;
body(comparison, `A5:F${4+compRows.length}`);
comparison.freezePanes.freezeRows(4);

title(requirements, "安知项目功能需求清单", "优先级：P0=比赛核心闭环，P1=重要增强，P2=研究或后续功能；状态按当前代码与演示结果填写。", "K");
requirements.getRange("A4:K4").values = [["编号","功能大类","子功能","用户故事 / 使用场景","功能说明","优先级","当前状态","验收标准","数据与依赖","赛题指标","备注 / 待确认"]];
header(requirements, "A4:K4");
const reqRows = [
  ["FR-001","账号与入口","模拟登录","作为普通用户，我可以用手机号和验证码进入系统","手机号、验证码模拟登录；保存本地登录状态","P1","已完成","输入合法手机号后进入仪表盘；退出后回到登录页","localStorage","否","比赛演示无需真实短信鉴权"],
  ["FR-002","账号与入口","大字号模式","作为老人，我可以放大全局字号","顶部按钮和角色设置均可开关，整体字号放大约 1.2 倍","P1","已完成","刷新页面后仍保持设置；主要页面不溢出","localStorage / CSS","否","需补移动端抽查"],
  ["FR-003","角色画像","角色设置","作为用户，我可以选择老人、儿童、青壮年或自定义角色","保存年龄、职业、性别和风险偏好","P0","已完成","保存后重开页面仍存在；分析请求携带画像","localStorage","是","画像只调整提醒，不作为证据"],
  ["FR-004","角色画像","监护人管理","作为用户，我可以维护监护人姓名、关系、邮箱/电话和默认联系人","支持添加、删除、默认通知和测试通知","P0","部分完成","至少可维护 1 名监护人；字段校验；保存后持久化","localStorage；邮件服务","是","目前主要为页面与模拟状态"],
  ["FR-005","仪表盘","安全概览","作为用户，我可以看到评分、检测次数、拦截风险和待处理预警","汇总今日/近期安全指标和最近 5 条预警","P1","已完成","指标与真实预警记录一致；无数据时显示空状态","SQLite API","否","部分图表仍需核对真实数据口径"],
  ["FR-006","文本分析","真实文本检测","作为用户，我可以粘贴可疑聊天记录并得到风险判断","本地 Ollama 分析；输出等级、类型、依据、建议和案例引用","P0","已完成","正常和诈骗文本均可提交；结果写入预警中心；错误不生成伪结论","Ollama qwen3.5:4b","是","本地首次调用可能较慢"],
  ["FR-007","图片分析","截图/VLM 检测","作为用户，我可以上传聊天截图或投资海报","后端内存缩放，VLM 识别可见文字并分析诈骗风险","P0","已完成","PNG/JPEG/WebP ≤10MB；返回识别文字、等级和建议；原图不落盘","Ollama vision / Pillow","是","当前实测约 95 秒，不满足赛题 10 秒目标"],
  ["FR-008","图片分析","独立 OCR 结果","作为用户，我可以看到截图中提取的原始文字","在 VLM 结果外增加可编辑 OCR 文本与关键词定位","P1","部分完成","显示完整 OCR 文本、关键词位置和识别失败提示","PaddleOCR 或 RapidOCR","是","当前由 VLM 返回短句，未独立 OCR"],
  ["FR-009","语音分析","语音转写","作为用户，我可以上传语音并查看时间轴文本","Faster-Whisper 本地转写，按时间段展示文本","P0","已完成","支持 WAV/MP3/M4A/AAC/OGG/WebM ≤20MB；临时文件分析后删除","Faster-Whisper","是","首次载入模型耗时较长"],
  ["FR-010","语音分析","语音内容风险判断","作为用户，我可以基于转写文本判断诱导转账等风险","转写结果进入文本风险模型并生成预警","P0","已完成","语音样本完成转写、风险判断、数据库保存","Whisper + Ollama","是","不得表述为声纹或真伪鉴定"],
  ["FR-011","语音分析","浏览器录音","作为用户，我可以直接录制一段语音进行检测","MediaRecorder 录音、预览、重录和提交","P1","待开发","允许录音授权；可试听和取消；提交与文件上传共用接口","浏览器 MediaRecorder","否","移动端需验证兼容性"],
  ["FR-012","语音分析","AI 合成语音辨伪","作为用户，我想知道声音是否疑似合成","输出疑似概率、模型版本和不确定性，不直接断言真伪","P2","待开发","使用公开数据集评估；报告 EER/AUC；结果与内容风险分开","AASIST/RawNet 基线及数据集","是","成本较高，建议作为研究型增强"],
  ["FR-013","多模态融合","联合风险结论","作为用户，我可以一次提交多种证据并得到统一结论","融合文字、图片、音频证据，避免简单取最高风险","P0","部分完成","同一事件可关联多个模态；显示各模态贡献和最终规则","事件模型 / 融合策略","是","当前各模态可分析但主要独立提交"],
  ["FR-014","风险决策","三级预警","作为用户，我可以直观看到低、中、高风险","低=绿色、中=橙色、高=红色；给出差异化操作建议","P0","已完成","所有真实分析统一等级枚举；中高风险进入待处理","模型结构化输出","是","风险等级不等同于警方认定"],
  ["FR-015","风险决策","诈骗类型识别","作为用户，我可以知道可能属于哪类诈骗","覆盖投资理财、刷单、公检法、客服退款、贷款等至少 10 类","P0","部分完成","测试集中每类至少 1 个黑样本；类型标签统一","案例库 / 提示词","是","需建立统一类型字典"],
  ["FR-016","风险决策","证据可解释","作为用户，我可以看到模型为何这样判断","引用输入片段、图片可见文字、时间轴以及相似案例","P0","已完成","所有中高风险至少展示 1 条输入证据；不得引用不存在内容","结构化 JSON 校验","是","已有证据 ID 与案例 ID 校验"],
  ["FR-017","个性化评估","画像阈值调整","作为老人或学生，我可以得到更符合自身风险的提醒","按角色、职业和风险偏好调整 needs_review 与建议语气","P1","部分完成","同一模糊样本在不同画像下允许提醒差异；证据结论不能被画像捏造","用户画像","是","需补阈值可解释说明"],
  ["FR-018","对话与记忆","历史风险摘要","作为用户，系统可以参考近期风险记录","最近 5 条同用户风险摘要进入模型上下文","P1","已完成","仅引用同一用户；不把历史事件当本次证据","SQLite","是","单机单用户原型"],
  ["FR-019","对话与记忆","多轮会话","作为用户，我可以围绕同一事件追问和补充证据","保存会话、消息与附件关系，支持继续分析","P1","部分完成","刷新后恢复会话；追加内容不丢失此前上下文","会话表 / 附件表","是","当前演示对话与真实分析分区"],
  ["FR-020","预警中心","预警列表与筛选","作为用户，我可以按等级、时间和类型查找预警","支持详情、筛选、批量处理和通知日志","P0","已完成","真实分析写入 SQLite；处理状态持久化；筛选结果正确","SQLite API","是","需继续做分页和搜索"],
  ["FR-021","预警中心","标记已处理","作为用户，我可以关闭已核实的风险事件","单条/批量标记并记录时间","P1","已完成","刷新后状态保持；仪表盘待处理数同步","SQLite API","否","保留审计日志"],
  ["FR-022","实时干预","监护人邮件通知","作为高风险用户，我可以一键通知默认监护人","使用 QQ 邮箱 SMTP 发送风险摘要和核实建议","P0","待开发","高风险详情可发送；成功/失败均记录；密钥只存后端环境变量","QQ SMTP / 授权码","是","需用户授权，禁止在聊天或前端保存授权码"],
  ["FR-023","实时干预","通知记录","作为用户，我可以查看谁在何时收到何种通知","预警详情展示接收人、渠道、时间和结果","P0","部分完成","发送成功或失败均生成日志；不可伪造已发送状态","通知日志表","是","当前主要有模拟日志"],
  ["FR-024","安全报告","报告生成","作为用户，我可以按时间范围生成风险报告","汇总风险趋势、类型分布、等级分布和建议","P0","部分完成","报告读取真实数据库；统计与预警中心一致","SQLite / Recharts","是","页面已有，需统一数据口径"],
  ["FR-025","安全报告","导出与打印","作为用户，我可以保存报告用于答辩或沟通","浏览器打印和 PDF 导出","P1","部分完成","A4 页面不截断关键图表；包含生成时间与数据范围","浏览器打印 / PDF","否","不包含原始敏感附件"],
  ["FR-026","知识库","案例上传入库","作为维护者，我可以粘贴或上传新案例","支持 TXT/JSON/CSV，清洗后保存诈骗类型、正文和来源","P0","已完成","合法文件入库；错误文件提示；条目数和更新时间同步","SQLite","是","当前以关键词检索为主"],
  ["FR-027","知识库","向量检索 RAG","作为模型，我可以找到语义相近案例辅助判断","分块、向量化、Top-K 检索、来源引用和版本管理","P0","待开发","同义表达能够召回相关案例；引用可追溯；离线评估 Recall@K","向量模型 / FAISS 或 Chroma","是","推荐 bge-small-zh 本地嵌入"],
  ["FR-028","知识库","更新日志与回滚","作为维护者，我可以查看每次知识更新","记录导入时间、来源、条目数和失败原因；支持停用错误案例","P1","部分完成","每次导入有批次号；停用后不参与检索","知识批次表","是","避免未经核实材料污染知识库"],
  ["FR-029","测试中心","标准测试集","作为团队，我可以维护不少于 20 个标准案例","黑白样本 1:1，含文本/图片/音频，黑样本覆盖 ≥10 类","P0","部分完成","案例含唯一编号、标签、模态、来源、期望结果","evaluation_cases / assets","是","已有基础资产，需补齐并审核标签"],
  ["FR-030","测试中心","批量评估","作为团队，我可以一键运行全部案例","生成混淆矩阵、准确率、Precision、Recall、F1、误报率和时延","P0","部分完成","指标公式正确；逐案例结果可导出；失败不计为正确","评估 API / 数据集","是","需完成跨模态批处理"],
  ["FR-031","测试中心","压力与稳定性测试","作为团队，我可以证明连续运行不崩溃","记录并发数、成功率、P50/P95 时延和资源占用","P1","待开发","完成约定轮次无崩溃；报告硬件和模型配置","Locust/k6/脚本","是","本地 CPU 并发能力有限"],
  ["FR-032","数据与持久化","SQLite 数据库","作为系统，我可以持久保存预警、知识条目和任务","后端 SQLite 作为本地单机数据层","P0","已完成","重启后数据仍存在；数据库初始化自动完成","SQLite / SQLAlchemy","是","比赛原型足够，生产需更强数据库"],
  ["FR-033","数据与持久化","备份与恢复","作为团队，我可以备份比赛演示数据","导出数据库及配置清单；支持一键恢复测试数据","P1","待开发","备份文件不含密钥；恢复后记录数量一致","脚本 / SQLite","否","提交前准备干净演示库"],
  ["FR-034","演示交付","一键启动","作为评委，我可以快速运行前端、后端和本地模型","批处理脚本启动 Ollama、FastAPI 和 Vite","P0","已完成","缺少依赖时给出明确提示；健康检查可访问","启动项目.bat","是","建议增加关闭脚本和端口占用提示"],
  ["FR-035","演示交付","全链路演示模式","作为答辩者，我可以稳定展示诱导—识别—预警—通知—报告","固定演示案例和步骤状态，仍标明真实/模拟能力","P0","部分完成","一次演示完整走通；每步显示耗时和结果来源","演示数据 / 邮件通知","是","避免将模拟通知说成真实短信"]
];
requirements.getRange(`A5:K${4+reqRows.length}`).values = reqRows;
body(requirements, `A5:K${4+reqRows.length}`);
requirements.freezePanes.freezeRows(4);

title(nonfunctional, "非功能需求与工程约束", "区分赛题目标、当前实测和可接受的阶段性验收，便于答辩时如实说明。", "H");
nonfunctional.getRange("A4:H4").values = [["编号","类别","需求","目标值 / 约束","当前情况","验收方法","优先级","风险与措施"]];
header(nonfunctional, "A4:H4");
const nfRows = [
  ["NFR-001","准确性","多模态融合识别准确率",">90%（赛题目标）","尚未完成标准评估","在固定 20+ 样本上计算 Accuracy 和 F1","P0","小样本容易高估；报告样本构成和置信区间"],
  ["NFR-002","误报率","正常社交误报率","<5%（赛题目标）","尚未完成标准评估","至少 10 个白样本；FP/白样本总数","P0","白样本应含转账但非诈骗等困难样本"],
  ["NFR-003","实时性","文本/图片平均响应","<10 秒（赛题目标）","文本受硬件影响；图片实测约 95 秒","分别记录平均、P50、P95；注明硬件","P0","本地 CPU 难达标；比赛可用云模型或更小模型优化"],
  ["NFR-004","稳定性","连续运行无崩溃","完成批量测试且服务不退出","基础单测通过，未完成长稳测试","连续运行 100 次；记录失败数和资源峰值","P1","增加任务队列、超时、重试和健康检查"],
  ["NFR-005","并发","多用户/多任务处理","原型至少 2–5 个并发任务可排队","当前单机同步图片/语音任务较慢","k6/Locust 并发测试","P1","比赛演示以任务队列和状态轮询为主"],
  ["NFR-006","隐私","附件处理","图片仅内存处理；语音临时文件处理后删除","已实现主要路径","检查磁盘临时目录和日志，不出现附件正文/密钥","P0","异常退出时也需清理临时文件"],
  ["NFR-007","安全","密钥和敏感配置","API Key、邮箱授权码仅存后端 .env；不提交 Git","Ollama 无云 Key；邮件尚未接入","扫描仓库；前端网络请求不含密钥","P0","曾暴露过的密钥必须吊销"],
  ["NFR-008","安全","输入与接口防护","限制类型、大小、长度和本地来源；防止提示注入","已完成部分校验","非法文件、超长文本、跨站 Origin 测试","P0","增加上传文件魔数校验和速率限制"],
  ["NFR-009","可用性","错误反馈","失败时显示原因和恢复建议，不生成伪结果","基本实现","断开 Ollama、超时、格式失败、磁盘异常测试","P0","错误信息不泄露供应商响应和敏感数据"],
  ["NFR-010","无障碍","老人友好","大字号、清晰风险色、键盘可用、颜色外文字标签","大字号已实现","键盘遍历、对比度、200%缩放检查","P1","风险不能只靠颜色表达"],
  ["NFR-011","兼容性","桌面与移动端","Chrome/Edge 最新版；常见手机宽度不横向溢出","响应式界面已实现","360/390/768/1440 px 视口抽查","P1","录音权限和 iOS 格式需单独验证"],
  ["NFR-012","可维护性","模块与配置","页面、组件、数据、服务、类型分层；模型可配置","已基本实现","构建通过、19 项后端测试通过","P1","继续补 API 契约和音频/图片测试"],
  ["NFR-013","可追溯性","分析审计","保存模型、知识版本、引用案例、证据和处理日志","已实现主要字段","抽查中高风险记录字段完整率","P0","模型升级后保留旧版本标记"],
  ["NFR-014","合规边界","结论表达","只给风险辅助建议，不声称警方认定、身份核验或真实报警","提示词与页面已有边界","检查全部页面、报告和演示文案","P0","答辩材料同样需要统一表述"]
];
nonfunctional.getRange(`A5:H${4+nfRows.length}`).values = nfRows;
body(nonfunctional, `A5:H${4+nfRows.length}`);
nonfunctional.freezePanes.freezeRows(4);

title(acceptance, "核心验收测试清单", "用于开发自测、演示彩排和最终评估。预期结果应以固定测试数据为准，不以单次主观判断代替指标。", "I");
acceptance.getRange("A4:I4").values = [["用例编号","模块","前置条件","测试步骤","测试数据","预期结果","当前结果","是否通过","证据/记录"]];
header(acceptance, "A4:I4");
const testRows = [
  ["TC-001","文本分析","Ollama 与后端运行","提交正常聊天文本","周末一起吃饭吗？","低风险；不给出虚构诈骗依据","待复测","","保存返回 JSON 和截图"],
  ["TC-002","文本分析","同上","提交冒充公检法话术","涉嫌洗钱，转入安全账户配合调查","高风险；类型为冒充公检法；建议停止转账并核实","已验证","是","预警中心记录"],
  ["TC-003","图片分析","视觉模型运行","上传聊天长截图","PNG/JPEG ≤10MB","自动缩放；返回可见文字、风险等级；写入预警","已验证，约95秒","是","image-bcdc..."],
  ["TC-004","图片校验","后端运行","上传不支持格式或超大图片","GIF / >10MB","拒绝并显示明确提示，不生成预警","待复测","","接口响应"],
  ["TC-005","语音转写","Whisper 模型可用","上传黑样本语音","black-03.wav","返回中文转写、时间段和风险分析","已验证，约56秒","是","接口结果"],
  ["TC-006","语音白样本","同上","上传正常语音","white-01.wav","低风险或合理 needs_review；不虚构转账内容","待复测","","接口结果"],
  ["TC-007","预警持久化","完成一次真实分析","刷新页面并打开预警中心","任意中高风险记录","记录仍存在；数量与仪表盘一致","已验证基础流程","是","SQLite 记录"],
  ["TC-008","批量处理","存在多条未处理预警","选择两条并标记已处理","两条预警","状态持久化；待处理数减少 2","待复测","","操作录屏"],
  ["TC-009","角色画像","保存老人/学生画像","分别提交同一模糊风险文本","固定文本","证据一致；提醒策略允许不同；不得捏造证据","待开发测试","","对比结果"],
  ["TC-010","监护人通知","配置 QQ 邮箱 SMTP","对高风险事件点击通知","测试邮箱","收到邮件；系统记录成功；失败时记录原因","待开发","","邮件与日志"],
  ["TC-011","知识入库","准备 TXT/JSON/CSV","上传案例并清洗入库","公开案例","条目数增加；类型、来源、时间完整","待复测","","知识库列表"],
  ["TC-012","RAG 引用","完成向量检索","提交同义诈骗话术","不含完全相同关键词","召回正确类型案例；返回可追溯来源","待开发","","Recall@K 结果"],
  ["TC-013","报告生成","数据库有多类预警","选择时间范围生成报告","最近7天","折线、饼图、柱图与数据库统计一致","待复测","","报告截图"],
  ["TC-014","报告打印","已生成报告","打印/导出 PDF","A4","标题、图表、建议不截断；无敏感附件","待复测","","PDF 文件"],
  ["TC-015","20例评估","标准测试集完成","运行全部案例","10黑+10白，≥10诈骗类型","生成 Accuracy、Precision、Recall、F1、FPR、时延","待开发","","评估报告"],
  ["TC-016","容错","关闭 Ollama","提交文本/图片","任意输入","显示服务不可用；不生成伪预警","基础路径已实现","是","错误响应"],
  ["TC-017","隐私","完成图片和语音分析","检查项目与临时目录","真实附件","图片不落盘；语音临时文件已删除","待审计","","目录检查记录"],
  ["TC-018","一键启动","关闭全部服务","双击启动项目.bat","本机环境","Ollama、后端、前端启动；健康检查成功","已完成","是","启动窗口/health"]
];
acceptance.getRange(`A5:I${4+testRows.length}`).values = testRows;
body(acceptance, `A5:I${4+testRows.length}`);
acceptance.freezePanes.freezeRows(4);

title(sources, "资料来源、假设与产品边界", "国家反诈中心 App 功能以政府及公安机关公开资料为依据；公开页面可能随版本更新。", "F");
sources.getRange("A4:F4").values = [["编号","资料名称","发布/维护单位","支持的事实","链接","备注"]];
header(sources, "A4:F4");
const sourceRows = [
  ["S-01","国家反诈中心 APP 使用说明","玉溪市人民政府","来电预警、举报、身份核实、App 自检、报案助手、防诈知识","https://www.yuxi.gov.cn/yxszfxxgk/slcjzdlygkzl/20230810/1502522.html","政府公开页面"],
  ["S-02","国家反诈中心 APP 应用详情","眉山市公共数据开放网","预警诈骗信息、快速举报、报案助手、骗局曝光；页面更新于 2025-06-10","https://data.ms.gov.cn/portal/app_detail?id=ff8080819757ff16019758dd5c3f0007&orgId=77b7beedc2ee4bcc9a4b89583fbd1ba9","用于核对当前公开定位"],
  ["S-03","国家反诈中心 App 主要功能","苏州市公安局","涉诈电话/短信/网址预警、一键举报、风险验证、案例学习","https://gonganju.suzhou.gov.cn/gaj/zxft/202501/9362a78466a94006801d13192395267c.shtml","公安机关公开资料"],
  ["S-04","藏在国家反诈中心 APP 里的秘密","福建省公安厅","预警、举报、交易账号风险查询、身份核实、快速报案","https://gat.fujian.gov.cn/ztzl/fjjffpzxrx/yjxx/202309/t20230913_6255881.htm","公安机关公开资料"],
  ["S-05","国家反诈中心 App 功能介绍","无锡市人民政府","预警数据来自已确认涉诈线索和大数据核查高风险信息；举报线索可纳入黑样本库","https://wjw.wuxi.gov.cn/doc/2021/11/17/3496838.shtml","用于说明数据权威性差异"],
  ["S-06","反诈国家队七大反诈利器","工业和信息化部系统","国家反诈中心 App 与 96110、12381 等国家反诈体系协同","https://tjca.miit.gov.cn/zwgk/wlaqgl/art/2023/art_117628b2c6154990a31d9f886e9a1028.html","用于说明官方体系能力"],
  ["S-07","A30 基于多模态的反诈智能助手赛题","中国大学生服务外包创新创业大赛","多模态输入、识别决策、干预、进化、指标和提交材料","https://fwwb.org.cn/topic/show/106d4f6e-db29-4ac4-9849-46c26f95ccbf","项目需求来源"],
  ["S-08","安知现有代码与本地验证","项目代码仓库","Ollama、图片 VLM、Faster-Whisper、SQLite、前端页面与测试结果","本地项目记录","截至 2026-09-23"]
];
sources.getRange(`A5:F${4+sourceRows.length}`).values = sourceRows;
body(sources, `A5:F${4+sourceRows.length}`);
section(sources, `A${6+sourceRows.length}:F${6+sourceRows.length}`, "产品表述边界");
const b = 7 + sourceRows.length;
sources.getRange(`A${b}:F${b+5}`).values = [
  ["B-01","不得使用","“接入公安数据库”“官方认证安全”“已向警方报警”“可替代国家反诈中心 App”","原因","当前项目不具备官方数据、接口和执法权限",""],
  ["B-02","建议使用","“基于公开案例和本地模型的风险辅助分析”“建议通过官方渠道核实”","原因","与实际能力和证据边界一致",""],
  ["B-03","语音边界","当前已实现语音转写和内容风险分析，尚未实现可靠的 AI 合成语音鉴伪","展示方式","把“内容风险”和“声音真实性”分成两个结果",""],
  ["B-04","指标边界","准确率、F1、误报率必须来自本项目固定测试集","展示方式","同时披露样本数量、类别、模态和硬件配置",""],
  ["B-05","数据边界","仅使用公开案例、合成测试数据或取得授权的数据","展示方式","保存来源、版本和更新时间；支持停用错误案例",""],
  ["B-06","通知边界","邮件通知必须获得用户授权，通知结果以真实发送日志为准","展示方式","发送失败不可显示“已通知”",""],
];
body(sources, `A${b}:F${b+5}`);
sources.freezePanes.freezeRows(4);

// Column sizing and row heights.
const widths = {
  "项目总览": [13,18,26,10,10,12,15,20],
  "差异对比": [16,31,34,27,29,26],
  "功能需求": [10,14,18,28,34,9,12,38,24,10,28],
  "非功能需求": [10,12,23,24,23,30,9,30],
  "验收测试": [11,14,20,28,24,36,18,10,24],
  "来源与边界": [10,25,20,42,52,24]
};
for (const [name, arr] of Object.entries(widths)) {
  const sh = wb.worksheets.getItem(name);
  arr.forEach((w, i) => sh.getRangeByIndexes(0, i, Math.max(1, sh.getUsedRange().rowCount), 1).format.columnWidth = w);
  sh.getUsedRange().format.autofitRows();
  sh.getRange("1:2").format.rowHeight = 34;
}

// Status colors in the two operational sheets.
for (let r=5; r<=4+reqRows.length; r++) {
  const cell = requirements.getRange(`G${r}`);
  const value = reqRows[r-5][6];
  cell.format.fill = value === "已完成" ? colors.greenBg : value === "部分完成" ? colors.amberBg : colors.redBg;
  cell.format.font = { name: font, bold: true, color: value === "已完成" ? colors.green : value === "部分完成" ? colors.amber : colors.red };
}

wb.recalculate();
const check = await wb.inspect({ kind: "sheet", include: "id,name", maxChars: 3000 });
console.log(check.ndjson);
const preview = await wb.render({ sheetName: "项目总览", autoCrop: "all", scale: 1, format: "png" });
await fs.writeFile("D:/Desktop/外包A30/anti-fraud/.artifact_tmp/requirements-preview.png", new Uint8Array(await preview.arrayBuffer()));
const comparisonPreview = await wb.render({ sheetName: "差异对比", range: "A1:F17", scale: 0.8, format: "png" });
await fs.writeFile("D:/Desktop/外包A30/anti-fraud/.artifact_tmp/comparison-preview.png", new Uint8Array(await comparisonPreview.arrayBuffer()));
const requirementPreview = await wb.render({ sheetName: "功能需求", range: "A1:K15", scale: 0.7, format: "png" });
await fs.writeFile("D:/Desktop/外包A30/anti-fraud/.artifact_tmp/functional-preview.png", new Uint8Array(await requirementPreview.arrayBuffer()));
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(outFile);
console.log(outFile);
