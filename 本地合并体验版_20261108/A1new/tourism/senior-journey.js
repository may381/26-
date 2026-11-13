'use strict';
// Local, self-reported travel notes. These never stand in for P2 Trip or memory.
function readTravelPreferences(){
 try{const p=JSON.parse(localStorage.getItem('a1-travel-preferences')||'null');
  if(!p||![20,40,60].includes(p.walkMinutes)||typeof p.avoidSteps!=='boolean')return null;
  const clean={walkMinutes:p.walkMinutes,avoidSteps:p.avoidSteps};
  if(typeof p.displayName==='string'&&p.displayName.trim())clean.displayName=p.displayName.trim().slice(0,20);
  if(Array.isArray(p.interests))clean.interests=p.interests.filter(v=>['历史文化','自然风景','美食休闲','非遗体验'].includes(v)).slice(0,4);
  if(['voice','text','both'].includes(p.interactionMode))clean.interactionMode=p.interactionMode;
  clean.onboardingCompleted=Boolean(p.onboardingCompleted);
  return clean;
 }catch{return null;}
}
function localTravelRead(key){try{return JSON.parse(localStorage.getItem(key)||'{}')||{};}catch{return {};}}
function localTravelWrite(key,value){try{localStorage.setItem(key,JSON.stringify(value));return true;}catch{showToast('浏览器未能保存，请复制记录自行保留');return false;}}
function openTravelGuide(){
 const dialog=document.createElement('dialog');dialog.setAttribute('aria-label','第一次使用');
 const close=choiceButton('关闭',()=>dialog.close());dialog.append(node('h2','先认识您的旅伴'),close,node('p','选好步行偏好，再试一次提问。这里的偏好仅保存在本浏览器，不是平台长期档案。'));
 const pref=readTravelPreferences()||{walkMinutes:40,avoidSteps:true,interests:[],interactionMode:'both',onboardingCompleted:false};
 const nameLabel=node('label','希望我怎么称呼您？');const displayName=document.createElement('input');displayName.maxLength=20;displayName.placeholder='例如：王阿姨';displayName.value=pref.displayName||'';displayName.setAttribute('aria-label','称呼');dialog.append(nameLabel,displayName);
 dialog.append(node('h3','一次连续走多久比较合适？'));
 const choices=node('div',null,'stop-actions');for(const minutes of [20,40,60]){const button=choiceButton(minutes+'分钟',()=>{pref.walkMinutes=minutes;for(const b of choices.children)b.setAttribute('aria-pressed',String(b===button));});button.setAttribute('aria-pressed',String(pref.walkMinutes===minutes));choices.append(button);}dialog.append(choices);
 const label=node('label');const steps=document.createElement('input');steps.type='checkbox';steps.checked=pref.avoidSteps;label.append(steps,document.createTextNode(' 尽量避开台阶（实际条件仍需核实）'));dialog.append(label);
 dialog.append(node('h3','平时更喜欢什么？'));const interestBox=node('div',null,'stop-actions');for(const value of ['历史文化','自然风景','美食休闲','非遗体验']){const button=choiceButton(value,()=>{const selected=new Set(pref.interests||[]);selected.has(value)?selected.delete(value):selected.add(value);pref.interests=[...selected];button.setAttribute('aria-pressed',String(selected.has(value)));});button.setAttribute('aria-pressed',String((pref.interests||[]).includes(value)));interestBox.append(button);}dialog.append(interestBox);
 dialog.append(node('h3','更习惯怎样看回答？'));const mode=document.createElement('select');mode.setAttribute('aria-label','交互偏好');for(const [value,title] of [['both','大字和语音都需要'],['voice','优先语音'],['text','优先大字文字']]){const option=document.createElement('option');option.value=value;option.textContent=title;mode.append(option);}mode.value=pref.interactionMode||'both';dialog.append(mode);
 const status=node('p');status.setAttribute('role','status');dialog.append(choiceButton('保存本机偏好',()=>{pref.displayName=displayName.value.trim();pref.avoidSteps=steps.checked;pref.interactionMode=mode.value;pref.onboardingCompleted=true;status.textContent=localTravelWrite('a1-travel-preferences',pref)?'已保存。新建计划会使用步行与台阶偏好，其余信息用于本页引导。':'未保存成功。';}),choiceButton('删除本机偏好',()=>{if(!confirm('删除本浏览器保存的称呼、兴趣、交互和步行偏好？已生成的出游草案不会删除。'))return;try{localStorage.removeItem('a1-travel-preferences');displayName.value='';pref.displayName='';pref.walkMinutes=40;pref.avoidSteps=true;pref.interests=[];pref.interactionMode='both';pref.onboardingCompleted=false;steps.checked=true;mode.value='both';for(const button of choices.children)button.setAttribute('aria-pressed',String(button.textContent==='40分钟'));for(const button of interestBox.children)button.setAttribute('aria-pressed','false');status.textContent='本机偏好已删除，后续新计划使用默认设置。';}catch{status.textContent='浏览器未能删除，请检查存储权限。';}}),status);
 dialog.append(node('h3','三个常用动作'));
 for(const [title,action] of [['我想去逛逛',()=>wizardStart()],['我有点累',()=>sendMessage('我有点累，请根据我提供的位置找休息设施；不知道位置时先问我。')],['练习问厕所在哪',()=>sendMessage('厕所在哪里？请说明使用的是演示资料还是真实地点资料。')]])dialog.append(choiceButton(title,()=>{dialog.close();action();}));
 dialog.append(node('h3','需要找人帮忙？'),node('p','当前旅游预览尚未接通工作人员接单或家属通知。请使用电话或直接联系现场服务台；这里不会显示已经通知成功。'),node('p','也可以请家属或现场人员协助设置。使用不顺利时，不必反复尝试。'));
 dialog.addEventListener('close',()=>dialog.remove(),{once:true});document.body.append(dialog);dialog.showModal();
}
function journeyNotesPanel(draft,day,index){
 const section=node('details',null,'plan-more');section.append(node('summary','游中记录、疲劳调整与游后反馈'));
 section.append(node('p','以下由您手动记录，仅保存在当前浏览器；不使用实时定位，不代表平台已开始游览或通知家属。'));
 const key='a1-local-journey:'+draft.id+':'+day.date;let saved=localTravelRead(key);
 const validStatuses=new Set(['visited','skip']);
 const marks={};for(const p of day.places)if(validStatuses.has(saved.marks?.[p.id]))marks[p.id]=saved.marks[p.id];
 const output=node('p');output.setAttribute('role','status');
 function summary(){const visited=day.places.filter(p=>marks[p.id]==='visited'),pending=day.places.filter(p=>!marks[p.id]);output.textContent='自己记录已游 '+visited.length+' 处；下一站：'+(pending[0]?.name||'暂无待游地点')+'。预计结束时间请参考建议时间轴，实际进度尚未核实。';}
 function persist(){return localTravelWrite(key,{marks,feedback:feedback.value,updatedAt:new Date().toISOString()});}
 for(const place of day.places){const row=node('label');row.style.display='block';row.style.padding='8px 0';row.append(document.createTextNode(place.name+' '));const select=node('select');select.setAttribute('aria-label',place.name+'游览状态');for(const [value,title] of [['','尚未游览'],['visited','我已游览'],['skip','本次跳过']]){const opt=node('option',title);opt.value=value;select.append(opt);}select.value=marks[place.id]||'';select.onchange=()=>{if(select.value)marks[place.id]=select.value;else delete marks[place.id];persist();summary();};row.append(select);section.append(row);}
 const feedback=node('textarea');feedback.maxLength=500;feedback.rows=3;feedback.placeholder='例如：走20分钟想休息，下次少安排一处';feedback.setAttribute('aria-label','本次游览反馈');feedback.value=typeof saved.feedback==='string'?saved.feedback.slice(0,500):'';
 let serverVersion=null;
 const sync=node('div');const syncStatus=node('p');syncStatus.setAttribute('role','status');
 const endpoint='/tourism-api/api/a1/travel-drafts/'+encodeURIComponent(draft.id)+'/journal';
 async function journalRequest(method,body){const response=await fetch(endpoint+(method==='GET'?'?date='+encodeURIComponent(day.date):''),{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(15000)});const result=await response.json();if(!response.ok||result.code!=='OK')throw new Error(response.status===409?'服务器记录已更新，请先恢复再修改。':'服务器记录操作失败，请先保存草案并核对结果。');return result.data;}
 const restore=choiceButton('恢复服务器游览记录',async()=>{restore.disabled=true;try{const entry=await journalRequest('GET');if(!confirm('用服务器记录替换本页手动记录？未提交的本机改动将被替换。'))return;serverVersion=entry.version;for(const id of Object.keys(marks))delete marks[id];for(const p of day.places)if(validStatuses.has(entry.marks?.[p.id]))marks[p.id]=entry.marks[p.id];feedback.value=entry.feedback||'';for(const select of section.querySelectorAll('select')){const place=day.places.find(p=>select.getAttribute('aria-label')===p.name+'游览状态');if(place)select.value=marks[place.id]||'';}persist();summary();syncStatus.textContent='已恢复服务器记录，版本 '+serverVersion+'。记录来源为用户自报，不代表定位核验。';}catch(e){syncStatus.textContent=e.message;}finally{restore.disabled=false;}});
 const upload=choiceButton('保存游览记录到旅游后端',async()=>{if(serverVersion===null){syncStatus.textContent='请先恢复服务器记录，核对后再保存，避免覆盖其他页面的记录。';return;}upload.disabled=true;try{const entry=await journalRequest('PUT',{date:day.date,marks,feedback:feedback.value,expectedVersion:serverVersion});serverVersion=entry.version;syncStatus.textContent='旅游后端已保存，版本 '+serverVersion+'；尚未写入P2长期记忆或通知家属。';}catch(e){syncStatus.textContent=e.message;}finally{upload.disabled=false;}});
 const clearServer=choiceButton('清空服务器本日记录与反馈',async()=>{if(serverVersion===null){syncStatus.textContent='请先恢复服务器记录，再决定是否清空。';return;}if(!confirm('清空旅游后端本日记录和反馈？本机记录单独保留。'))return;clearServer.disabled=true;try{const entry=await journalRequest('PUT',{date:day.date,marks:{},feedback:'',expectedVersion:serverVersion});serverVersion=entry.version;syncStatus.textContent='服务器本日内容已清空，保留版本号以防止旧页面覆盖。';}catch(e){syncStatus.textContent=e.message;}finally{clearServer.disabled=false;}});
 sync.append(node('h3','服务器游览记录'),node('p','先保存出游草案，再恢复服务器记录后修改。使用当前浏览器的草案归属凭据；尚无生产账号鉴权。'),restore,upload,clearServer,syncStatus);section.append(sync);
 const fatigue=node('div');fatigue.setAttribute('role','status');
 section.append(choiceButton('请学校模型根据记录给调整建议',()=>{
  const text='请给出适老出游调整建议，不执行路线修改、通知或长期记忆保存。以下都是用户手动记录，地点是计划而非当前位置；缺少资料请追问，不编造距离、设施或营业状态。\n计划日期：'+day.date+'\n地点状态：'+day.places.map(p=>p.name+'：'+(marks[p.id]==='visited'?'用户自报已游':marks[p.id]==='skip'?'用户计划跳过':'尚未确认游览')).join('；')+'\n用户反馈：'+(feedback.value||'尚未填写，请先询问体力状态与希望调整的部分。');
  if(text.length>2000){showToast('内容过长，请减少地点或精简反馈后再咨询');return;}
  draftDialog.close();sendMessage(text);
 }));
 section.append(output,choiceButton('我累了，看看怎么减少剩余安排',()=>{
  const remaining=day.places.filter(p=>!marks[p.id]);fatigue.replaceChildren(node('p','先停下来休息。已游记录保持不变；建议只保留下一处，其余可暂时跳过。该建议尚未修改您的草案。'));
  if(remaining.length>1)fatigue.append(choiceButton('确认将后续地点标为本次跳过',()=>{for(const p of remaining.slice(1))marks[p.id]='skip';persist();const replacement=journeyNotesPanel(draft,day,index);replacement.open=true;section.replaceWith(replacement);}));
  fatigue.append(choiceButton('查询休息设施',()=>{draftDialog.close();sendMessage('我累了，请先确认我的位置，再查找休息设施，不要把计划地点当作我所在的位置。');}));
 }),fatigue,node('h3','游后反馈'),feedback,choiceButton('保存本机反馈',()=>{if(persist())showToast('反馈已保存在本机，尚未写入长期记忆');}),choiceButton('复制自己记录的游览小结',async()=>{
  const text=[draft.title+' · 第'+(index+1)+'天 '+day.date,'本机手动记录，非定位或平台核验结果。','我记录已游：'+(day.places.filter(p=>marks[p.id]==='visited').map(p=>p.name).join('、')||'暂无'),'本次跳过：'+(day.places.filter(p=>marks[p.id]==='skip').map(p=>p.name).join('、')||'暂无'),'我的反馈：'+(feedback.value||'未填写'),'尚未通知家属、未提交平台档案或长期记忆。'].join('\n');
  try{await navigator.clipboard.writeText(text);showToast('已复制，请核对后自行分享');}catch{showToast('浏览器无法复制，请手动保留记录');}
 }),choiceButton('删除本日的本机记录',()=>{if(!confirm('删除本日的手动游览记录和反馈？出游草案会保留。'))return;try{localStorage.removeItem(key);const replacement=journeyNotesPanel(draft,day,index);replacement.open=true;section.replaceWith(replacement);}catch{showToast('未能删除，请检查浏览器存储权限');}}));summary();return section;
}
const guideEntry=choiceButton('第一次使用 / 步行偏好',openTravelGuide);guideEntry.className='suggestion';document.querySelector('#welcome .suggestions').append(guideEntry);
