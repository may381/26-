import { Workbook, SpreadsheetFile } from "file:///C:/Users/dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";
const out="D:/Desktop/外包A30/anti-fraud/项目方案/安知与国家反诈中心APP对比.xlsx";
const wb=await Workbook.create();
const border="#D9D9D9", header="#F2F2F2", text="#222222";
function setup(ws,widths){ws.showGridLines=false;for(const [c,w] of Object.entries(widths))ws.getRange(`${c}:${c}`).format.columnWidth=w;}
function title(ws,range,val){const r=ws.getRange(range);r.merge();r.values=[[val]];r.format={fill:"#FFFFFF",font:{bold:true,color:text,size:15},horizontalAlignment:"left",verticalAlignment:"center",borders:{bottom:{style:"medium",color:"#666666"}}};r.format.rowHeight=32;}
function head(ws,range){ws.getRange(range).format={fill:header,font:{bold:true,color:text,size:10},wrapText:true,horizontalAlignment:"center",verticalAlignment:"center",borders:{preset:"all",style:"thin",color:border}};ws.getRange(range).format.rowHeight=28;}
function body(ws,range){ws.getRange(range).format={font:{color:text,size:10},wrapText:true,verticalAlignment:"top",borders:{preset:"all",style:"thin",color:border}};}
const rows=[
["产品定位","官方全民反诈工具，依托公安体系提供预警、举报、核验、报案和宣传","内容分析型反诈助手，分析用户提交的聊天、截图、语音和视频","互补关系：官方负责通信和线索防护，安知负责内容理解"],
["主要服务对象","面向社会公众，强调实名注册和系统权限","个人、家庭、学校和社区，可按角色配置提醒","安知适合私有化和场景化试验"],
["触发方式","来电、短信、网址、应用等系统级风险预警；用户也可主动举报或查询","用户主动粘贴文本、上传截图、音频或视频","安知关注用户手里正在看到的具体内容"],
["主要分析对象","涉诈电话、短信、网址、应用、社交账号、支付账号等风险线索","对话内容、诈骗话术、宣传图片、语音转写和多模态证据","安知从“是否涉诈”进一步解释“为什么可疑”"],
["文本能力","预警、风险查询、举报和宣传内容","逐段理解聊天记录，提取诱导、转账、身份冒充等话术","安知强调逐句解释和证据摘录"],
["图片能力","可作为举报或案件线索材料提交","OCR提取聊天截图、付款提示和宣传图中的文字并分析","图片被转化为可引用的风险证据"],
["音频能力","主要依托来电预警和官方劝阻体系","音频转写后识别语音中的诈骗话术；后续可扩展声学鉴伪","面向语音消息和录音材料"],
["视频能力","不作为本项目主要对比范围","后续可通过关键帧、音轨转写和内容分析扩展","当前作为增强能力"],
["多模态融合","公开功能重点是预警、举报、风险查询和宣传","文本、OCR和音频转写统一成证据对象后综合决策","多模态融合是安知的核心创新点"],
["风险依据","官方风险数据、预警体系、用户举报和核验能力","本地模型、规则引擎、反诈知识库和相似案例检索","安知必须清楚标注模型依据和能力边界"],
["结果输出","风险提示、查询结果、举报入口、报案入口、宣传内容","低/中/高风险、诈骗类型、置信度、证据、相似案例和防御建议","安知更适合辅助理解和教学"],
["个性化能力","面向全民的统一官方服务","老人、儿童、青壮年、自定义角色和风险偏好","角色只调整提醒方式，不改变事实风险"],
["监护人联动","主要面向本人预警、举报和报案","高风险后通知监护人，监护人查看事件并反馈处置状态","安知增加家庭协同干预闭环"],
["知识内容","官方统一发布反诈宣传和权威案例","可上传公开案例和本地案例，清洗、去重、向量化后用于RAG","安知支持学校、社区和企业私有案例库"],
["部署形态","官方移动App，需要实名注册和系统级权限","当前为响应式Web，可本地部署；后续可PWA、App或小程序","安知适合快速迭代和私有化部署"],
["隐私方式","按官方App的实名、权限和隐私机制运行","默认本地模型和本地数据库，密钥只放后端，可清理媒体文件","本地原型不应包装成官方服务"],
["执法能力","可连接官方预警、举报、报案和劝阻体系","不具备报警、止付、冻结、追回和执法权限","高风险时仍需拨打110或96110"],
["适合展示的场景","全民安装、来电预警、风险查询、举报和报案","聊天截图/语音提交→证据提取→风险解释→通知监护人","答辩突出内容层和家庭闭环"],
["项目关系","官方底层防线和权威处置渠道","官方防线之上的内容理解与家庭协同补充","不是替代，而是互补"]
];
const ws=wb.worksheets.add("功能对比");setup(ws,{A:18,B:46,C:52,D:42});title(ws,"A1:D1","安知与国家反诈中心 App 功能对比");ws.getRange("A2:D2").merge();ws.getRange("A2").values=[["说明：本表用于项目需求分析、详细方案和答辩材料。安知不替代国家反诈中心 App。"]];ws.getRange("A4:D4").values=[["对比维度","国家反诈中心 App","安知多模态反诈智能助手","项目结论"]];head(ws,"A4:D4");ws.getRange(`A5:D${4+rows.length}`).values=rows;body(ws,`A5:D${4+rows.length}`);ws.freezePanes.freezeRows(4);ws.tables.add(`A4:D${4+rows.length}`,true,"ComparisonTable");
const layers=[["通信与账号层","国家反诈中心 App","电话、短信、网址、应用、账号预警和风险查询","官方数据和系统权限","官方主防线"],["内容理解层","安知","聊天文本、截图、语音和视频内容分析","本地模型、OCR、Whisper、RAG","项目创新层"],["家庭干预层","安知","高风险通知监护人并记录处置结果","监护人档案、通知日志、确认Token","项目闭环层"],["执法处置层","公安、银行、96110、110","报警、劝阻、止付、冻结和案件处理","官方渠道和执法权限","安知只能引导" ]];
const wl=wb.worksheets.add("防护分层");setup(wl,{A:18,B:26,C:58,D:38,E:18});title(wl,"A1:E1","反诈防护分层关系");wl.getRange("A4:E4").values=[["防护层","对应系统","主要能力","依赖","项目定位"]];head(wl,"A4:E4");wl.getRange(`A5:E${4+layers.length}`).values=layers;body(wl,`A5:E${4+layers.length}`);wl.freezePanes.freezeRows(4);wl.tables.add(`A4:E${4+layers.length}`,true,"LayerTable");
const points=[["核心差异","国家反诈中心 App 防护已知风险对象；安知分析尚未进入黑名单的对话内容。","“国家反诈中心 App 看对象，安知看内容。”"],["多模态差异","安知将文本、截图OCR、语音转写和后续视频证据统一分析。","强调内容证据融合，不宣称替代官方数据库。"],["家庭闭环","安知高风险后通知监护人并保留处置记录。","展示“识别—预警—监护人确认”完整链路。"],["知识库差异","安知可以导入学校、社区或企业自己的案例库进行RAG检索。","强调可进化和私有化部署。"],["能力边界","安知不能报警、冻结资金、阻断通话或确认绝对真伪。","发现高风险后引导拨打110/96110并人工核实。"]];
const wp=wb.worksheets.add("答辩要点");setup(wp,{A:18,B:72,C:52});title(wp,"A1:C1","答辩要点与标准表述");wp.getRange("A4:C4").values=[["主题","建议表述","补充说明"]];head(wp,"A4:C4");wp.getRange(`A5:C${4+points.length}`).values=points;body(wp,`A5:C${4+points.length}`);wp.freezePanes.freezeRows(4);wp.tables.add(`A4:C${4+points.length}`,true,"DefenseTable");
const src=wb.worksheets.add("参考来源");setup(src,{A:24,B:100});title(src,"A1:B1","参考来源");src.getRange("A4:B4").values=[["来源","链接"]];head(src,"A4:B4");src.getRange("A5:B7").values=[["司法部智慧普法平台","https://legalinfo.moj.gov.cn/zhfxfzzx/fzzxyw/202506/t20250619_521225.html"],["苏州市公安局在线访谈","https://gonganju.suzhou.gov.cn/gaj/zxft/202501/9362a78466a94006801d13192395267c.shtml"],["福建省公安厅反诈宣传","https://gat.fj.gov.cn/ztzl/fjjffpzxrx/yjxx/202309/t20230913_6255881.htm"]];body(src,"A5:B7");src.freezePanes.freezeRows(4);
await wb.recalculate();for(const s of ["功能对比","防护分层","答辩要点","参考来源"])await wb.inspect({kind:"table",sheetId:s,range:"A1:D12",include:"values,formulas",tableMaxRows:12,tableMaxCols:6});const x=await SpreadsheetFile.exportXlsx(wb);await x.save(out);console.log(`saved ${out}`);
