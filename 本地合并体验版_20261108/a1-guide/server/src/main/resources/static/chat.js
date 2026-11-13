'use strict';
const form=document.querySelector('#form');
const input=document.querySelector('#text');
const chat=document.querySelector('#chat');
const scrollArea=document.querySelector('#scroll-area');
const welcome=document.querySelector('#welcome');
const statusText=document.querySelector('#status');
const locationSelect=document.querySelector('#location');
const send=document.querySelector('#send');
const moreMenu=document.querySelector('#more-menu');
const moreButton=document.querySelector('#more');
const jump=document.querySelector('#jump-latest');
let busy=false,toastTimer,selectedPlace=null;

function icon(name){
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('class','icon');svg.setAttribute('aria-hidden','true');
  const use=document.createElementNS('http://www.w3.org/2000/svg','use');
  use.setAttribute('href','#i-'+name);svg.append(use);return svg;
}
function nearBottom(){return scrollArea.scrollHeight-scrollArea.scrollTop-scrollArea.clientHeight<130;}
function toLatest(){scrollArea.scrollTo({top:scrollArea.scrollHeight,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}
function showToast(text){document.querySelector('#toast').textContent=text;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{document.querySelector('#toast').textContent='';},2200);}
function inlineText(target,text){
  let last=0;const pattern=/\*\*([^*\n]+)\*\*|`([^`\n]+)`/g;let match;
  while((match=pattern.exec(text))){target.append(document.createTextNode(text.slice(last,match.index)));const element=document.createElement(match[1]?'strong':'code');element.textContent=match[1]||match[2];target.append(element);last=pattern.lastIndex;}
  target.append(document.createTextNode(text.slice(last)));
}
function renderText(target,text){
  // A small, DOM-only formatter: no raw HTML, scripts, remote images or embedded links.
  let paragraph=[],list=null,quote=null,inCode=false,codeLines=[];
  const flush=()=>{if(paragraph.length){const p=document.createElement('p');inlineText(p,paragraph.join('\n'));target.append(p);paragraph=[];}};
  const appendCode=()=>{const pre=document.createElement('pre'),code=document.createElement('code');code.textContent=codeLines.join('\n');pre.append(code);target.append(pre);codeLines=[];};
  for(const line of text.split('\n')){
    if(/^\s*```/.test(line)){flush();list=null;quote=null;if(inCode)appendCode();inCode=!inCode;continue;}
    if(inCode){codeLines.push(line);continue;}
    if(!line.trim()){flush();list=null;quote=null;continue;}
    const heading=line.match(/^(#{1,4})\s+(.+)$/);
    const item=line.match(/^\s*(?:(\d{1,2})[.、)]\s*|([-*])\s+)(.+)$/);
    const quoted=line.match(/^>\s?(.*)$/);
    if(heading){flush();list=null;quote=null;const h=document.createElement(heading[1].length<3?'h3':'h4');inlineText(h,heading[2]);target.append(h);}
    else if(item){flush();quote=null;const tag=item[1]?'OL':'UL';if(!list||list.tagName!==tag){list=document.createElement(tag.toLowerCase());if(item[1])list.start=Number(item[1]);target.append(list);}const li=document.createElement('li');inlineText(li,item[3]);list.append(li);}
    else if(quoted){flush();list=null;if(!quote){quote=document.createElement('blockquote');target.append(quote);}const p=document.createElement('p');inlineText(p,quoted[1]);quote.append(p);}
    else{list=null;quote=null;paragraph.push(line);}
  }
  flush();if(inCode&&codeLines.length)appendCode();
}
function message(text,{mine=false,meta='',error=false,speechRate=.8}={}){
  const shouldScroll=mine||nearBottom();welcome.hidden=true;
  const row=document.createElement('article');row.className='message'+(mine?' user':'');
  row.setAttribute('aria-label',mine?'您的消息':error?'发送提示':'旅伴的回答');
  if(!mine){const avatar=document.createElement('div');avatar.className='avatar';avatar.append(icon(error?'info':'sparkle'));row.append(avatar);}
  const content=document.createElement('div');content.className='message-content';
  if(!mine){const author=document.createElement('div');author.className='author';author.textContent=error?'暂时没有连上':'小颐';content.append(author);}
  const bubble=document.createElement('div');bubble.className='bubble';
  const clean=mine?text:text.replace(/【[^】]*(?:演示|本地\s*AI)[^】]*】\s*/g,'').trim();
  renderText(bubble,clean);content.append(bubble);
  if(!mine){
    const footer=document.createElement('div');footer.className='message-footer';
    const source=document.createElement('span');source.className='source-label';source.textContent=meta;footer.append(source);
    if(!error){const copy=document.createElement('button');copy.type='button';copy.className='copy-button';copy.setAttribute('aria-label','复制这条回答');copy.title='复制回答';copy.append(icon('copy'));
      copy.onclick=async()=>{try{await navigator.clipboard.writeText(bubble.innerText);showToast('已复制回答');}catch{showToast('请选中回答文字进行复制');}};footer.append(copy);}
    if(!error){const listen=document.createElement('button');listen.type='button';listen.className='listen-button';listen.textContent='听这段';listen.onclick=()=>speakAnswer(clean,listen,speechRate);footer.append(listen);}
    content.append(footer);
  }
  row.append(content);chat.append(row);if(shouldScroll)toLatest();else jump.classList.add('visible');return row;
}
function thinking(){
  const row=document.createElement('div');row.className='message';row.setAttribute('aria-hidden','true');
  const avatar=document.createElement('div');avatar.className='avatar';avatar.append(icon('sparkle'));
  const body=document.createElement('div');body.className='thinking';
  const dots=document.createElement('span');dots.className='thinking-dots';
  for(let i=0;i<3;i++)dots.append(document.createElement('i'));
  const label=document.createElement('span');label.textContent='正在等待助手回复…';
  const started=Date.now();const tick=setInterval(()=>{if(!row.isConnected){clearInterval(tick);return;}const seconds=Math.floor((Date.now()-started)/1000);label.textContent=(seconds>=15?'仍在等待模型返回，请稍候…':'正在等待助手回复…')+' '+seconds+'秒';},1000);
  body.append(dots,label);row.append(avatar,body);chat.append(row);toLatest();return row;
}
function resizeInput(){input.style.height='44px';input.style.height=Math.min(input.scrollHeight,150)+'px';send.disabled=busy||!input.value.trim();}
function setBusy(value){
  busy=value;input.readOnly=value;locationSelect.disabled=value;
  document.querySelectorAll('[data-request]').forEach(b=>b.disabled=value);
  chat.setAttribute('aria-busy',String(value));send.disabled=value||!input.value.trim();
  document.querySelector('#model-state').textContent=value?'正在回复':'智能助手';
}
function closeMore(){moreMenu.classList.remove('open');moreButton.setAttribute('aria-expanded','false');}
function closeSidebar(){document.querySelector('#sidebar').classList.remove('open');document.querySelector('#backdrop').classList.remove('open');document.querySelector('#menu').setAttribute('aria-expanded','false');}

