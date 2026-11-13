'use strict';
let travelDraft=null,travelWizard=null,travelEpoch=0;
const draftDialog=document.querySelector('#draft-dialog');
const planDateLocal=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date());
function node(tag,text,cls){const element=document.createElement(tag);if(text)element.textContent=text;if(cls)element.className=cls;return element;}
function choiceButton(text,action){const b=node('button',text);b.type='button';b.onclick=action;return b;}
function wizardStart(destination=''){
 if(savingDraft){showToast('正在保存草案，请完成后再开始新计划');return;}if(busy)return;travelEpoch++;travelWizard={destination,startDate:planDateLocal(),days:2,walkMinutes:40,companions:'独自出游',avoidSteps:true,restFrequency:'standard',travelMode:'transit',pace:'steady',step:0,importedPlaceIds:(window.pendingImportedPlaces||[]).map(p=>p.id)};window.pendingImportedPlaces=null;
 const savedPreferences=readTravelPreferences();if(savedPreferences){Object.assign(travelWizard,savedPreferences);travelWizard.pace={20:'slow',40:'steady',60:'active'}[savedPreferences.walkMinutes];}
 message(destination?'帮我准备去'+destination+'的出游计划':'帮我准备出游计划',{mine:true});
 showWizard();input.value='';resizeInput();closeMore();closeSidebar();
}
window.beginPlanFromText=text=>{if(!/计划|行程安排|几日游|几天游/.test(text)||/取消|不想|不要/.test(text))return false;let destination=text.match(/(?:想去|计划去|去)([\p{Script=Han}]{2,15}?)(?:旅游|游玩|旅行|[，,。！!]|$)/u)?.[1]||'';wizardStart(destination);return true;};
const QUESTIONS=[
 {key:'companions',title:'同行的是谁？',items:[['独自出游','🎒','独自出游'],['家人同行','👨‍👩‍👧','家人同行（每天少安排一些）'],['朋友同行','🧑‍🤝‍🧑','朋友同行']]},
 {key:'restFrequency',title:'希望多久休息一次？',items:[['frequent','🪑','多休息，约每20分钟'],['standard','🍵','走走歇歇，约每40分钟'],['rare','🥾','体力较好，约每60分钟']]},
 {key:'days',title:'1. 这次打算玩几天？',items:[[1,'🌱','轻松 1 天（走马观花，当天来回）'],[2,'🚶','推荐 2 天（不紧不慢，能睡午觉）'],[3,'🌄','悠闲 3 天（一天只去一两个地方）'],[4,'🧳','深度 4 天（慢慢住，慢慢看）']]},
 {key:'travelMode',title:'2. 主要用什么交通方式？',items:[['transit','🚌','步行 + 公共交通（不自驾也到得了）'],['taxi','🚕','打车或家人接送（门到门，最省力）'],['self-drive','🚗','自驾出行（时间最灵活）']]},
 {key:'pace',title:'3. 更看重哪种行程节奏？',apply:(v,s)=>{s.walkMinutes={slow:20,steady:40,active:60}[v]||40;},items:[['slow','🍃','慢节奏休闲，不赶景点（一天一两处）'],['steady','🚶','走走歇歇，常规节奏（适量安排）'],['active','🥾','徒步为主，多看几处（体力较好）']]},
 {key:'avoidSteps',title:'4. 要不要避开台阶？',items:[[true,'🪜','尽量避开台阶（优先平缓、少爬升）'],[false,'⛰️','台阶不介意（可以爬坡、登高看景）']]}
];
function showWizard(){
 const state=travelWizard;if(!state)return;
 const questions=['您想去哪个城市？','打算什么时候出发？','我再确认几件事，就能把行程搭起来。'];
 const row=message(questions[state.step],{meta:'出游准备 · 第 '+(state.step+1)+' 步，共 3 步'});
 const card=node('section',null,'wizard-card');row.querySelector('.message-content').append(card);
 const cancel=choiceButton('取消准备',()=>{card.replaceChildren(node('p','已取消，可以继续聊天。'));travelWizard=null;});cancel.className='wizard-cancel';
 if(state.step===0){const label=node('label','目的地城市');const destination=node('input');destination.value=state.destination;destination.placeholder='例如：北京、阳江';destination.maxLength=40;destination.setAttribute('aria-label','目的地城市');card.append(label,destination);const next=choiceButton('下一步',()=>{if(!destination.value.trim()){destination.focus();return;}if(state.importedPlaceIds.length&&state.destination.replace(/市$/,"").trim()!==destination.value.trim().replace(/市$/,"")){if(!confirm("更换目的地将清除当前导入地点，并按新城市重新查找。是否继续？"))return;state.importedPlaceIds=[];}state.destination=destination.value.trim();state.step=1;card.replaceChildren(node('p','目的地：'+state.destination));message(state.destination,{mine:true});showWizard();});next.className='wizard-primary';card.append(next);}
 if(state.step===1){renderTravelDates(state,card);}

 if(state.step===2){
  const quiz=node('section',null,'question-card');
  for(const question of QUESTIONS.filter(q=>q.key!=='days'||!state.dateConfirmed)){
   const block=node('div',null,'question-block');
   block.append(node('p',question.title,'question-title'));
   const rows=node('div',null,'answer-rows');
   for(const [value,emoji,label] of question.items){
    const b=choiceButton('');b.className='answer-row';b.setAttribute('aria-pressed',String(state[question.key]===value));
    const face=node('span','','option-emoji');face.textContent=emoji;
    const text=node('span',label,'option-text');
    b.append(face,text,node('span','','radio'));
    b.onclick=()=>{state[question.key]=value;question.apply?.(value,state);
      rows.querySelectorAll('.answer-row').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));};
    rows.append(b);
   }
   block.append(rows);quiz.append(block);
  }
  const actions=node('div',null,'wizard-actions');
  const skip=choiceButton('跳过',()=>echoAnswers(state,card));
  skip.className='btn-skip';
  const confirm=choiceButton('确认',()=>echoAnswers(state,card));
  confirm.className='btn-confirm';
  actions.append(skip,confirm);
  quiz.append(node('p','这是出游建议草案，不会自动开始游览或订票。','wizard-note'),actions);
  card.append(quiz);cancel.textContent='取消准备';
 }
 card.append(cancel);toLatest();
}
function echoAnswers(state,card){
 const lines=[];
 for(const question of QUESTIONS){
  const picked=question.items.find(([value])=>value===state[question.key]);
  if(picked)lines.push('问：'+question.title.replace(/^\d+\.\s*/,''),'答：'+picked[1]+' '+picked[2]);
 }
 if(!state.restFrequency)state.restFrequency='standard';
 const echo=message(lines.join('\n'),{mine:true});
 const echoText=echo.querySelector('.bubble');if(echoText)echoText.classList.add('qa-echo');
 card.replaceChildren(node('p','已确认：'+state.destination+'，'+state.startDate+' 出发。'));
 createTravelDraft(state,card);
}
function travelDraftRequest(state){
 const {destination,startDate,days,walkMinutes,companions,avoidSteps,restFrequency,travelMode,pace,importedPlaceIds}=state;
 return {destination,startDate,days,walkMinutes,companions,avoidSteps,restFrequency,travelMode,pace,importedPlaceIds};
}
async function createTravelDraft(state,card){
 if(busy||travelWizard!==state)return;const epoch=travelEpoch;setBusy(true);card.querySelectorAll('button').forEach(b=>b.disabled=true);
 const row=message('正在准备您的出游草案…',{meta:'实际查询进度'});row.classList.add('draft-loading');row.querySelector('.bubble').setAttribute('role','status');row.querySelector('.bubble').setAttribute('aria-live','polite');row.querySelector('.message-footer')?.remove();const trace=document.createElement('details');trace.className='execution-trace';trace.open=true;const traceSummary=node('summary','正在查询地点…'),traceList=node('div');trace.append(traceSummary,traceList);row.querySelector('.message-content').append(trace);let success=false;
 try{const request=travelDraftRequest(state);const controller=new AbortController();const stop=choiceButton('停止查询',()=>controller.abort());trace.append(stop);
 const response=await fetch('/api/a1/travel-drafts/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.any([controller.signal,AbortSignal.timeout(180000)])});
 if(!response.ok){const error=await response.json();throw new Error(error.message||'请求失败');}
 const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',result=null;
 while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let split;
 while((split=buffer.indexOf('\n\n'))!==-1){const event=buffer.slice(0,split).replace(/\r/g,'');buffer=buffer.slice(split+2);const type=event.match(/^event:(.*)$/m)?.[1]?.trim();const payload=event.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5)).join('\n');if(!payload)continue;const data=JSON.parse(payload);
 if(type==='progress'){row.querySelector('.bubble').textContent=data.message;traceSummary.textContent=data.message;traceList.append(node('p',data.message));toLatest();}else if(type==='result')result=data;else if(type==='failure')throw new Error(data.message);}}
 if(!result||result.code!=='OK')throw new Error('查询未完成，请重试。');stop.remove();traceSummary.textContent='地点查询与草案整理完成';trace.open=false;
 if(epoch!==travelEpoch)return;
 travelDraft=result.data;travelWizard=null;success=true;row.querySelector('.bubble').textContent='已完成地点查询，下面是出游建议。';card.replaceChildren(node('p','已确认：'+state.destination+'，'+state.startDate+'出发，'+state.days+'天，'+state.companions+'。'));
 const answer=message((state.importedPlaceIds?.length?'已使用您确认的攻略地点，按日期整理成待调整草案。':'根据高德查到的地点，我先整理了一份可调整的慢游草案。')+'地点次序尚未按真实交通路线优化，台阶、休息点和开放状态需要进一步核实。',{meta:'高德地点资料 · 建议草案'});
 renderDraftCard(answer.querySelector('.message-content'),travelDraft);document.querySelector('.topbar-title').firstChild.textContent=state.destination+'出游计划';
 }catch(error){row.querySelector('.bubble').textContent=error.name==='AbortError'?'本次生成已停止。':'本次草案未生成成功，请重试。';traceSummary.textContent=error.name==='AbortError'?'查询已停止':'生成失败';trace.open=true;trace.querySelector('button')?.remove();const retry=choiceButton('重新生成',()=>{if(busy||travelWizard!==state)return;retry.remove();row.remove();createTravelDraft(state,card);});trace.append(retry);traceList.append(node('p',error.name==='AbortError'?'已停止接收本次结果，未执行草案保存操作。':error.name==='TimeoutError'?'地点查询超时，请重试。':error.message));}finally{row.classList.remove('draft-loading');setBusy(false);if(!success)card.querySelectorAll('button').forEach(b=>b.disabled=false);}
}
const pad2=n=>String(n).padStart(2,'0');
function clockAt(total){const m=((total%1440)+1440)%1440;return pad2(Math.floor(m/60))+':'+pad2(m%60);}
function fmtMin(m){if(m==null)return null;if(m<60)return m+' 分钟';const h=Math.floor(m/60),r=m%60;return h+' 小时'+(r?' '+r+' 分钟':'');}
async function transportLeg(from,to,mode){
 try{
  const r=await fetch('/api/a1/transport?'+new URLSearchParams({from,to,mode}),{signal:AbortSignal.timeout(25000)});
  const j=await r.json();
  if(!r.ok||j.code!=='OK')return null;
  const o=j.data&&j.data.options&&j.data.options[0];
  if(!o)return null;
  const d=numericEstimate(o.distance),t=numericEstimate(o.duration);
  let cost=null;const raw=o.cost;if(raw!==undefined&&raw!==null&&raw!==''){const n=numericEstimate(raw);if(Number.isFinite(n))cost=n;}
  return {km:Number.isFinite(d)?Math.round(d/100)/10:null,min:Number.isFinite(t)?Math.max(1,Math.round(t/60)):null,cost};
 }catch{return null;}
}
async function weatherFor(id){
 try{const r=await fetch('/api/a1/weather?id='+encodeURIComponent(id),{signal:AbortSignal.timeout(25000)});const j=await r.json();return (!r.ok||j.code!=='OK')?null:j.data;}catch{return null;}
}
function factCell(label,value){const cell=node('div',null,'fact');cell.append(node('span',label,'fact-label'),node('strong',value,'fact-value'));return cell;}
function travelModeLabel(v){return v==='self-drive'?'自驾出行':v==='taxi'?'打车 / 家人接送':v==='transit'?'步行 + 公交':'未选择';}
function paceLabel(v){return v==='slow'?'慢节奏，不赶景点':v==='active'?'徒步为主，多看几处':v==='steady'?'走走歇歇，常规节奏':'未选择';}
function renderTripFacts(draft){
 const p=draft.preferences;
 const s=node('section',null,'trip-facts');
 s.append(node('div','出行信息','facts-eyebrow'));
 const grid=node('div',null,'facts-grid');
 grid.append(factCell('目的地',p.destination),factCell('出发',p.startDate),factCell('天数',p.days+' 天'),
  factCell('出行方式',travelModeLabel(p.travelMode)),factCell('行程节奏',paceLabel(p.pace)),
  factCell('单次步行',p.walkMinutes+' 分钟'),factCell('同行',p.companions||'独自出游'),
  factCell('台阶',p.avoidSteps===false?'可以爬坡':'尽量避开'));
 s.append(grid);
 const prefer=p.restFrequency==='frequent'?'每 20 分钟歇一次':p.restFrequency==='rare'?'一小时以上歇一次':p.restFrequency?'每 40 分钟歇一次':'按常规节奏';
 s.append(node('p','休息安排：'+prefer+'。已按坐标邻近关系分组；交通按出行方式查询，台阶条件尚未核实。','facts-note'));
 return s;
}
function renderDayTimeline(day,index,draft){const block=node('section',null,'timeline-day');block.append(node('h3','第'+(index+1)+'天 · '+day.date),scheduleView(day));return block;}
function renderCostCard(draft){
 const c=node('section',null,'cost-card');
 c.append(node('h3','费用明细'));
 const rows=node('div',null,'cost-rows');
 const add=(label,stateText,value,note)=>{
  const r=node('div',null,'cost-row cost-'+stateText);
  const head=node('div',null,'cost-head');
  head.append(node('span',label,'cost-label'),node('strong',value,'cost-value'));
  r.append(head);if(note)r.append(node('p',note,'cost-note'));
  rows.append(r);return r;
 };
 add('步行路段','ok','0 元','步行不产生票价');
 const transit=add('市内公共交通','pending','查询中…','按已查路段的接口估算，非全程票价');
 add('住宿','none','未接入报价','需接入住宿供应商后才能给出数字');
 add('门票','none','未接入报价','需接入票务供应商后才能给出数字');
 add('餐饮','none','未接入报价','按需接入，避免给出不准的数字');
 add('机票 / 火车票','none','未接入供应商','12306 无官方开放接口；机票需接票务服务商');
 c.append(rows);
 c.append(node('p','未接入的项目一律不填估算数字，以免误导；接入供应商后可补齐。','cost-final'));
 const first=draft.days.find(d=>d.places.length>1);
 if(!first){transit.querySelector('.cost-value').textContent='暂无跨点路段';transit.querySelector('.cost-note').textContent='添加两个地点后，可查询路段交通费用。';}
 if(first){
  transportLeg(first.places[0].id,first.places[1].id,'transit').then(v=>{
   const value=transit.querySelector('.cost-value'),note=transit.querySelector('.cost-note');
   if(v&&v.cost!=null){value.textContent='约 '+v.cost+' 元 / 段';transit.classList.remove('cost-pending');transit.classList.add('cost-ok');
    note.textContent='高德公交接口对「'+first.places[0].name+' → '+first.places[1].name+'」的估算。';}
   else{value.textContent='本次未查到';transit.classList.remove('cost-pending');transit.classList.add('cost-none');
    note.textContent='公交线路费用本次未返回，不代表实际无费用。';}
  });
 }
 return c;
}
function renderTipsCard(draft){
 const c=node('section',null,'tips-card');
 c.append(node('h3','贴心提醒'));
 const list=node('ul',null,'tips-list');
 const add=(text,cls)=>{const li=node('li',text,cls?'tip '+cls:'tip');list.append(li);};
 const p=draft.preferences;
 const perDay=draft.days.reduce((max,d)=>Math.max(max,d.places.length),0);
 if(perDay>0&&p.walkMinutes<=20&&perDay>1)add('您设定单次走约 '+p.walkMinutes+' 分钟，但每天安排了 '+perDay+' 个地点，可能偏赶，建议先删减一个。','tip-warn');
 add('本次为建议草案：开放时间、台阶与无障碍条件、营业状态都尚未核验，出行前请再向景区确认。');
 add('时间轴已包含建议游玩、午餐和休息；交通采用高德估算，失败路段后续钟点留待确认。');
 if(p.avoidSteps===false)add('您选择了不介意台阶；若同行有老人或腿脚不便，仍建议优先平缓路线。');
 else add('您选择了尽量避开台阶；已降低名称明显涉及登高地点的优先级；具体台阶和坡度尚未核实。');
 add('本次没有订票、没有占用名额，也不会自动开始行程。');
 c.append(list);
 const weather=node('p','目的地天气：正在查询…','tip-weather');
 c.append(weather);
 const firstDay=draft.days.find(d=>d.places.length);
 const first=firstDay&&firstDay.places[0];
 if(!first){weather.textContent='目的地天气：本次没有可查询的地点。';return c;}
 weatherFor(first.id).then(data=>{
  const live=data&&data.lives&&data.lives[0];
  if(!live){weather.textContent='目的地天气：本次未查询到，不影响草案内容。';return;}
  const casts=(data.forecasts&&data.forecasts[0]&&data.forecasts[0].casts)||[];
  const cast=casts.find(x=>x.date===p.startDate);
  const now='高德天气 · '+live.city+' 当前 '+live.weather+' '+live.temperature+'°C（实况发布于 '+live.reporttime+'）';
  weather.textContent=cast
   ? now+'；'+p.startDate+' 预报 '+cast.dayweather+'，'+cast.nighttemp+'–'+cast.daytemp+'°C。出发前请再看一次。'
   : now+'；'+p.startDate+' 超出接口预报范围，不能据此断定当天天气。';
 }).catch(()=>{weather.textContent='目的地天气：本次未查询到，不影响草案内容。';});
 return c;
}
function placeEmoji(place){
 const type=String(place.type||'');
 if(/餐饮|美食|餐厅|food|restaurant/i.test(type))return '🍜';
 if(/酒店|住宿|hotel|住宿服务/i.test(type))return '🏨';
 if(/公园|风景|景区|山|湖|植物|travel/i.test(type))return '🏞';
 return '📍';
}
function catKind(place){
 const type=String(place.type||'');
 if(/餐饮|美食|餐厅|food|restaurant/i.test(type))return 'food';
 if(/酒店|住宿|hotel|住宿服务/i.test(type))return 'hotel';
 return 'attraction';
}
function catLabel(place){const k=catKind(place);return k==='food'?'吃喝':k==='hotel'?'住宿':'景点';}
function cnDate(iso){
 const [y,m,d]=String(iso||'').split('-').map(Number);
 return y&&m&&d?(y+'年'+m+'月'+d+'日'):String(iso||'');
}
function renderGroupedSummary(draft){
 const wrap=node('section',null,'summary-group');
 draft.days.forEach((day,index)=>{
  const block=node('section',null,'reference-day');
  block.append(node('h3','第'+(index+1)+'天｜'+draft.preferences.destination));
  if(!day.places.length){block.append(node('p','留作休息，或在计划里添加地点。'));wrap.append(block);return;}
  const list=node('ul',null,'summary-bullets'),photos=[],seen=new Set();
  for(const place of day.places){
   const li=node('li'),body=node('span','','sb-body');
   const name=choiceButton(place.name,()=>openPlaceMap(place));name.className='sb-name';
   body.append(name);if(place.address)body.append(node('span',place.address,'sb-addr'));
   li.append(node('span',placeEmoji(place),'sb-emoji'),body);list.append(li);
  }
  // Prefer a different place for each image; only use photos returned for that place.
  for(let n=0;n<3;n++)for(const place of day.places){const url=place.photos?.[n];if(url&&!seen.has(url)&&photos.length<3){seen.add(url);photos.push({url,place});}}
  block.append(list);if(day.timeline)block.append(scheduleView(day));
  if(photos.length){const gallery=node('div',null,'summary-photos');for(const {url,place} of photos){const b=choiceButton('');b.className='sp';b.setAttribute('aria-label','查看'+place.name+'照片');const im=node('img');im.src=url;im.alt=place.name;im.loading='lazy';im.referrerPolicy='no-referrer';im.onerror=()=>b.remove();b.onclick=()=>openPhoto(url,place);b.append(im);gallery.append(b);}block.append(gallery);}
  wrap.append(block);
 });
 wrap.append(node('p','地点与照片来自高德 · 坐标分组，开放情况待核实','gallery-source'));return wrap;
}
function dateTabLabel(date){const d=new Date(date+'T00:00:00+08:00');return date.slice(5).replace('-','.')+' 周'+'日一二三四五六'[d.getDay()];}
function renderPlanSummary(draft){
 const p=draft.preferences;
 const card=node('section',null,'plan-summary');
 card.append(node('h3',p.destination+' · 慢游建议草案（'+p.days+' 天）'));
 card.append(node('p',cnDate(p.startDate)+' 出发 · 共 '+p.days+' 天 · '+travelModeLabel(p.travelMode)+' · '+paceLabel(p.pace),'ps-dates'));
 draft.days.forEach((day,i)=>{
  const row=node('div',null,'ps-row');
  row.append(node('span','第'+(i+1)+'天','ps-day'));
  row.append(node('span',day.places.length?day.places.map(pl=>pl.name).join(' → '):'留作休息或待补充','ps-route'));
  card.append(row);
 });
 card.append(node('p','这是建议草案：未订票、未占用名额、不会自动开始行程；实际路程、体力适配与开放状态仍需核实。','ps-note'));
 return card;
}
function renderDraftCard(target,draft){
 const card=node('section',null,'draft-summary narrative-draft');
 card.append(node('div','建议草案 · 尚未开始游览','draft-eyebrow'),node('h2',draft.title));
 const facts=node('details',null,'plan-more');facts.append(node('summary','出行偏好'),renderTripFacts(draft));card.append(facts);
 card.append(renderGroupedSummary(draft));
 const extras=node('details',null,'plan-more');extras.append(node('summary','费用与出行提醒'),renderCostCard(draft),renderTipsCard(draft));card.append(extras);
 card.append(renderPlanSummary(draft));
 card.append(choiceButton('查看计划 ↗',()=>openDraft(draft)));
 card.append(node('p','以上按已查询地点整理；路网次序、天气、台阶与营业状态仍需核实。','wizard-note'));
 target.append(card);toLatest();
}
function openPhoto(url,place){const dialog=document.querySelector('#photo-dialog');document.querySelector('#photo-full').src=url;document.querySelector('#photo-label').textContent=place.name+' · 高德地点照片';dialog.showModal();}
function openDraft(draft){if(savingDraft){showToast('正在保存草案，请稍后恢复');return;}if(travelDraft?.id===draft.id&&(draft.version||1)<(travelDraft.version||1)){showToast('恢复结果是旧版本，已保留当前草案');return;}travelDraft=draft;draftDialog.showModal();renderDraftDetail(0);window.setTripSheet?.(.68);}
function renderDraftDetail(active){if(active===-1){renderTripOverview();return;}const root=document.querySelector('#draft-detail');root.replaceChildren(node('h1',travelDraft.title),node('p',travelDraft.preferences.startDate+' 起 · '+travelDraft.days.length+' 天 · 建议草案','draft-dates'));const tabs=node('nav',null,'draft-tabs');tabs.setAttribute('aria-label','按天查看');travelDraft.days.forEach((day,i)=>{const b=choiceButton(dateTabLabel(day.date),()=>renderDraftDetail(i));b.setAttribute('aria-pressed',String(i===active));tabs.append(b);});const overview=choiceButton('总览',()=>renderDraftDetail(-1));overview.setAttribute('aria-pressed','false');tabs.prepend(overview);root.append(tabs);
 window.showTripDay?.(travelDraft,active);const day=travelDraft.days[active];root.append(node('h2',dateTabLabel(day.date)+' · 当天行程'));if(!day.places.length)root.append(node('p','当天暂无地点资料，可留作休息。'));
 root.append(scheduleView(day),journeyNotesPanel(travelDraft,day,active),node('h3','地点资料与编辑'));
 day.places.forEach((place,index)=>{const item=node('article',null,'draft-stop');item.dataset.placeId=place.id;item.append(node('span',String(index+1),'stop-number'));
 const head=node('div',null,'stop-head');const ht=node('div',null,'stop-headtext');
 ht.append(node('span',catLabel(place),'cat-tag cat-'+catKind(place)),node('h3',place.name));
 if(place.address)ht.append(node('p',place.address));
 const timeLabel=node('span','','stop-time');timeLabel.textContent=stopScheduleLabel(day,place.id);ht.append(timeLabel);
 head.append(ht);
 const thumbUrl=place.photos&&place.photos[0];
 if(thumbUrl){const im=node('img','','stop-thumb');im.src=thumbUrl;im.alt=place.name+' · 高德地点照片';im.loading='lazy';im.referrerPolicy='no-referrer';im.onerror=()=>im.remove();head.prepend(im);}
 item.append(head);
 const controls=node('div',null,'stop-actions');controls.append(choiceButton('地图定位',()=>window.focusTripPlace?.(place.id)),choiceButton('问问这个地点',()=>{draftDialog.close();selectedPlace=place;document.querySelector('#scene-name').textContent=place.name;sendMessage('介绍一下'+place.name+'，请根据查到的资料回答。');}),choiceButton('移除此地点',()=>{if(!canEditDraft())return;day.places.splice(index,1);renderDraftDetail(active);showToast('已移除，点击保存后生效');}));if(index>0)controls.append(choiceButton('上移',()=>{if(!canEditDraft())return;[day.places[index-1],day.places[index]]=[day.places[index],day.places[index-1]];renderDraftDetail(active);}));if(index<day.places.length-1)controls.append(choiceButton('下移',()=>{if(!canEditDraft())return;[day.places[index+1],day.places[index]]=[day.places[index],day.places[index+1]];renderDraftDetail(active);}));if(index<day.places.length-1)controls.append(choiceButton('到下一站的交通',()=>openTransportInfo(place,day.places[index+1])));item.querySelector('h3').onclick=()=>window.focusTripPlace?.(place.id);const edit=node('details',null,'stop-edit-details');const editLabel=node('summary','编辑','stop-edit-label');edit.append(editLabel,controls);item.append(edit);root.append(item);});appendDraftEditing(root,active);root.append(node('p','修改后请点保存。保存的是出游草案，不会开始正式旅程；实际路程、体力适配和开放状态仍需核实。','wizard-note'));}
