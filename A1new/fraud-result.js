'use strict';
// Pure validation shared by the browser and offline tests. No inference or fallback verdicts.
function validateFraudResult(value){
 if(!value||typeof value!=='object'||Array.isArray(value))return '分析结果格式无效';
 if(value.origin!=='backend')return '结果不是后端真实分析返回';
 if(typeof value.model!=='string'||!value.model.trim())return '未返回可核对的模型名称';
 if(typeof value.type!=='string'||!value.type.trim())return '未返回完整分析类型';
 if(!['high','medium','low'].includes(value.level))return '未返回有效风险等级';
 if(!['assessed','needs_review'].includes(value.assessment))return '未返回完整评估状态';
 if(value.level==='low'&&value.assessment==='needs_review')return '风险等级与待核实状态不一致';
 if(typeof value.evidence!=='string'||!value.evidence.trim())return '未返回有效分析依据';
 if(!Array.isArray(value.advice)||!value.advice.length||value.advice.some(x=>typeof x!=='string'||!x.trim()))return '未返回完整处理建议';
 if(!Array.isArray(value.evidenceItems)||!value.evidenceItems.length||value.evidenceItems.some(x=>!x||typeof x.excerpt!=='string'||!x.excerpt.trim()))return '未返回可核对的原文证据';
 if(value.sources!=null&&(!Array.isArray(value.sources)||value.sources.some(x=>!x||typeof x!=='object')))return '参考来源格式无效';
 return null;
}
function fraudFollowupText(result,limit=2000){
 const original=typeof result.summary==='string'?result.summary.trim():'';
 const evidence=(result.evidenceItems||[]).map(x=>x.excerpt).filter(x=>typeof x==='string').join('\n');
 const text='请结合完整原文重新分析。\n原文：\n'+(original||evidence)+'\n\n补充信息：';
 return text.length<=limit?{text,tooLong:false}:{text:'请粘贴需要重新核对的完整原文，并补充信息：',tooLong:true};
}
if(typeof module!=='undefined'&&module.exports)module.exports={validateFraudResult,fraudFollowupText};