async function sendMessage(text,reset=false){
  if(busy||!text.trim())return;
  if(!reset && window.beginPlanFromText?.(text))return;
  closeMore();closeSidebar();setBusy(true);
  statusText.textContent=reset?'正在开启新对话…':'正在生成回答，首次加载模型可能稍慢…';
  if(!reset)message(text,{mine:true});
  const pending=reset?null:thinking();
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),110000);
  try{
    const location=selectedPlace?"amap:"+selectedPlace.id:locationSelect.value;
    const response=await fetch('/api/agent/messages',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({userId:'u100',text,context:{tripId:null,location:location||null}}),signal:controller.signal});
    const data=await response.json();document.querySelector('#result').textContent=JSON.stringify(data,null,2);
    if(!response.ok||data.code!=='OK')throw new Error(data.message||'发送失败，请稍后重试。');
    if(pending)pending.remove();
    if(reset){window.clearTravelDraft?.();chat.replaceChildren();welcome.hidden=false;locationSelect.value='';clearPlace();jump.classList.remove('visible');scrollArea.scrollTo({top:0});}
    else{
      const isModel=/【[^】]*本地\s*AI[^】]*】/.test(data.data.text);
      const isMock=Array.isArray(data.data.tools)&&data.data.tools.some(t=>t.result&&t.result.source==='MOCK');
      const meta=isMock?'景区演示资料'+(isModel?' · 智能助手':''):isModel?'智能助手 · 本次对话':'资料回答';
      const real=[...(data.data.tools||[])].reverse().find(t=>t.result?.source==='AMAP'&&t.result.status!=='FAILED');
      const row=message(data.data.text,{speechRate:data.data.speechRate,meta:real?'高德地点资料 · 查询时间 '+new Date(real.result.retrievedAt).toLocaleTimeString():meta});
      if(real){const trace=document.createElement('details');trace.className='execution-trace';const summary=document.createElement('summary');summary.textContent='查看查询依据';trace.append(summary);for(const call of data.data.tools||[]){const line=document.createElement('p');line.textContent=call.tool+' · '+(call.result?.status==='FAILED'?'未完成':'已返回')+' · '+(call.result?.retrievedAt?new Date(call.result.retrievedAt).toLocaleTimeString():'');trace.append(line);}row.querySelector('.message-content').append(trace);renderPlaces(row.querySelector('.message-content'),real.result.places,!real.result.requiresSelection);if(real.result.queryPlace){document.querySelector('#scene-name').textContent='查询：'+real.result.queryPlace;selectedPlace=null;document.querySelector('#selected-place').textContent='未选择真实地点 · 可继续体验演示资料';document.querySelector('#clear-place').hidden=true;}}
    }
    input.value='';statusText.textContent=reset?'新对话已准备好。':'回答已生成';
  }catch(error){
    if(pending)pending.remove();
    message(error.name==='AbortError'?'等待已超时，尚未收到回复。请检查模型连接后再试，您的问题已保留。':error.message,{error:true,meta:'问题已保留，可重新发送'});
    statusText.textContent='发送未完成，可重试';
  }finally{clearTimeout(timer);setBusy(false);resizeInput();}
}
form.onsubmit=e=>{e.preventDefault();sendMessage(input.value.trim());};
input.addEventListener('input',resizeInput);
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&e.keyCode!==229){e.preventDefault();form.requestSubmit();}});
document.querySelectorAll('[data-ask]').forEach(b=>b.onclick=()=>{if(!busy){setTypingMode(true);input.value=b.dataset.ask;resizeInput();sendMessage(input.value);}});
document.querySelectorAll('[data-reset]').forEach(b=>b.onclick=()=>sendMessage('重新开始对话',true));
moreButton.onclick=()=>{const open=moreMenu.classList.toggle('open');moreButton.setAttribute('aria-expanded',String(open));};
document.addEventListener('click',e=>{if(!moreMenu.contains(e.target)&&!moreButton.contains(e.target))closeMore();});
document.querySelector('#menu').onclick=()=>{document.querySelector('#sidebar').classList.add('open');document.querySelector('#backdrop').classList.add('open');document.querySelector('#menu').setAttribute('aria-expanded','true');};
document.querySelector('#backdrop').onclick=closeSidebar;
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeSidebar();closeMore();}});
const fontButton=document.querySelector('#font-toggle');
function setLarge(value){document.documentElement.classList.toggle('large-type',value);fontButton.setAttribute('aria-pressed',String(value));fontButton.title=value?'恢复标准字号':'切换大字模式';}
try{setLarge(localStorage.getItem('a1-large-type')==='true');}catch{}
fontButton.onclick=()=>{const value=!document.documentElement.classList.contains('large-type');setLarge(value);try{localStorage.setItem('a1-large-type',String(value));}catch{}showToast(value?'已开启大字模式':'已恢复标准字号');};
const debug=document.querySelector('#debug-dialog');document.querySelector('#debug-open').onclick=()=>debug.showModal();document.querySelector('#debug-close').onclick=()=>debug.close();
jump.onclick=toLatest;scrollArea.addEventListener('scroll',()=>jump.classList.toggle('visible',!nearBottom()&&welcome.hidden));
resizeInput();