document.querySelector('#draft-close').onclick=()=>draftDialog.close();document.querySelector('#draft-copy').onclick=async()=>{if(!travelDraft)return;const text=travelDraftSummary(travelDraft);try{await navigator.clipboard.writeText(text);showToast('已复制草案');}catch{showToast('当前浏览器无法复制');}};
document.querySelector('#start-plan').onclick=()=>wizardStart();document.querySelector('#plan-tool').onclick=()=>wizardStart();document.querySelector('#start-place').onclick=()=>{input.value='我想了解';input.focus();resizeInput();};document.querySelector('#place-tool').onclick=()=>placesDialog.showModal();
window.clearTravelDraft=()=>{travelEpoch++;travelDraft=null;travelWizard=null;document.querySelector('.topbar-title').firstChild.textContent='问问小颐';};

function renderPlanCalendar(target,inputDate){
 let [year,month]=inputDate.value.split('-').map(Number);month--;const calendar=node('section',null,'plan-calendar');target.append(calendar);
 const draw=()=>{calendar.replaceChildren();const header=node('div',null,'calendar-header');const previous=choiceButton('‹',()=>{month--;if(month<0){month=11;year--;}draw();}),next=choiceButton('›',()=>{month++;if(month>11){month=0;year++;}draw();});previous.setAttribute('aria-label','上个月');next.setAttribute('aria-label','下个月');header.append(previous,node('strong',year+'年'+(month+1)+'月'),next);calendar.append(header);const grid=node('div',null,'calendar-grid');for(const label of ['日','一','二','三','四','五','六'])grid.append(node('span',label));
 const first=new Date(year,month,1).getDay(),days=new Date(year,month+1,0).getDate();for(let i=0;i<first;i++)grid.append(node('span'));
 for(let day=1;day<=days;day++){const value=year+'-'+String(month+1).padStart(2,'0')+'-'+String(day).padStart(2,'0');const b=choiceButton(String(day),()=>{inputDate.value=value;draw();});b.disabled=value<planDateLocal();b.setAttribute('aria-label',value);b.setAttribute('aria-pressed',String(inputDate.value===value));grid.append(b);}calendar.append(grid);};inputDate.addEventListener('change',()=>{[year,month]=inputDate.value.split('-').map(Number);month--;draw();});draw();
}

