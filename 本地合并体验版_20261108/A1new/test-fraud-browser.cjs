// Isolated browser QA. Fixture responses never reach the user preview or school server.
const assert=require('node:assert/strict');
(async()=>{
 const tabs=await(await fetch('http://127.0.0.1:9230/json/list')).json();const tab=tabs.find(t=>t.url.startsWith('http://127.0.0.1:8095/'));assert.ok(tab,'Preview page available');
 const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});let id=0;const jobs=new Map();ws.onmessage=e=>{const data=JSON.parse(e.data);if(data.id){const job=jobs.get(data.id);if(job){clearTimeout(job.timer);jobs.delete(data.id);data.error?job.reject(Error(data.error.message)):job.resolve(data.result);}}};
 function call(method,params={}){return new Promise((resolve,reject)=>{const n=++id;const timer=setTimeout(()=>{jobs.delete(n);reject(Error('CDP timeout '+method));},12000);jobs.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params}));});}
 async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;}
 try{
 await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 console.log(await evaluate(`(async()=>{
 const check=(value,name)=>{if(!value)throw Error(name);};const wait=()=>new Promise(r=>setTimeout(r,60));window.confirm=()=>true;
 check(typeof validateFraudResult==='function','validation script loaded');
 let calls=[],mode='queued';const fixture={origin:'backend',level:'high',assessment:'assessed',type:'QA测试类型',evidence:'QA测试解释，不是真实分析',advice:['QA测试建议'],evidenceItems:[{excerpt:'<img src=x onerror=alert(1)>测试原文'}],sources:[],summary:'QA完整原文',model:'QA-MOCK'};
 window.fetch=async(url,options)=>{const body=JSON.parse(options?.body||'{}');calls.push({url,body});if(url==='/api/reset')return new Response(JSON.stringify({state:'READY'}),{status:200});if(mode==='image-fail')return new Response(JSON.stringify({error:'QA学校模型不可达'}),{status:502});if(mode==='queued')return new Response(JSON.stringify({domain:'fraud',state:'WAIT_RESULT',domainResult:{state:'ACCEPTED'}}),{status:200});return new Response(JSON.stringify({domain:'fraud',domainResult:fixture}),{status:200});};
 document.querySelector('.topics [data-topic="fraud"]').click();check(!fraudToolbar.hidden&&travelToolbar.hidden,'fraud toolbar selected');
 $('question').value='QA完整原文';$('composer').requestSubmit();await wait();check(pending,'queued request pending');check(calls.length===1,'one submission');check(lastFraudInput.text==='QA完整原文','original captured before clearing');clearTimeout(pollTimer);
 display({domainResult:{status:'completed',result:fixture}});check(!pending,'completion unlocks');check(document.querySelectorAll('.fraud-report').length===1,'report rendered');check(!document.querySelector('.fraud-evidence img'),'evidence rendered as inert text');
 [...document.querySelectorAll('.fraud-report-actions button')].find(b=>b.textContent==='补充信息再分析').click();check($('question').value.includes('QA完整原文'),'follow-up preserves original');
 display({domainResult:{status:'completed',result:{...fixture,evidenceItems:[]}}});check(document.querySelectorAll('.fraud-report').length===1,'invalid result creates no verdict');
 mode='image-fail';image='data:image/png;base64,iVBORw0KGgo=';$('question').value='QA图片附言';$('composer').requestSubmit();await wait();check(image!==null&&!$('attachment').hidden,'failed image retained');check($('question').value==='QA图片附言','failed text retained');
 display({domainResult:{status:'failed',error:'QA失败'}});[...fraudProgress.querySelectorAll('button')][0].click();check($('question').value==='QA图片附言','failed job restore');
 mode='completed';recoverFraudTask.click();await wait();check(calls.at(-1).url==='/api/status','recovery only queries original task');check(document.querySelectorAll('.fraud-report').length===2,'recovery renders completed original result');await reset();check(history.length===0,'history cleared');check(lastFraudInput===null,'private input cleared');check(!pending&&!image,'pending and image cleared');check(!document.querySelector('.fraud-report'),'report removed');
 document.querySelector('.topics [data-topic="tourism"]').click();check(fraudToolbar.hidden&&!travelToolbar.hidden,'travel toolbar restored');check(document.documentElement.scrollWidth<=innerWidth,'no horizontal overflow');
 return '15 browser flow checks passed (QA fixtures only)';
})()`));
 }finally{await call('Browser.close').catch(()=>{});ws.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1});