function clearPlace(){selectedPlace=null;document.querySelector('#scene-name').textContent='想了解哪里？直接问我';document.querySelector('#selected-place').textContent='未选择真实地点 · 可继续体验演示资料';document.querySelector('#clear-place').hidden=true;}
document.querySelector('#clear-place').onclick=()=>{if(!busy)clearPlace();};
function renderPlaces(target,places,hero=false){
 const cards=document.createElement('div');cards.className='place-cards';
 for(const place of places||[]){
  const card=document.createElement('section');card.className='place-card'+(hero?' hero-card':' wide-card');if(place.photos?.length)card.classList.add('has-photo');
  if(place.photos?.length){const photo=document.createElement('img');photo.src=place.photos[0];photo.alt=place.name+' · 高德地点照片';photo.loading='lazy';photo.referrerPolicy='no-referrer';photo.onerror=()=>{photo.remove();card.classList.remove('has-photo');};card.append(photo);}
  const title=document.createElement('h3');title.textContent=place.name;const address=document.createElement('p');address.textContent=place.address||'暂无地址资料';card.append(title,address);
  const choose=document.createElement('button');choose.textContent='选择并询问';choose.onclick=()=>{if(busy)return;selectedPlace=place;document.querySelector('#scene-name').textContent=place.name;document.querySelector('#places-dialog').close();locationSelect.value='';document.querySelector('#selected-place').textContent='正在了解：'+place.name;document.querySelector('#clear-place').hidden=false;sendMessage('介绍一下'+place.name+'，请根据查到的资料回答。');};card.append(choose);
  const link=document.createElement('button');link.type='button';link.className='inline-map-button';link.textContent='查看地图';link.onclick=()=>openPlaceMap(place);card.append(link);cards.append(card);
 }
 if(!hero && cards.children.length>1){
  cards.classList.add('stack-deck');const items=Array.from(cards.children);let current=0,startY=null;
  const controls=document.createElement('div');controls.className='deck-controls';
  const previous=document.createElement('button'),next=document.createElement('button'),page=document.createElement('span');
  previous.type=next.type='button';previous.textContent='↑ 上一张';next.textContent='下一张 ↓';page.setAttribute('aria-live','polite');
  const draw=()=>{items.forEach((item,index)=>{const depth=(index-current+items.length)%items.length;item.dataset.depth=String(depth);item.hidden=depth>2;item.inert=depth!==0;item.setAttribute('aria-hidden',String(depth!==0));});page.textContent=String(current+1).padStart(2,'0')+' / '+String(items.length).padStart(2,'0');};
  const change=delta=>{current=(current+delta+items.length)%items.length;draw();};
  previous.onclick=()=>change(-1);next.onclick=()=>change(1);controls.append(previous,page,next);
  cards.addEventListener('pointerdown',e=>{if(!e.target.closest('button,a'))startY=e.clientY;});
  cards.addEventListener('pointerup',e=>{if(startY!==null&&startY-e.clientY>65)change(1);startY=null;});
  cards.addEventListener('pointercancel',()=>{startY=null;});
  draw();target.append(cards,controls);
 }else target.append(cards);toLatest();
}
document.querySelector('#place-search').onclick=async()=>{
 if(busy)return;const query=document.querySelector('#place-query').value.trim(),city=document.querySelector('#place-city').value.trim();if(!query){showToast('请先输入地点名称');return;}
 setBusy(true);const pending=thinking();
 try{const response=await fetch('/api/a1/places?'+new URLSearchParams({query,city}),{signal:AbortSignal.timeout(20000)});const data=await response.json();if(!response.ok||data.code!=='OK')throw new Error(data.message||'查询失败');
 updateGuideBadge(data.data.places.length);placesDialog.close();const visiblePlaces=document.querySelector('#photo-filter').checked?data.data.places.filter(p=>p.photos?.length):data.data.places;
 const row=message(visiblePlaces.length?'找到这些地方，想先了解哪一个？':'本次没有符合条件的地点，试试取消照片筛选或更换名称。',{meta:'高德地点搜索 · '+new Date(data.data.retrievedAt).toLocaleTimeString()});renderPlaces(row.querySelector('.message-content'),visiblePlaces);
 }catch(e){message(e.message||'地点查询失败，请重试',{error:true});}finally{pending.remove();setBusy(false);}
};