let savingDraft=false;
function canEditDraft(){if(savingDraft){showToast('正在保存并重算路线，请稍后再编辑');return false;}return true;}
function appendDraftEditing(root,active){
 const section=node('details',null,'draft-editing');const heading=node('summary','＋ 添加地点 / 保存计划');const query=node('input');query.placeholder='搜索景点、住宿或机场';query.maxLength=100;query.setAttribute('aria-label','要添加的地点');const results=node('div');const search=choiceButton('搜索地点',async()=>{if(!query.value.trim())return;search.disabled=true;results.replaceChildren(node('p','正在查询…'));try{const response=await fetch('/api/a1/places?'+new URLSearchParams({query:query.value.trim(),city:travelDraft.preferences.destination}),{signal:AbortSignal.timeout(20000)});const data=await response.json();if(!response.ok||data.code!=='OK')throw new Error(data.message||'查询失败');results.replaceChildren();for(const place of data.data.places){const b=choiceButton(place.name+' · 添加',()=>{if(!canEditDraft())return;if(travelDraft.days.some(d=>d.places.some(p=>p.id===place.id))){showToast('此地点已在草案中');return;}if(travelDraft.days[active].places.length>=8){showToast('每天最多8个地点，建议适量安排');return;}travelDraft.days[active].places.push(place);renderDraftDetail(active);showToast('已添加，记得保存');});results.append(b);}if(!data.data.places.length)results.append(node('p','没有查到，请换个名称。'));}catch(e){results.replaceChildren(node('p',e.message));}finally{search.disabled=false;}});section.append(heading,query,search,results);
 const save=choiceButton('保存草案',async()=>{if(savingDraft)return;savingDraft=true;const original=travelDraft,epoch=travelEpoch;save.disabled=true;save.textContent='正在重新计算并保存…';try{const payload={id:travelDraft.id,title:travelDraft.title,expectedVersion:travelDraft.version||1,days:travelDraft.days.map(d=>({date:d.date,placeIds:d.places.map(p=>p.id)}))};const response=await fetch('/api/a1/travel-drafts/current',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(180000)});const data=await response.json();if(!response.ok||data.code!=='OK')throw new Error(data.message||'保存失败');if(travelEpoch!==epoch||travelDraft!==original){showToast('旧草案保存已完成，可从菜单恢复；未覆盖当前页面');return;}travelDraft=data.data;showToast('草案已保存，可在菜单中恢复');save.textContent='已保存';renderDraftDetail(active);}catch(e){if(travelEpoch!==epoch||travelDraft!==original)return;showToast(e.name==='TimeoutError'?'保存等待超时，结果未确认；请从菜单恢复核对，不要连续重复保存':e.message);save.textContent='重试保存';}finally{savingDraft=false;save.disabled=false;}});save.className='wizard-primary';section.append(save);root.append(section);
}
document.querySelector('#restore-draft').onclick=async()=>{if(busy)return;closeMore();try{const response=await fetch('/api/a1/travel-drafts/current');const data=await response.json();if(!response.ok||data.code!=='OK')throw new Error(data.message||'暂无草案');openDraft(data.data);}catch(e){showToast(e.message);}};

