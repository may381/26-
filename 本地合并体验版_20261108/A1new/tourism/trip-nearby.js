'use strict';
const nearbyBar=node('nav',null,'trip-nearby-bar');nearbyBar.setAttribute('aria-label','行程地点周边设施');
const nearbyCaption=node('p','围绕当天第一个地点查询','trip-nearby-caption');nearbyCaption.setAttribute('role','status');
const nearbyResults=node('section',null,'trip-nearby-results');nearbyResults.hidden=true;
const tripNearbyCategories=[['住宿','酒店','hotel','▱'],['卫生间','卫生间','toilet','WC'],['美食','美食','food','食'],['饮品','饮品','drink','杯']];
let nearbyAnchor=null,nearbyOverlays=[],nearbyRequest=null,nearbyRevision=0,nearbyInfo=null;
const nearbyButtons=[];
function clearTripNearby(){nearbyRevision++;nearbyRequest?.abort();nearbyRequest=null;if(tripMap&&nearbyOverlays.length)tripMap.remove(nearbyOverlays);nearbyOverlays=[];nearbyInfo?.close();nearbyResults.hidden=true;nearbyResults.replaceChildren();nearbyButtons.forEach(b=>b.setAttribute('aria-pressed','false'));}
for(const [category,label,kind,glyph] of tripNearbyCategories){const button=choiceButton(label,()=>queryTripNearby(button,category,label,kind,glyph));button.setAttribute('aria-pressed','false');nearbyBar.append(button);nearbyButtons.push(button);}
const nearbyClear=choiceButton('清除',()=>{clearTripNearby();nearbyCaption.textContent=nearbyAnchor?'周边中心：'+nearbyAnchor.name:'请先选择行程地点';});nearbyBar.append(nearbyClear);
draftDialog.append(nearbyBar,nearbyCaption,nearbyResults);
const baseTripDay=window.showTripDay;
window.showTripDay=(draft,day)=>{clearTripNearby();nearbyAnchor=(day<0?draft.days.flatMap(d=>d.places):draft.days[day].places)[0]||null;nearbyCaption.textContent=nearbyAnchor?'周边中心：'+nearbyAnchor.name+' · 点击编号可切换':'当天没有地点，可先添加';return baseTripDay(draft,day);};
const baseTripSelect=selectTripPlace;
selectTripPlace=function(id,fromMarker){const p=tripDayPlaces.find(p=>p.id===id);if(p&&nearbyAnchor?.id!==p.id){clearTripNearby();nearbyAnchor=p;nearbyCaption.textContent='周边中心：'+p.name;}return baseTripSelect(id,fromMarker);};
draftDialog.addEventListener('close',clearTripNearby);
async function queryTripNearby(button,category,label,kind,glyph){
 if(button.getAttribute('aria-pressed')==='true'){clearTripNearby();nearbyCaption.textContent='周边中心：'+(nearbyAnchor?.name||'未选择');return;}
 if(!nearbyAnchor||!tripMap||!window.AMap){nearbyCaption.textContent='请等待地图加载，并选择一个行程地点。';return;}
 clearTripNearby();const revision=nearbyRevision,anchor=nearbyAnchor;button.setAttribute('aria-pressed','true');nearbyCaption.textContent='正在查询「'+anchor.name+'」附近的'+label+'…';nearbyRequest=new AbortController();
 try{
  const response=await fetch('/tourism-api/api/a1/nearby?'+new URLSearchParams({id:anchor.id,category}),{signal:AbortSignal.any([nearbyRequest.signal,AbortSignal.timeout(25000)])});const result=await response.json();
  if(revision!==nearbyRevision||!draftDialog.open)return;if(!response.ok||result.code!=='OK')throw new Error(result.message||'周边查询失败');
  const places=(result.data.places||[]).filter(p=>/^\d+(?:\.\d+)?,\d+(?:\.\d+)?$/.test(p.location)).slice(0,8);
  nearbyCaption.textContent=anchor.name+'附近 · 查到'+places.length+'处'+label+' · 非您的实时位置';
  nearbyResults.replaceChildren();nearbyResults.hidden=!places.length;
  for(const [index,place] of places.entries()){
   const content=choiceButton('');content.className='nearby-poi-marker poi-'+kind;content.setAttribute('aria-label',label+'：'+place.name);content.append(node('span',glyph),node('small',String(index+1)));
   const marker=new AMap.Marker({position:place.location.split(',').map(Number),content,anchor:'bottom-center',title:place.name,zIndex:130});
   const reveal=()=>{
    nearbyInfo?.close();const body=node('section',null,'nearby-poi-info');body.append(node('strong',place.name),node('p',place.address||'地址暂未提供'),node('p','高德地点资料 · 营业与无障碍情况待确认','import-note'));
    const close=choiceButton('关闭',()=>nearbyInfo?.close());body.append(close);nearbyInfo=new AMap.InfoWindow({content:body,offset:new AMap.Pixel(0,-30),autoMove:true});nearbyInfo.open(tripMap,place.location.split(',').map(Number));
   };marker.on('click',reveal);nearbyOverlays.push(marker);
   const item=choiceButton((index+1)+'. '+place.name,()=>{tripMap.setZoomAndCenter(16,place.location.split(',').map(Number));reveal();});nearbyResults.append(item);
  }
  tripMap.add(nearbyOverlays);window.setTripSheet(.28);
  if(places.length)tripMap.setFitView(nearbyOverlays,false,[210,40,Math.round(draftDialog.clientHeight*.3)+30,40],16);
  else nearbyCaption.textContent='本次未查到'+label+'，可切换行程地点后重试；不代表附近没有。';
 }catch(e){if(revision!==nearbyRevision)return;button.setAttribute('aria-pressed','false');nearbyCaption.textContent=e.name==='TimeoutError'?'周边查询超时，点击分类可重试。':e.message||'周边查询失败，请重试。';}
}