const placesDialog=document.querySelector('#places-dialog');
document.querySelector('#open-places').onclick=()=>placesDialog.showModal();
document.querySelector('#close-places').onclick=()=>placesDialog.close();
placesDialog.addEventListener('click',e=>{if(e.target===placesDialog){const b=placesDialog.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)placesDialog.close();}});

document.querySelector('#place-filter').onclick=()=>{const panel=document.querySelector('#place-filters');panel.hidden=!panel.hidden;document.querySelector('#place-filter').setAttribute('aria-expanded',String(!panel.hidden));};

// One shared highlight moves between existing explanation controls.
const explanationMenu=document.querySelector('.tool-row');
const explanationHighlight=document.createElement('span');explanationHighlight.className='sliding-highlight';explanationHighlight.setAttribute('aria-hidden','true');explanationMenu.prepend(explanationHighlight);
let highlightedAction=null;
function positionHighlight(){if(!highlightedAction)return;explanationHighlight.style.width=highlightedAction.offsetWidth+'px';explanationHighlight.style.height=highlightedAction.offsetHeight+'px';explanationHighlight.style.transform='translate('+highlightedAction.offsetLeft+'px,'+highlightedAction.offsetTop+'px)';}
explanationMenu.querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>{highlightedAction=button;explanationMenu.querySelectorAll('button').forEach(item=>item.classList.toggle('highlighted',item===button));explanationMenu.classList.add('has-highlight');positionHighlight();}));
new ResizeObserver(positionHighlight).observe(explanationMenu);
document.fonts.ready.then(positionHighlight);

