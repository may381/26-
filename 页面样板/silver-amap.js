(()=>{
let sdkPromise;
const active=new Map();
function load(){if(window.AMap)return Promise.resolve(window.AMap);if(sdkPromise)return sdkPromise;
 sdkPromise=new Promise((resolve,reject)=>{
  if(!window.SILVER_AMAP_CONFIG){reject(Error('未找到地图配置'));return}
  window._AMapSecurityConfig={securityJsCode:window.SILVER_AMAP_CONFIG.securityJsCode};
  const script=document.createElement('script');let settled=false;
  const finish=(error)=>{if(settled)return;settled=true;clearTimeout(timeout);if(error){script.remove();reject(error)}else resolve(window.AMap)};
  const timeout=setTimeout(()=>finish(Error('高德地图加载超时，请检查网络后重试')),20000);
  script.src='https://webapi.amap.com/maps?v=2.0&key='+encodeURIComponent(window.SILVER_AMAP_CONFIG.key);
  script.onload=()=>finish(window.AMap?null:Error('地图服务未就绪，请检查 Key 与域名设置'));
  script.onerror=()=>finish(Error('无法连接高德地图，请检查网络或 Key 配置'));
  document.head.append(script);
 }).catch(error=>{sdkPromise=null;throw error});return sdkPromise}
function errorState(host,error){if(!host.isConnected)return;const state=host.parentElement.querySelector('.amap-state');state.hidden=false;state.replaceChildren();const text=document.createElement('span');text.textContent=error.message;const retry=document.createElement('button');retry.textContent='重新加载';retry.onclick=()=>{const previous=active.get(host);if(previous){clearTimeout(previous._silverTimer);previous.destroy();active.delete(host)}init(host)};state.append(text,retry)}
async function init(host){if(host.dataset.initializing==='true'||active.has(host))return;host.dataset.initializing='true';const state=host.parentElement.querySelector('.amap-state');state.hidden=false;state.textContent='正在加载高德地图…';
try{const AMap=await load();if(!host.isConnected)return;
const map=new AMap.Map(host,{viewMode:'2D',zoom:15,center:[112.9398,28.1868],resizeEnable:true});active.set(host,map);
const timeout=setTimeout(()=>errorState(host,Error('地图瓦片尚未加载，请检查网络后重试')),20000);
map.on('complete',()=>{clearTimeout(timeout);state.hidden=true});
const places=[['游客中心',[112.94175,28.18386]],['爱晚亭',[112.93683,28.18721]],['观景台',[112.93982,28.19018]],['休息点（示例）',[112.94272,28.18778]]];
map.add(places.map(([name,position])=>new AMap.Marker({position,title:name,label:{content:name,direction:'top'}})));
map.add(new AMap.Polyline({path:[[112.94175,28.18386],[112.94082,28.18492],[112.93974,28.18578],[112.93831,28.18654],[112.93683,28.18721],[112.93812,28.18866],[112.93982,28.19018]],strokeColor:'#2e73d7',strokeWeight:6,lineJoin:'round',lineCap:'round',showDir:true}));
host.parentElement.querySelector('.amap-recenter').onclick=()=>{map.setZoomAndCenter(15,[112.9398,28.1868])};
state.textContent='地图初始化中…';
active.get(host)._silverTimer=timeout;
}catch(error){errorState(host,error)}finally{delete host.dataset.initializing}}
function sync(){for(const [host,map] of active){if(!host.isConnected){clearTimeout(map._silverTimer);map.destroy();active.delete(host)}}document.querySelectorAll('.amap-host').forEach(init)}
new MutationObserver(sync).observe(document.getElementById('surface'),{childList:true});sync();
window.addEventListener('resize',()=>active.forEach(map=>map.resize()));
})();