async function openTransportInfo(origin,destination){
 document.querySelector('#place-info-title').textContent='交通信息';placeInfoBody.replaceChildren(node('p',origin.name+' → '+destination.name));placeInfoDialog.showModal();
 const container=node('div',null,'transport-options');placeInfoBody.append(container);const names={walking:'步行',driving:'驾车',transit:'公共交通'};
 for(const mode of ['walking','driving','transit']){const section=node('section',null,'transport-option');section.append(node('strong',names[mode]),node('p','正在查询…'));container.append(section);
 (async()=>{try{const response=await fetch('/api/a1/transport?'+new URLSearchParams({from:origin.id,to:destination.id,mode}),{signal:AbortSignal.timeout(25000)});const data=await response.json();if(!response.ok||data.code!=='OK')throw new Error(data.message||'查询失败');section.replaceChildren(node('strong',names[mode]));const option=data.data.options?.[0];if(!option){section.append(node('p','本次未返回可用方案'));return;}const distance=numericEstimate(option.distance),duration=numericEstimate(option.duration);section.append(node('p',(Number.isFinite(distance)?(distance/1000).toFixed(1)+'公里':'距离未提供')+' · '+(Number.isFinite(duration)?Math.max(1,Math.round(duration/60))+'分钟':'耗时未提供')));
 if(mode==='transit'){const lines=[];for(const seg of option.segments||[])for(const line of seg.bus?.buslines||[])if(line.name)lines.push(line.name);if(lines.length)section.append(node('p',lines.join(' → ')));const cost=numericEstimate(option.cost);if(cost!==null)section.append(node('p','接口估算费用 '+cost+' 元'));}
 }catch(e){section.replaceChildren(node('strong',names[mode]),node('p',e.message||'查询失败'));}})();}
 placeInfoBody.append(node('p','普通交通估算，未核实无障碍、台阶与老人步速；不代表已开始导航，公交时刻与费用以运营方为准。','wizard-note'));
}

document.querySelector('#photo-close').onclick=()=>document.querySelector('#photo-dialog').close();

function renderTripOverview(){const root=document.querySelector('#draft-detail');root.replaceChildren(node('h1',travelDraft.title),node('p','总览 · 建议草案','draft-dates'));const tabs=node('nav',null,'draft-tabs');travelDraft.days.forEach((day,i)=>tabs.append(choiceButton(dateTabLabel(day.date),()=>renderDraftDetail(i))));root.append(tabs,renderTripFacts(travelDraft),renderCostCard(travelDraft),renderTipsCard(travelDraft));travelDraft.days.forEach((day,index)=>{const block=node('section',null,'draft-day');block.append(node('h3',day.date),node('p',day.places.map(p=>p.name).join(' → ')||'留作休息或待补充'),choiceButton('查看当天',()=>renderDraftDetail(index)));root.append(block);});window.showTripDay?.(travelDraft,-1);}