const inlineGroups=Array.from(document.querySelectorAll('.inline-group'));
inlineGroups.forEach(group=>{const toggle=group.querySelector('.inline-toggle'),panel=group.querySelector('.inline-panel');toggle.onclick=()=>{const opening=toggle.getAttribute('aria-expanded')!=='true';inlineGroups.forEach(other=>{other.querySelector('.inline-toggle').setAttribute('aria-expanded','false');other.querySelector('.inline-panel').hidden=true;});if(opening){toggle.setAttribute('aria-expanded','true');panel.hidden=false;}};});
document.querySelector('#sidebar-place-search').onclick=()=>{closeSidebar();placesDialog.showModal();};

document.querySelector('#dock-chat').onclick=()=>{closeSidebar();if(placesDialog.open)placesDialog.close();input.focus();};


const dockItems=Array.from(document.querySelectorAll('.dock-item'));
dockItems.forEach((item,index)=>{item.addEventListener('pointerenter',()=>{dockItems.forEach((other,i)=>other.classList.toggle('dock-neighbor',Math.abs(i-index)===1));});item.addEventListener('pointerleave',()=>dockItems.forEach(other=>other.classList.remove('dock-neighbor')));});

const provinceSelect=document.querySelector('#place-province'),citySelect=document.querySelector('#place-city'),locateButton=document.querySelector('#locate-me'),locationStatus=document.querySelector('#location-status');
let districtLoaded=false;
function fillOptions(select,items,useName=false){select.replaceChildren();for(const item of items){const o=document.createElement('option');o.value=useName?item.name:item.adcode;o.textContent=item.name;select.append(o);}}
async function districtData(code){const response=await fetch('/api/a1/districts?'+new URLSearchParams({code}),{signal:AbortSignal.timeout(20000)});const result=await response.json();if(!response.ok||result.code!=='OK')throw new Error(result.message||'地区加载失败');return result.data[0]?.districts||[];}
async function loadCities(){const code=provinceSelect.value;citySelect.disabled=true;try{const items=await districtData(code);if(code!==provinceSelect.value)return;const cities=items.length?items:[{name:provinceSelect.selectedOptions[0].textContent}];fillOptions(citySelect,cities,true);}catch(e){locationStatus.textContent=e.message+'，可稍后重试或使用定位。';}finally{citySelect.disabled=false;}}
provinceSelect.onchange=loadCities;
placesDialog.addEventListener('toggle',async()=>{if(!placesDialog.open||districtLoaded)return;districtLoaded=true;try{const provinces=await districtData('中国');fillOptions(provinceSelect,provinces);provinceSelect.value='430000';await loadCities();}catch(e){districtLoaded=false;locationStatus.textContent='地区加载失败，保留长沙选项，可重开窗口重试。';}});
locateButton.onclick=()=>{
 if(!navigator.geolocation){locationStatus.textContent='当前浏览器不支持定位，请手动选择城市。';return;}
 locateButton.disabled=true;locationStatus.textContent='正在获取位置，请在浏览器提示中允许定位…';
 navigator.geolocation.getCurrentPosition(async position=>{try{
  const response=await fetch('/api/a1/location',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({longitude:position.coords.longitude,latitude:position.coords.latitude}),signal:AbortSignal.timeout(35000)});const result=await response.json();if(!response.ok||result.code!=='OK')throw new Error(result.message||'地址解析失败');
  const place=result.data;if(!place.city)throw new Error('未能识别城市，请手动选择。');
  const province=Array.from(provinceSelect.options).find(o=>o.textContent===place.province);if(province)provinceSelect.value=province.value;
  let option=Array.from(citySelect.options).find(o=>o.value===place.city);if(!option){option=new Option(place.city,place.city);citySelect.append(option);}citySelect.value=place.city;
  locationStatus.textContent='已更新查询城市。定位结果不是到达景点记录。';showLocationResult(place,position);
 }catch(e){locationStatus.textContent=e.message+'，请手动选择城市。';}finally{locateButton.disabled=false;}},error=>{locateButton.disabled=false;locationStatus.textContent=error.code===1?'未获得定位授权，您仍可手动选择城市。':error.code===3?'定位超时，请重试或手动选择。':'暂时无法获取位置，请检查设备定位设置。';},{enableHighAccuracy:true,timeout:12000,maximumAge:60000});
};

