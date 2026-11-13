const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const tabs=await(await fetch('http://127.0.0.1:9231/json/list')).json();
 const tab=tabs.find(t=>t.url.startsWith('http://127.0.0.1:8095/'));assert.ok(tab);
 const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);
 let id=0;const jobs=new Map();ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id){jobs.get(d.id)?.(d);jobs.delete(d.id);}};
 const call=(method,params={})=>new Promise(r=>{jobs.set(++id,r);ws.send(JSON.stringify({id,method,params}));});
 try{
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  const fixture=JSON.parse(fs.readFileSync(__dirname+'/qa/fraud-regression-live.json','utf8'))[0].response.result;
  const response=await call('Runtime.evaluate',{expression:`(()=>{const result=${JSON.stringify(fixture)};const bubble=message('QA真实响应渲染验证');facts(bubble,result);if(!bubble.querySelector('h3').textContent.includes('信息不足'))throw Error('review title missing');if(!fraudReportText(result).includes('风险：信息不足，待核实'))throw Error('export mislabels review');document.dispatchEvent(new CustomEvent('agent-execution-failure',{detail:{error:'QA模拟服务失败',executionTrace:[{label:'委派领域服务',status:'failed',detail:'QA失败阶段'}]}}));if(!document.querySelector('.agent-execution-trace[open]'))throw Error('failure trace not expanded');if(document.documentElement.scrollWidth>innerWidth)throw Error('horizontal overflow');return 'Review title, export, expanded failure trace and mobile width passed';})()`,returnByValue:true});
  if(response.result.exceptionDetails)throw Error(JSON.stringify(response.result.exceptionDetails));
  console.log(response.result.result.value);
 }finally{await call('Browser.close');ws.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
