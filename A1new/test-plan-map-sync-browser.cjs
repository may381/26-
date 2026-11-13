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
  for(let attempt=0;attempt<40;attempt++){const ready=await call('Runtime.evaluate',{expression:'typeof openPlanSheet',returnByValue:true});if(ready.result.result.value==='function')break;await new Promise(r=>setTimeout(r,250));}
  const fixture=JSON.parse(fs.readFileSync(__dirname+'/qa/native-plan-save-restore-live.json','utf8')).restored;
  const response=await call('Runtime.evaluate',{expression:`(()=>{const draft=${JSON.stringify(fixture)};let seen=null;mountInteractiveMap=(root,place,scope)=>{seen=scope;};openPlanSheet(draft,{textContent:''});const d=document.querySelector('dialog.plan-detail-sheet');if(!d)throw Error('plan missing');d.querySelectorAll('.plan-date-tabs button')[1].click();if(seen.days.length!==1||seen.days[0].date!==draft.days[0].date)throw Error('day scope wrong');const updated=structuredClone(draft);updated.version++;updated.days[0].places.reverse();d.dispatchEvent(new CustomEvent('plan-saved',{detail:updated}));if(seen.version!==updated.version||seen.days[0].places[0].id!==updated.days[0].places[0].id)throw Error('saved map stale');d.close();return 'Selected-day scope and saved plan map synchronization passed';})()`,returnByValue:true});
  if(response.result.exceptionDetails)throw Error(JSON.stringify(response.result.exceptionDetails));
  console.log(response.result.result.value);
 }finally{await call('Browser.close');ws.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