const moduleDialog=document.querySelector('#module-dialog');
function moduleNotice(title,description){document.querySelector('#module-title').textContent=title;document.querySelector('#module-description').textContent=description;moduleDialog.showModal();}
document.querySelector('#module-close').onclick=()=>moduleDialog.close();document.querySelector('#module-action').onclick=()=>moduleDialog.close();
document.querySelector('#dock-home').onclick=()=>moduleNotice('首页','这里将连接队友的老人首页：出游、休息、找人帮忙。当前是 A1 问答页独立预览，尚未接入首页。');
document.querySelector('#dock-guide').onclick=()=>{document.querySelector('#guide-badge').hidden=true;closeSidebar();placesDialog.showModal();};
document.querySelector('#dock-profile').onclick=()=>{document.querySelector('#menu').click();};
document.querySelector('#dock-help').onclick=()=>moduleNotice('求助入口尚未接通','本预览没有发送求助、通知家属或联系工作人员。完整平台将在这里接入团队的求助流程；如当前需要帮助，请直接联系身边工作人员或家人。');
function updateGuideBadge(count){const badge=document.querySelector('#guide-badge');badge.hidden=count===0;badge.textContent=String(count);badge.setAttribute('aria-label','本次查到 '+count+' 个地点');badge.classList.remove('badge-enter');void badge.offsetWidth;badge.classList.add('badge-enter');}

const mapDialog=document.querySelector('#map-dialog'),placeMapEl=document.querySelector('#place-map'),mapStatus=document.querySelector('#map-status'),mapRetry=document.querySelector('#map-retry');let AMapSDK=null,placeMap=null,placeOverlays=[],mapPlace=null,mapZoom=15,mapNearbyPlaces=[],mapNearbyEpoch=0;
function mapCoords(value){return/^\d+(?:\.\d+)?,\d+(?:\.\d+)?$/.test(value||'')?value.split(',').map(Number):null;}
function placePin(text,center){const element=document.createElement('button');element.type='button';element.className=center?'place-pin place-pin-center':'place-pin';element.textContent=text;return element;}
function syncPlaceZoom(){const zoom=placeMap?placeMap.getZoom():mapZoom;document.querySelector('#map-zoom').textContent=String(Math.round(zoom));document.querySelector('#map-out').disabled=zoom<=8;document.querySelector('#map-in').disabled=zoom>=18;}
async function ensurePlaceMap(){
 if(placeMap)return placeMap;
 const map=await window.loadMapSdk();AMapSDK=map;
 placeMap=new map.Map('place-map',{viewMode:'2D',zoom:mapZoom,resizeEnable:true,dragEnable:true,zoomEnable:true});
 placeMap.on('zoomchange',syncPlaceZoom);placeMap.on('complete',()=>{placeMap.resize?.();syncPlaceZoom();});
 syncPlaceZoom();return placeMap;
}
function paintPlaceMap(){
 if(!placeMap||!mapPlace)return;
 placeMap.remove(placeOverlays);placeOverlays=[];
 const center=mapCoords(mapPlace.location);
 if(!center){mapStatus.hidden=false;mapStatus.textContent='该地点暂无有效地图坐标。';return;}
 placeOverlays.push(new AMapSDK.Marker({position:center,content:placePin('A',true),anchor:'bottom-center',title:mapPlace.name,zIndex:120}));
 mapNearbyPlaces.forEach((place,index)=>{const at=mapCoords(place.location);if(!at)return;placeOverlays.push(new AMapSDK.Marker({position:at,content:placePin(String(index+1),false),anchor:'bottom-center',title:place.name,zIndex:100+index}));});
 placeMap.add(placeOverlays);
 placeMap.setFitView(placeOverlays,false,[26,104,Math.min(placeMapEl.clientHeight*.5,400)+26,26],17);
}
async function openPlaceMap(place){
 mapNearbyEpoch++;mapNearbyPlaces=[];document.querySelector('#nearby-map-list').replaceChildren();document.querySelectorAll('[data-nearby]').forEach(b=>b.setAttribute('aria-pressed','false'));
 mapPlace=place;mapZoom=15;document.querySelector('#map-title').textContent=place.name;document.querySelector('#map-address').textContent=place.address;
 const detail=document.querySelector('#map-detail-content');detail.hidden=true;document.querySelector('#map-details').setAttribute('aria-expanded','false');
 detail.textContent='坐标（高德）：'+(place.location||'暂无')+'。来源：高德地点查询。当前为可拖动缩放的交互地图，暂不支持实时导航。';
 mapStatus.hidden=false;mapStatus.textContent='正在打开交互地图…';mapRetry.hidden=true;mapDialog.showModal();
 try{await ensurePlaceMap();mapStatus.hidden=true;mapStatus.textContent='';mapRetry.hidden=true;paintPlaceMap();}
 catch(error){mapStatus.hidden=false;mapStatus.textContent=error.message||'地图加载失败，请检查网络。';mapRetry.hidden=false;}
}
document.querySelector('#map-close').onclick=()=>mapDialog.close();
document.querySelector('#map-in').onclick=()=>{if(placeMap&&placeMap.getZoom()<18)placeMap.zoomIn();};
document.querySelector('#map-out').onclick=()=>{if(placeMap&&placeMap.getZoom()>8)placeMap.zoomOut();};
mapRetry.onclick=()=>openPlaceMap(mapPlace);
document.querySelector('#map-details').onclick=()=>{const content=document.querySelector('#map-detail-content');content.hidden=!content.hidden;document.querySelector('#map-details').setAttribute('aria-expanded',String(!content.hidden));};
function showLocationResult(place,position){document.querySelector('#location-result').hidden=false;document.querySelector('#location-result-address').textContent=place.address;document.querySelector('#location-result-details').textContent='设备报告精度约 '+Math.round(position.coords.accuracy)+' 米；获取于 '+new Date(position.timestamp).toLocaleTimeString()+'。地址由高德解析，本次仅用于查询城市。';flipLocation(false);}
function flipLocation(back){const card=document.querySelector('#location-result');card.classList.remove('flipping');void card.offsetWidth;card.classList.add('flipping');document.querySelector('#location-result-front').hidden=back;document.querySelector('#location-result-back').hidden=!back;}
document.querySelector('#location-detail-open').onclick=()=>flipLocation(true);document.querySelector('#location-detail-close').onclick=()=>flipLocation(false);

