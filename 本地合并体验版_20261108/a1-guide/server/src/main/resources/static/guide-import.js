'use strict';
const importDialog=node('dialog',null,'guide-import-dialog');
importDialog.setAttribute('aria-label','导入攻略');
const importTitle=node('h2','把喜欢的攻略，变成自己的行程');
const importClose=choiceButton('✕',()=>importDialog.close());importClose.setAttribute('aria-label','关闭导入攻略');
const importHeader=node('header',null,'import-header');importHeader.append(importTitle,importClose);
const importIntro=node('p','粘贴小红书分享链接、攻略正文，或上传截图。读取公开笔记后，确认真实地点，再变成自己的行程。','import-note');
const importText=node('textarea');importText.maxLength=6000;importText.rows=8;importText.placeholder='例如：阳江三日游，想去海陵岛、十里银滩、大角湾……\n\n支持小红书笔记链接和 xhslink 分享短链接。';importText.setAttribute('aria-label','攻略正文或分享文案');
const importStatus=node('p','','import-status');importStatus.setAttribute('role','status');
const importFile=node('input');importFile.type='file';importFile.accept='image/png,image/jpeg';importFile.hidden=true;
const uploadGuide=choiceButton('上传攻略截图',()=>importFile.click());
const analyzeGuide=choiceButton('读取攻略并提取',analyzeImportedGuide);analyzeGuide.className='import-primary';
const importActions=node('div',null,'import-actions');importActions.append(uploadGuide,analyzeGuide,importFile);
const importResults=node('section',null,'import-results');
const importSource=node('section',null,'import-source');importSource.hidden=true;
importDialog.append(importHeader,importIntro,importText,importActions,importStatus,importSource,importResults);document.body.append(importDialog);
const importTrigger=choiceButton('导入攻略',()=>{closeMore();importDialog.showModal();});
document.querySelector('.tool-row').prepend(importTrigger);
document.querySelector('#more-menu').prepend(choiceButton('导入链接 / 正文 / 截图',()=>{closeMore();importDialog.showModal();}));
let importInFlight=false,importSelected=new Map(),importRevision=0;
async function importRequest(url,options){const response=await fetch(url,{...options,signal:AbortSignal.timeout(150000)});const data=await response.json();if(!response.ok||data.code!=='OK')throw new Error(data.message||'处理未完成，请重试');return data.data;}
function importBusy(value){importInFlight=value;uploadGuide.disabled=value;analyzeGuide.disabled=value;importText.disabled=value;}
importText.addEventListener('input',()=>{importRevision++;importResults.replaceChildren();importSelected.clear();importStatus.textContent='';importSource.hidden=true;importSource.replaceChildren();});
importFile.onchange=async()=>{
 const file=importFile.files[0];if(!file||importInFlight)return;
 if(file.size>4*1024*1024){importStatus.textContent='截图请小于4MB，支持 PNG 或 JPG。';importFile.value='';return;}
 importSource.hidden=true;importSource.replaceChildren();importBusy(true);importRevision++;importResults.replaceChildren();importSelected.clear();importStatus.textContent='正在识别截图文字，请稍候…';
 try{const body=new FormData();body.append('file',file);const data=await importRequest('/api/a1/guide-imports/ocr',{method:'POST',body});importText.value=data.text;importStatus.textContent=(data.truncated?'文字已截取前6000字。':'截图文字已识别。')+'请先核对文字，再点击提取地点。';}
 catch(e){importStatus.textContent=e.message||'截图识别失败，请粘贴正文。';}
 finally{importBusy(false);importFile.value='';}
};
async function analyzeImportedGuide(){
 if(importInFlight)return;let text=importText.value.trim();if(!text){importText.focus();return;}
 importBusy(true);const revision=++importRevision;importResults.replaceChildren();importSelected.clear();importStatus.textContent='正在从您提供的文字中提取地点…';
 try{
 const links=guideShareLinks(text);
 if(links.length){
  importStatus.textContent='正在读取公开笔记正文…';importSource.hidden=false;importSource.replaceChildren(node('strong','正在读取小红书分享链接'),node('p','只读取公开网页；需要登录或正文不可用时，可继续上传截图。','import-note'));
  const page=await importRequest('/api/a1/guide-imports/read-link',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:links[0]})});if(revision!==importRevision)return;
  importSource.replaceChildren(node('strong',page.status==='READY'?(page.title||'已读取公开笔记'):'需要补充攻略内容'),node('p',page.message,'import-note'));
  const original=node('a','打开原笔记');original.href=page.sourceUrl;original.target='_blank';original.rel='noopener noreferrer';importSource.append(original);
  if(page.status!=='READY'){importStatus.textContent='未读到笔记正文，请补充正文或上传截图后继续。';const supplement=choiceButton('补充笔记正文',()=>{importText.focus();importText.select();});importSource.append(supplement,choiceButton('上传笔记截图',()=>importFile.click()));
   const pasted=text.replace(/https?:\/\/[^\s<>"，。]+/gi,'').replace(/复制这段话[\s\S]*$/,'').trim();
   if(pasted.length>=12)importSource.append(choiceButton('仅提取已粘贴的文字',()=>{importText.value=pasted;importSource.hidden=true;analyzeImportedGuide();}));return;}
  text=page.text;importText.value=text;importSource.append(node('p','来源：小红书公开网页 · '+new Date(page.retrievedAt).toLocaleString('zh-CN'),'import-note'));
 }
 importStatus.textContent='正文已就绪，正在提取目的地和地点…';
 const data=await importRequest('/api/a1/guide-imports/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});if(revision!==importRevision)return;importStatus.textContent=data.message;
 if(data.status!=='REVIEW')return;
 const city=node('input');city.value=data.destination;city.maxLength=40;city.placeholder='请填写目的地城市，例如阳江';city.setAttribute('aria-label','目的地城市');
 importResults.append(node('h3','确认攻略中的地点'),node('p','目前使用高德国内地点数据。请核对同名地点与地址，海外攻略暂不能直接生成地图行程。','import-note'),city);
 const count=node('p','已确认 0 个地点','import-count');importResults.append(count);
 let placeCount=0;
 const addPlace=(initial)=>{
  if(placeCount>=8){showToast('每次最多匹配8个地点');return;}const key='place-'+(++placeCount);
  const card=node('article',null,'import-place'),results=node('div',null,'import-matches');
  const nameInput=node('input');nameInput.value=initial;nameInput.maxLength=60;nameInput.placeholder='填写或修改地点名称';nameInput.setAttribute('aria-label','攻略中的地点名称');
  const updateCount=()=>{count.textContent='已确认 '+importSelected.size+' 个地点';};
  nameInput.addEventListener('input',()=>{importSelected.delete(key);results.replaceChildren();updateCount();});
  const search=choiceButton('查找匹配地点',async()=>{
   if(!city.value.trim()){city.focus();importStatus.textContent='先填写目的地城市，再匹配地点。';return;}if(!nameInput.value.trim()){nameInput.focus();return;}
   const requestedCity=city.value.trim(),requestedName=nameInput.value.trim();search.disabled=true;results.replaceChildren(node('p','正在查询高德地点…'));
   try{const response=await fetch('/api/a1/places?'+new URLSearchParams({query:requestedName,city:requestedCity}),{signal:AbortSignal.timeout(25000)});const found=await response.json();if(revision!==importRevision||city.value.trim()!==requestedCity||nameInput.value.trim()!==requestedName)return;if(!response.ok||found.code!=='OK')throw new Error(found.message||'查询失败');results.replaceChildren();
    for(const place of found.data.places){const b=choiceButton('');b.append(node('strong',place.name),node('span',place.address||'地址未提供'));b.setAttribute('aria-pressed',String(importSelected.get(key)?.id===place.id));b.onclick=()=>{if([...importSelected].some(([other,p])=>other!==key&&p.id===place.id)){showToast('这个地点已经确认过了');return;}const wasSelected=importSelected.get(key)?.id===place.id;if(wasSelected)importSelected.delete(key);else importSelected.set(key,place);results.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(!wasSelected&&x===b)));updateCount();};results.append(b);}
    if(!found.data.places.length)results.append(node('p','未查到匹配地点，可修改名称再查，或暂不加入行程。'));
   }catch(e){results.replaceChildren(node('p',e.message||'查询失败，请重试'));}finally{search.disabled=false;}
  });card.append(nameInput,search,results);importResults.insertBefore(card,addManual);
 };
 const addManual=choiceButton('＋ 补充一个地点',()=>addPlace(''));importResults.append(addManual);
 for(const name of data.places)addPlace(name);
 city.addEventListener('input',()=>{importSelected.clear();count.textContent='城市已修改，请重新匹配地点';importResults.querySelectorAll('.import-matches').forEach(el=>el.replaceChildren());});
 const begin=choiceButton('用确认的地点准备行程',()=>{if(!city.value.trim()||!importSelected.size){importStatus.textContent='请填写城市，并至少确认一个真实地点。';return;}if(busy){showToast('请等待当前对话完成');return;}window.pendingImportedPlaces=[...importSelected.values()];importDialog.close();wizardStart(city.value.trim());});begin.className='import-primary';importResults.append(begin,node('p','地点按日期分配形成待调整草案，不代表已核验开放状态、台阶或交通可达性。','import-note'));
 }catch(e){importStatus.textContent=e.message||'提取失败，请重试';if(importSource.querySelector('strong')?.textContent==='正在读取小红书分享链接')importSource.replaceChildren(node('strong','链接读取未完成'),node('p','可重试读取，或补充正文、上传截图继续。','import-note'),choiceButton('上传笔记截图',()=>importFile.click()));}finally{importBusy(false);}
}

function guideShareLinks(text){return [...text.matchAll(/https?:\/\/[^\s<>"，。]+/gi)].map(m=>m[0].replace(/[）)。，！!；;]+$/g,''));}
