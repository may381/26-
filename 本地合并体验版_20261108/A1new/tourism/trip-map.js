'use strict';
let sdkPromise=null,tripMap=null,tripMapEpoch=0,tripDayPlaces=[],tripMarkers=[],tripLines=[],tripAbort=null;
const tripFeedback=document.querySelector('#trip-map-feedback'),tripSheet=document.querySelector('#draft-sheet'),sheetHandle=document.querySelector('#sheet-handle');
function loadMapSdk(){if(window.AMap)return Promise.resolve(window.AMap);if(sdkPromise)return sdkPromise;sdkPromise=(async()=>{const response=await fetch('/tourism-api/api/a1/map-config',{signal:AbortSignal.timeout(8000)});const result=await response.json();if(!response.ok||result.code!=='OK')throw new Error(result.message||'地图配置读取失败');window._AMapSecurityConfig={serviceHost:location.origin+result.data.serviceHost};return new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='https://webapi.amap.com/maps?v=2.0&key='+encodeURIComponent(result.data.key);const timer=setTimeout(()=>{script.remove();reject(new Error('高德地图加载超时，请检查网络后重试'));},20000);script.onload=()=>{clearTimeout(timer);if(!window.AMap){reject(new Error('地图 SDK 未就绪'));return;}resolve(window.AMap);};script.onerror=()=>{clearTimeout(timer);reject(new Error('未能加载高德地图，请检查网络'));};document.head.append(script);});})();sdkPromise.catch(()=>{sdkPromise=null;});return sdkPromise;}window.loadMapSdk=loadMapSdk;
window.showTripDay=async(draft,day)=>{
 const epoch=++tripMapEpoch;tripAbort?.abort();tripAbort=new AbortController();tripFeedback.textContent='正在加载交互地图…';
 try{const AMap=await loadMapSdk();if(epoch!==tripMapEpoch||!draftDialog.open)return;if(!tripMap){tripMap=new AMap.Map('trip-map',{viewMode:'2D',zoom:12,center:[116.397,39.908],dragEnable:true,zoomEnable:true,resizeEnable:true});}
 tripMap.remove([...tripMarkers,...tripLines]);tripMarkers=[];tripLines=[];tripDayPlaces=day<0?draft.days.flatMap(d=>d.places):draft.days[day].places;
 const valid=tripDayPlaces.filter(p=>/^\d+(?:\.\d+)?,\d+(?:\.\d+)?$/.test(p.location));
 valid.forEach((place,index)=>{const content=document.createElement('button');content.className='trip-marker';content.type='button';content.textContent=String(index+1);content.setAttribute('aria-label',place.name);const marker=new AMap.Marker({position:place.location.split(',').map(Number),content,anchor:'bottom-center',title:place.name});marker.on('click',()=>selectTripPlace(place.id,true));tripMarkers.push(marker);});tripMap.add(tripMarkers);tripFeedback.textContent=valid.length?'地点已标记，正在整理当天交通路线…':'当天暂无可标记地点';fitTripMap();
 if(day<0){tripFeedback.textContent='总览 · '+valid.length+'个地点；切换日期查看当天路线';return;}
 if(valid.length<2){tripFeedback.textContent=valid.length?'可拖动、缩放地图，点击编号查看地点':'当天暂无地点';return;}
 const planned=day>=0?draft.days[day]:null;
 if(planned&&scheduledDay(planned)){
  const legs=planned.timeline.filter(s=>s.kind==='transport');let missing=0;
  for(const leg of legs){let drawn=0;
   for(const line of leg.polyline||[]){const path=line.split(';').filter(Boolean).map(point=>point.split(',').map(Number)).filter(p=>p.length===2&&p.every(Number.isFinite)&&Math.abs(p[0])<=180&&Math.abs(p[1])<=90);if(path.length<2)continue;
    tripLines.push(new AMap.Polyline({path,strokeColor:leg.mode==='driving'?'#267c9a':leg.mode==='transit'?'#3275be':'#303039',strokeWeight:5,strokeOpacity:.75,lineJoin:'round',lineCap:'round',showDir:true}));drawn++;}
   if(!drawn)missing++;
  }
  tripMap.add(tripLines);tripFeedback.textContent=missing?'部分路段没有路线形状，已标记地点；交通与休息见当天时间轴':'已显示查询所得路线 · 台阶与无障碍条件尚未核实';fitTripMap();return;
 }
 tripFeedback.textContent='旧草案未保存交通依据，仅显示地点；请重新生成草案以查看与时间轴一致的路线。';
 fitTripMap();
 }catch(error){if(epoch!==tripMapEpoch)return;tripFeedback.replaceChildren();const label=document.createElement('span');label.textContent=error.message||'地图加载失败';const retry=document.createElement('button');retry.textContent='重试';retry.onclick=()=>window.showTripDay(draft,day);tripFeedback.append(label,retry);}
};
function fitTripMap(){if(!tripMap||!tripMarkers.length||document.querySelector('.trip-nearby-bar button[aria-pressed=true]'))return;tripMap.resize?.();const height=document.querySelector('#draft-dialog').clientHeight;tripMap.setFitView([...tripMarkers,...tripLines],false,[220,35,Math.round(height*.56)+20,35],16);}
function selectTripPlace(id,fromMarker){const place=tripDayPlaces.find(p=>p.id===id);if(!place||!tripMap)return;tripMap.setZoomAndCenter(16,place.location.split(',').map(Number));tripMarkers.forEach(marker=>{const active=marker.getTitle()===place.name;marker.getContent().classList.toggle('selected',active);});const items=document.querySelectorAll('#draft-detail .draft-stop');items.forEach(item=>{const active=item.dataset.placeId===id;item.classList.toggle('map-selected',active);if(active&&fromMarker){window.setTripSheet(.55);item.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});}});}
window.focusTripPlace=id=>{window.setTripSheet(.3);selectTripPlace(id,false);};
let sheetHeight=.55,dragStart=null,lastDrag=0;
window.setTripSheet=ratio=>{sheetHeight=Math.max(.23,Math.min(.88,ratio));tripSheet.style.height=(sheetHeight*100)+'%';sheetHandle.setAttribute('aria-expanded',String(sheetHeight>.6));sheetHandle.querySelector('span').textContent=sheetHeight>.6?'收起行程':'展开行程';};
sheetHandle.onclick=()=>{if(Date.now()-lastDrag>400)window.setTripSheet(sheetHeight>.6?.3:.85);};
sheetHandle.onpointerdown=e=>{dragStart={y:e.clientY,height:sheetHeight};sheetHandle.setPointerCapture(e.pointerId);tripSheet.classList.add('dragging');};
sheetHandle.onpointermove=e=>{if(!dragStart)return;window.setTripSheet(dragStart.height+(dragStart.y-e.clientY)/draftDialog.clientHeight);};
sheetHandle.onpointerup=e=>{if(!dragStart)return;const moved=Math.abs(e.clientY-dragStart.y)>8;dragStart=null;tripSheet.classList.remove('dragging');if(moved){lastDrag=Date.now();const snaps=[.28,.55,.86];window.setTripSheet(snaps.reduce((a,b)=>Math.abs(b-sheetHeight)<Math.abs(a-sheetHeight)?b:a));}};
sheetHandle.onpointercancel=()=>{dragStart=null;tripSheet.classList.remove('dragging');};
document.querySelector('#trip-fit').onclick=()=>{window.setTripSheet(.55);fitTripMap();};draftDialog.addEventListener('close',()=>{tripMapEpoch++;tripAbort?.abort();});