const speechPlayer=document.querySelector('#speech-player'),voiceState=document.querySelector('#voice-state'),recordButton=document.querySelector('#record-voice');let recorder=null,micStream=null,recordTimer=null,voiceProcessing=false;
const navHandle=document.querySelector('#nav-handle'),mainNavigation=document.querySelector('#main-navigation');let navTouchY=null,navLastSwipe=0;
function expandNavigation(open){mainNavigation.hidden=!open;navHandle.setAttribute('aria-expanded',String(open));navHandle.querySelector('span').textContent=open?'收起导航':'展开导航';}
navHandle.onclick=()=>{if(Date.now()-navLastSwipe>500)expandNavigation(mainNavigation.hidden);};
navHandle.addEventListener('touchstart',e=>{navTouchY=e.touches[0].clientY;},{passive:true});
navHandle.addEventListener('touchend',e=>{if(navTouchY!==null){const distance=navTouchY-e.changedTouches[0].clientY;if(Math.abs(distance)>20){navLastSwipe=Date.now();expandNavigation(distance>0);}navTouchY=null;}},{passive:true});
input.addEventListener('focus',()=>expandNavigation(false));
document.querySelector('#exit-ask').onclick=()=>{let sameOrigin=false;try{sameOrigin=Boolean(document.referrer)&&new URL(document.referrer).origin===location.origin;}catch{}if(sameOrigin&&history.length>1){history.back();return;}moduleNotice('退出问问','当前是问问页独立预览，平台首页尚未接入。可使用浏览器返回，或暂时关闭本标签页；聊天不会发送到其他页面。');};

function setTypingMode(){input.hidden=false;resizeInput();}
const voiceStatusObserver=new MutationObserver(()=>{
 const recording=recorder?.state==='recording';recordButton.classList.toggle('recording',recording);recordButton.setAttribute('aria-label',recording?'结束录音':'语音输入');recordButton.title=recording?'正在录音，点击结束':'点击说话';
 voiceState.classList.toggle('sr-only',voiceState.textContent==='点击输入框开始说话，也可切换打字');
});voiceStatusObserver.observe(voiceState,{childList:true,characterData:true,subtree:true});


const composerBox=document.querySelector('.composer-box');
input.addEventListener('focus',()=>{composerBox.classList.add('editing');expandNavigation(false);});
input.addEventListener('blur',()=>{if(!input.value.trim())composerBox.classList.remove('editing');});
input.addEventListener('input',()=>composerBox.classList.toggle('has-text',Boolean(input.value.trim())));

const placeInfoDialog=document.querySelector('#place-info-dialog'),placeInfoBody=document.querySelector('#place-info-body');let infoRequest=null;
document.querySelector('#place-info-close').onclick=()=>placeInfoDialog.close();placeInfoDialog.addEventListener('close',()=>{infoRequest?.abort();});
async function queryPlaceInformation(kind,category){
 if(!mapPlace)return;infoRequest?.abort();const controller=new AbortController();infoRequest=controller;
 document.querySelector('#place-info-title').textContent=kind==='weather'?'当地天气':'附近'+category;placeInfoBody.replaceChildren();const loading=document.createElement('p');loading.textContent='正在查询高德数据…';placeInfoBody.append(loading);placeInfoDialog.showModal();
 try{const params=new URLSearchParams({id:mapPlace.id});if(category)params.set('category',category);const timer=setTimeout(()=>controller.abort(),45000);let response;try{response=await fetch('/api/a1/'+kind+'?'+params,{signal:controller.signal});}finally{clearTimeout(timer);}const result=await response.json();if(!response.ok||result.code!=='OK')throw new Error(result.message||'查询失败');if(infoRequest!==controller)return;placeInfoBody.replaceChildren();
 if(kind==='nearby'){
 const note=document.createElement('p');note.className='wizard-note';note.textContent='以“'+mapPlace.name+'”为中心检索约3公里范围，不代表您的当前位置；尚未核实营业和无障碍情况。';placeInfoBody.append(note);
 if(!result.data.places.length){const empty=document.createElement('p');empty.textContent='本次没有查到地点，可更换分类。';placeInfoBody.append(empty);}
 for(const place of result.data.places){const button=document.createElement('button');button.className='nearby-result';const name=document.createElement('strong'),address=document.createElement('span');name.textContent=place.name;address.textContent=place.address;button.append(name,address);button.onclick=()=>{placeInfoDialog.close();openPlaceMap(place);};placeInfoBody.append(button);}
 }else{
 const live=result.data.lives?.[0];if(live){const main=document.createElement('div');main.className='weather-main';const title=document.createElement('h3'),temp=document.createElement('strong'),detail=document.createElement('p');title.textContent=live.city;temp.textContent=live.temperature+'°';detail.textContent=live.weather+' · 风力 '+live.windpower+' 级 · 湿度 '+live.humidity+'%';main.append(title,temp,detail);const time=document.createElement('p');time.className='wizard-note';time.textContent='高德天气实况 · 发布于 '+live.reporttime;main.append(time);placeInfoBody.append(main);}
 for(const cast of result.data.forecasts?.[0]?.casts||[]){const line=document.createElement('div');line.className='weather-day';const date=document.createElement('strong'),detail=document.createElement('span');date.textContent=cast.date;detail.textContent=cast.dayweather+' / '+cast.nightweather+'　'+cast.nighttemp+'–'+cast.daytemp+'°';line.append(date,detail);placeInfoBody.append(line);}
 const note=document.createElement('p');note.className='wizard-note';note.textContent='仅展示接口已返回日期；超出预报范围的出游日期，不能据此断定天气。';placeInfoBody.append(note);
 }
 }catch(error){if(!placeInfoDialog.open)return;placeInfoBody.replaceChildren();const text=document.createElement('p');text.textContent=error.name==='AbortError'?'查询超时或已取消，请重试。':error.message;const retry=document.createElement('button');retry.className='wizard-primary';retry.textContent='重新查询';retry.onclick=()=>queryPlaceInformation(kind,category);placeInfoBody.append(text,retry);}
}
document.querySelector('#map-weather').onclick=()=>queryPlaceInformation('weather');document.querySelectorAll('[data-nearby]').forEach(button=>button.onclick=()=>showNearbyMarkers(button));

async function showNearbyMarkers(button){
 if(!mapPlace)return;const epoch=++mapNearbyEpoch;const list=document.querySelector('#nearby-map-list');list.replaceChildren();const message=document.createElement('p');message.textContent='正在查询附近'+button.dataset.nearby+'…';list.append(message);document.querySelectorAll('[data-nearby]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 try{const response=await fetch('/api/a1/nearby?'+new URLSearchParams({id:mapPlace.id,category:button.dataset.nearby}),{signal:AbortSignal.timeout(20000)});const data=await response.json();if(!response.ok||data.code!=='OK')throw new Error(data.message||'查询失败');if(epoch!==mapNearbyEpoch)return;mapNearbyPlaces=data.data.places.filter(p=>/^\d+(?:\.\d+)?,\d+(?:\.\d+)?$/.test(p.location)).slice(0,8);list.replaceChildren();const note=document.createElement('p');note.textContent=mapNearbyPlaces.length?'地图编号与下面地点一一对应，A 为查询中心。':'附近暂无查询结果';list.append(note);
 mapNearbyPlaces.forEach((place,index)=>{const b=document.createElement('button');b.textContent=(index+1)+'　'+place.name;b.onclick=()=>{const at=mapCoords(place.location);if(at)placeMap?.setZoomAndCenter(16,at);};list.append(b);});mapZoom=13;paintPlaceMap();
 }catch(e){if(epoch===mapNearbyEpoch){message.textContent=e.message+'，可重新点击分类重试。';}}
}
