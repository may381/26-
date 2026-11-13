import {reactive} from 'vue'
import {routes,setServerRoutes,setServerFacilities,resetRoutes,resetFacilities} from './travel-data.js'
import {USE_SERVER} from '../api/config.js'
import * as api from '../api/index.js'
import * as chain2 from '../api/chain2.js'
import {adaptProfile,adaptPreferences,adaptRoutes,adaptRecordDetail,adaptFacilityGroup,profilePatch,adaptActiveTrip} from '../api/adapters.js'
import {actor,actorKey,actorList,setActor,userId as currentUserId} from '../api/session.js'

const clone=v=>JSON.parse(JSON.stringify(v))
const defaults={onboarded:false,profile:{nickname:'王阿姨',age:66,city:'深圳',language:'普通话',emergencyContact:{name:'',phone:'',relation:''}},preferences:null,plan:null,tour:null,help:null,'help-events':[],family:{relations:[{id:'daughter',name:'王小明',relation:'女儿',phone:'',status:'ACTIVE',permissions:{position:false,progress:true,help:true}}]},'family-suggestion':null,notifications:[{id:'welcome',type:'reminder',title:'出门记得带水',body:'演示提醒：穿舒适鞋，带水和手机。',time:Date.now(),unread:true,target:'plan'},{id:'message',type:'family',title:'女儿留言',body:'演示留言：今天出门记得添衣。',time:Date.now(),unread:true}],favorites:[],'trip-record':null,settings:{fontSize:'standard',speechRate:'slow',inputMode:'voice',guideSeen:false},chat:[],route:0}
defaults['trip-photos']={}
export function readState(key){const v=uni.getStorageSync('elder-'+key);return v===''||v==null?clone(defaults[key]??null):v}
export const state=reactive({})
export function writeState(key,value){uni.setStorageSync('elder-'+key,clone(value));state[key]=clone(value)}
export function removeState(key){uni.removeStorageSync('elder-'+key);state[key]=clone(defaults[key]??null)}
export function refreshState(){Object.keys(defaults).forEach(k=>state[k]=readState(k));syncServer()}
export function migrate(){if(!uni.getStorageSync('elder-settings')){writeState('settings',{...defaults.settings,fontSize:uni.getStorageSync('elder-large')?'large':'standard',speechRate:uni.getStorageSync('elder-slow')?'slow':'normal'})}if(!uni.getStorageSync('elder-preferences')){const old=uni.getStorageSync('elder-confirmed-preferences')||uni.getStorageSync('elder-travel-preferences');if(old)writeState('preferences',{walkDuration:old.walkDuration??null,pace:old.pace||'',stairs:old.stairs||(old.flat?'少台阶':''),interests:old.interests||[],avoid:old.avoid||[],updatedAt:old.confirmedAt||Date.now()})}if(!uni.getStorageSync('elder-favorites')&&uni.getStorageSync('elder-park-favorite'))writeState('favorites',[{type:'scenic',name:'清风园',sub:'演示景区',addedAt:Date.now()}]);const help=uni.getStorageSync('elder-help');if(help&&!['OPEN','ACKNOWLEDGED','RESOLVED'].includes(help.status))removeState('help');Object.keys(defaults).forEach(k=>{const v=uni.getStorageSync('elder-'+k);if(v===''||v==null)uni.setStorageSync('elder-'+k,clone(defaults[k]))});refreshState()}
export function resetState(){for(const key of [...Object.keys(defaults),'large','slow','travel-preferences','confirmed-preferences','park-favorite','server-trip','server-trips','records'])uni.removeStorageSync('elder-'+key);state.records=[];state.tour=null;refreshState()}
export function notify(type,title,body,target){writeState('notifications',[{id:String(Date.now())+Math.random(),type,title,body:'演示数据 · '+body,time:Date.now(),unread:true,target},...readState('notifications')])}
export function activeFamily(){return state.family.relations.find(r=>r.status==='ACTIVE')}
export const helpLabels={OPEN:'求助已发出',ACKNOWLEDGED:'工作人员已接单',RESOLVED:'已解决'}
export function createHelp(){const old=readState('help');if(old&&old.status!=='RESOLVED')return old;const now=Date.now(),t=tourView();const h={id:String(now),type:'GENERAL',reason:'走累了，需要协助',location:t?.currentStop?.name||'位置未提供（演示）',status:'OPEN',timeline:[{label:'已发出',time:now,body:'演示求助已创建，未实际联系工作人员。'}],notifications:[],createdAt:now,updatedAt:now};saveHelp(h);return h}
function saveHelp(h){const family=activeFamily();if(family?.permissions.help){h.notifications.push({to:family.name,time:Date.now(),body:helpLabels[h.status]});notify('help','家属求助通知',family.name+'：'+helpLabels[h.status],'tour-help')}writeState('help',h);const events=readState('help-events');writeState('help-events',[h,...events.filter(e=>e.id!==h.id)]);notify('help',helpLabels[h.status],h.reason,'tour-help')}
export function updateHelp(id,action){const h=clone(readState('help-events').find(e=>e.id===id)||readState('help'));if(!h)return;if(action==='ack'&&h.status==='OPEN')h.status='ACKNOWLEDGED';else if(action==='resolve'&&h.status==='ACKNOWLEDGED')h.status='RESOLVED';else if(action!=='progress'||h.status!=='ACKNOWLEDGED')return;h.updatedAt=Date.now();h.timeline.push({label:action==='progress'?'处理中':helpLabels[h.status],time:h.updatedAt,body:'景区端更新（演示）'});saveHelp(h)}

/* ===================== 后端（链路一） ===================== */

const TRIP_KEY='elder-server-trip'
const TRIP_HISTORY_KEY='elder-server-trips'
let spotsById={},lastSync=0,syncing=null
state.server={online:false,loading:false,error:'',syncedAt:0}
state.records=[]

export {actor,actorKey,actorList,setActor}
export const serverOnline=()=>!!state.server.online
export const currentActor=actor
export const currentUserIdValue=currentUserId

function savedTrip(){const v=uni.getStorageSync(TRIP_KEY);return v&&v.tripId?v:null}

export function buildTourView(t){
  const route=routes[Number(t.route)]||routes[0]
  const stations=route.stations||[]
  const elapsed=Math.max(0,Math.floor(((t.endedAt||Date.now())-t.startedAt)/60000))
  const finishAt=t.estimatedFinishAt==null?NaN:new Date(t.estimatedFinishAt).getTime()
  const remaining=t.ended?0:t.estimatedFinishAt===undefined?Math.max(0,(Number(t.remainingMin??route.minutes)||0)-Math.max(0,elapsed-(Number(t.elapsedMin)||0))):t.estimatedFinishAt===null?null:Number.isFinite(finishAt)?Math.max(0,Math.round((finishAt-Date.now())/60000)):null
  const current=Math.min(t.current||0,Math.max(0,stations.length-1))
  const skipped=t.skipped||[]
  const next=stations.find((s,i)=>i>current&&!skipped.includes(i))
  return {...t,visited:t.visited||[0],skipped,restInserted:t.restInserted||0,startClock:t.startClock||new Date(t.startedAt).toTimeString().slice(0,5),routeData:route,current,elapsedMin:elapsed,remainingMin:remaining,currentStop:stations[current],nextStop:next,progress:Math.min(100,Math.round(elapsed/Math.max(1,elapsed+remaining)*100))}
}

export function tourView(){const t=state.tour;if(!t)return null;if(t.backend)return buildTourView(t);const route=routes[Number(t.route)]||routes[0];const current=Number(t.current)||0;const elapsed=Math.max(Number(t.elapsedMin)||0,Math.floor(((t.endedAt||Date.now())-t.startedAt)/60000));const skipped=t.skipped||[];const next=route.stations.find(s=>s.id>current&&!skipped.includes(s.id));const remaining=t.ended?0:Math.max(0,(Number(t.remainingMin??route.minutes) || 0)-Math.max(0,elapsed-(Number(t.elapsedMin)||0)));return {...t,visited:t.visited||[0],skipped,restInserted:t.restInserted||0,startClock:t.startClock||new Date(t.startedAt).toTimeString().slice(0,5),routeData:route,current,elapsedMin:elapsed,remainingMin:remaining,currentStop:route.stations[current],nextStop:next,progress:Math.min(100,Math.round(elapsed/Math.max(1,elapsed+remaining)*100))}}

function buildTour(trip,progress,saved,routeIndex,adjusted){
  const route=routes[routeIndex>=0?routeIndex:0]
  const snapshot={...progress,...trip}
  const active=adaptActiveTrip(snapshot)
  const started=active.startedAt?new Date(active.startedAt).getTime():saved.startedAt
  const visitedIds=active.visitedSpotIds
  const idxOf=id=>(route.stations||[]).findIndex(s=>s.spotId===id)
  const visited=visitedIds.map(idxOf).filter(i=>i>=0)
  const currentIndex=idxOf(active.currentSpotId)
  const current=currentIndex>=0?currentIndex:visited.length?Math.max(...visited):0
  const finishAt=active.estimatedFinishAt==null?NaN:new Date(active.estimatedFinishAt).getTime()
  const remaining=active.estimatedFinishAt===undefined?route.minutes:active.estimatedFinishAt===null?null:Number.isFinite(finishAt)?Math.max(0,Math.round((finishAt-Date.now())/60000)):null
  return {...active,id:active.tripId,tripVersion:active.tripVersion||saved.tripVersion||0,route:routeIndex>=0?routeIndex:0,routeId:route.routeId,plan:state.plan,startedAt:started,startClock:new Date(started).toTimeString().slice(0,5),current,visited:visited.length?visited:[0],visitedSpotIds:visitedIds,skipped:active.skippedSpotIds.map(idxOf).filter(i=>i>=0),adjusted:!!adjusted,elapsedMin:0,remainingMin:remaining,ended:false,endedAt:null,restInserted:0,backend:true}
}

export function currentTripVersion(){return state.tour?.tripVersion||0}

async function tourActionError(e,title){
  if(e.status===409){
    await syncActiveTrip()
    uni.showModal({title:'游览状态已更新',content:'请刷新后重试',showCancel:false})
  }else uni.showModal({title,content:e.message||'请稍后重试',showCancel:false})
  return null
}

export async function serverSkipStop(stationIndex){
  const t=state.tour;if(!USE_SERVER||!t||!t.backend)return null
  try{
    const route=routes[Number(t.route)],station=route.stations[stationIndex]
    await api.skipStop(t.tripId,station.spotId,t.tripVersion||0)
    await syncActiveTrip();return true
  }catch(e){return tourActionError(e,'跳过未成功')}
}

export async function serverStartRest(plannedMinutes){
  const t=state.tour;if(!USE_SERVER||!t||!t.backend)return null
  try{
    const route=routes[Number(t.route)]
    const spot=spotsById[t.currentSpotId||route.stations[t.current].spotId]
    const coordinates=spot?.location||spot
    if(coordinates?.lat==null||coordinates?.lng==null)throw new Error('当前站点坐标暂不可用，请刷新后重试')
    await api.createRest(t.tripId,{expectedTripVersion:t.tripVersion||0,plannedMinutes,location:{lat:coordinates.lat,lng:coordinates.lng,coordinateSystem:spot.coordinateSystem||'WGS84'}})
    await syncActiveTrip();return true
  }catch(e){return tourActionError(e,'开始休息未成功')}
}

export async function serverExtendRest(additionalMinutes){
  const t=state.tour;if(!USE_SERVER||!t||!t.backend)return null
  try{
    if(!t.activeRest?.id)throw new Error('当前没有进行中的休息，请刷新后重试')
    await api.extendRest(t.tripId,t.activeRest.id,{expectedTripVersion:t.tripVersion||0,additionalMinutes})
    await syncActiveTrip();return true
  }catch(e){return tourActionError(e,'延长休息未成功')}
}

export async function serverFinishRest(){
  const t=state.tour;if(!USE_SERVER||!t||!t.backend)return null
  try{
    if(!t.activeRest?.id)throw new Error('当前没有进行中的休息，请刷新后重试')
    await api.finishRest(t.tripId,t.activeRest.id,{expectedTripVersion:t.tripVersion||0})
    await syncActiveTrip();return true
  }catch(e){return tourActionError(e,'结束休息未成功')}
}

export async function syncActiveTrip(){
  if(!USE_SERVER)return null
  const saved=savedTrip()
  if(!saved){
    try{
      const trip=await api.getActiveTrip()
      if(trip){
        const restored={tripId:trip.id,startedAt:Date.now()}
        uni.setStorageSync(TRIP_KEY,restored)
        writeState('tour',buildTour(trip,null,restored,routes.findIndex(r=>r.routeId===trip.routeId),false))
        return state.tour
      }
    }catch(e){/* 404/405 尚未部署或后端离线：静默保留本地演示路径 */}
    if(state.tour&&state.tour.backend&&!state.tour.ended)state.tour=null
    return null
  }
  try{
    const trip=await api.getTrip(saved.tripId)
    if(!trip||trip.status!=='ACTIVE'){
      uni.removeStorageSync(TRIP_KEY)
      // 已结束的游览保留在当前状态里，游后页还要用它显示「已结束」。
      if(state.tour&&state.tour.tripId===saved.tripId)return state.tour
      return null
    }
    let progress=null
    try{progress=await api.getProgress(saved.tripId)}catch(e){/* 尚未上报进度 */}
    // 改过线时以最新一次调整的路线为准（Trip 自身的 routeId 不会变）。
    let adjustment=null
    try{
      const list=await api.listAdjustments(saved.tripId)
      if(Array.isArray(list)&&list.length)adjustment=list.reduce((a,b)=>(b.revision>a.revision?b:a),list[0])
    }catch(e){/* 没有调整记录 */}
    const effectiveRouteId=adjustment?adjustment.routeId:trip.routeId
    const routeIndex=routes.findIndex(r=>r.routeId===effectiveRouteId)
    writeState('tour',buildTour(trip,progress,saved,routeIndex,!!adjustment))
    return state.tour
  }catch(e){uni.removeStorageSync(TRIP_KEY);return null}
}

// 后端可用时用真实数据覆盖本地演示数据；失败只记录错误，页面继续用本地兜底。
export async function syncServer({force=false}={}){
  if(!USE_SERVER)return false
  if(!force&&Date.now()-lastSync<2000)return !!state.server.online
  if(syncing)return syncing
  syncing=(async()=>{
    state.server.loading=true
    try{
      const plan=state.plan
      // 档案可能还没建：404 不等于后端不可用，单独标记，交给页面引导建档。
      let profile=null,profileMissing=false
      try{profile=await api.getProfile()}catch(e){if(e&&e.status===404)profileMissing=true;else throw e}
      const [spots,facilities]=await Promise.all([
        api.listSpots(),
        api.searchFacilities({limit:50})
      ])
      // 没建档的账号按档案推荐会 404，这里不能让整次同步失败。
      let routeResult=null
      try{routeResult=await api.listRoutes({walkDurationMin:plan&&plan.duration,avoidSteps:plan&&plan.energy==='有点累'?true:undefined})}catch(e){routeResult=null}
      spotsById={};(spots||[]).forEach(s=>{spotsById[s.id]=s})
      if(routeResult&&Array.isArray(routeResult.routes))setServerRoutes(adaptRoutes(routeResult,spotsById,facilities||[]))
      setServerFacilities(adaptFacilityGroup(facilities))
      const p=adaptProfile(profile)
      if(p){state.profile=p;state.preferences=adaptPreferences(p);uni.setStorageSync('elder-profile',clone(p));uni.setStorageSync('elder-preferences',clone(state.preferences))}
      // 这个账号还没建档：不要把上一个身份的档案继续显示出来。
      else if(profileMissing){state.profile={nickname:'新朋友',age:0,city:'',language:'',emergencyContact:{name:'',phone:'',relation:''},contacts:[],interests:[],walkSpeed:'MEDIUM',walkDurationMin:40,avoidSteps:true,version:null};state.preferences=null}
      state.server.needsProfile=!!(profileMissing&&actorKey().indexOf('elder')===0)
      await syncActiveTrip()
      await loadRecords()
      state.server.online=true;state.server.error='';state.server.syncedAt=Date.now();lastSync=Date.now()
      return true
    }catch(e){
      // 4xx 说明后端在线，只是当前身份没有档案/权限；不能据此显示“未连接”。
      const status=(e&&e.status)||0
      const reachable=status>=400&&status<500
      state.server.online=reachable
      state.server.error=reachable?'':((e&&e.message)||String(e))
      lastSync=Date.now()
      return reachable
    }finally{state.server.loading=false;syncing=null}
  })()
  return syncing
}

export function serverSpots(){return spotsById}

export async function loadRecords(){
  if(!USE_SERVER)return []
  try{
    const page=await api.listRecords({limit:20})
    const items=((page&&page.items)||[]).map(s=>{
      const route=routes.find(r=>r.routeId===s.routeId)
      const plannedMin=route?route.minutes:0
      return {
        id:s.id,routeId:s.routeId,routeName:s.routeName,dateLabel:new Date(s.startedAt||Date.now()).toLocaleDateString('zh-CN'),
        start:s.startedAt?new Date(s.startedAt).toTimeString().slice(0,5):'',end:s.finishedAt?new Date(s.finishedAt).toTimeString().slice(0,5):'',
        minutes:Math.max(1,Math.round((s.durationSeconds||0)/60)),km:(plannedMin*0.05).toFixed(1),
        feedbackSubmitted:!!s.feedbackSubmitted,backend:true}
    })
    state.records=items
    return items
  }catch(e){return state.records||[]}
}

// 开始游览：POST /api/v3/trips。已有 ACTIVE 时后端 409，尽量续上本地记录。
export async function serverBeginTour(routeIndex,plan){
  const route=routes[routeIndex]||routes[0]
  if(!USE_SERVER||!route||!route.routeId)return beginTour(routeIndex,plan)
  try{
    const trip=await api.createTrip(route.routeId)
    const saved={tripId:trip.id,startedAt:trip.startedAt?new Date(trip.startedAt).getTime():Date.now(),routeId:trip.routeId,tripVersion:trip.tripVersion||0}
    uni.setStorageSync(TRIP_KEY,saved)
    const history=uni.getStorageSync(TRIP_HISTORY_KEY)||[]
    uni.setStorageSync(TRIP_HISTORY_KEY,[saved,...history.filter(h=>h&&h.tripId!==trip.id)].slice(0,10))
    if(plan)writeState('plan',{...plan,createdAt:plan.createdAt||Date.now()})
    await syncActiveTrip()
    return true
  }catch(e){
    if(e&&e.status===409){
      // 后端 v3 没有“查询进行中游览”的接口，只能按本机保存过的 tripId 逐个确认是否还能续上。
      const saved=savedTrip()
      if(saved){const t=await syncActiveTrip();if(t)return true}
      const history=uni.getStorageSync(TRIP_HISTORY_KEY)||[]
      for(const item of history){
        if(!item||!item.tripId)continue
        try{
          const trip=await api.getTrip(item.tripId)
          if(trip&&trip.status==='ACTIVE'){uni.setStorageSync(TRIP_KEY,item);await syncActiveTrip();return true}
        }catch(err){/* 已结束或不属于本账号 */}
      }
      uni.showModal({title:'已有进行中的游览',content:'这个账号还有一次未结束的游览，但本机没有它的记录（可能是在别的浏览器里开始的）。请先结束那次游览，再来开始新的。',showCancel:false})
      return false
    }
    uni.showModal({title:'开始游览未成功',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return false
  }
}

// 按时间推算当前应到的站点并上报进度（现场定位未接入，坐标取当前景点坐标）。
export async function serverProgressTick({force=false}={}){
  const t=state.tour
  if(!USE_SERVER||!t||!t.backend||t.ended)return null
  const route=routes[Number(t.route)]||routes[0]
  const stations=route.stations||[]
  if(!stations.length)return null
  const elapsed=(Date.now()-t.startedAt)/60000
  let target=0
  stations.forEach((s,i)=>{if(s.at<=elapsed)target=i})
  if(!force&&target<=(t.current||0))return null
  const station=stations[target]
  const spot=spotsById[station&&station.spotId]
  if(!spot||!spot.location)return null
  const visitedSpotIds=stations.slice(0,target+1).map(s=>s.spotId).filter(Boolean)
  try{
    const progress=await api.reportProgress(t.tripId,{progressSeq:(t.progressSeq||0)+1,lat:spot.location.lat,lng:spot.location.lng,currentSpotId:station.spotId,visitedSpotIds,nextSpotId:stations[target+1]&&stations[target+1].spotId})
    writeState('tour',{...state.tour,current:target,visited:stations.slice(0,target+1).map((s,i)=>i),visitedSpotIds,progressSeq:progress.progressSeq,nextSpotId:progress.nextSpotId})
    return progress
  }catch(e){
    if(e.status===409){
      await syncActiveTrip()
      uni.showModal({title:'游览状态已更新',content:'请刷新后重试',showCancel:false})
    }
    return null
  }
}

export async function serverFinishTour(){
  const t=state.tour
  // 本地演示分支也要返回 true，否则调用方会认为没结束、不跳转（学长演示踩到的 bug）。
  if(!USE_SERVER||!t||!t.backend){finishTour();return true}
  try{
    await api.finishTrip(t.tripId)
    uni.removeStorageSync(TRIP_KEY)
    writeState('tour',{...state.tour,ended:true,endedAt:Date.now(),remainingMin:0})
    await loadRecord(t.tripId)
    return true
  }catch(e){
    uni.showModal({title:'结束游览未成功',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return false
  }
}

// 记录 ID 即 Trip UUID。
export async function loadRecord(recordId){
  if(!USE_SERVER||!recordId)return null
  try{
    const detail=await api.getRecord(recordId)
    const routeIndex=routes.findIndex(r=>r.routeId===detail.routeId)
    const rec=adaptRecordDetail(detail,spotsById,routeIndex)
    writeState('trip-record',rec)
    return rec
  }catch(e){return null}
}

// 我累了改线：POST /api/v3/trips/{id}/adjustments，目标路线取最短的其它路线。
export async function serverAdjust(action){
  const t=state.tour
  if(!USE_SERVER||!t||!t.backend)return adjustTour(action)
  try{
    await serverProgressTick({force:true})
    const cur=state.tour
    const current=routes[Number(cur.route)]||routes[0]
    const candidates=routes.filter(r=>r.routeId&&r.routeId!==current.routeId).sort((a,b)=>a.minutes-b.minutes)
    const target=candidates[0]||current
    if(!cur.progressSeq)await serverProgressTick({force:true})
    const res=await api.adjustTrip(cur.tripId,{routeId:target.routeId,reason:'走累了，想缩短剩余路线',expectedProgressSeq:(state.tour&&state.tour.progressSeq)||1})
    const routeIndex=routes.findIndex(r=>r.routeId===res.routeId)
    const next={...state.tour,route:routeIndex>=0?routeIndex:cur.route,adjusted:true,remainingMin:target.minutes}
    writeState('tour',next)
    return next
  }catch(e){
    if(e.status===409){
      await syncActiveTrip()
      uni.showModal({title:'游览状态已更新',content:'请刷新后重试',showCancel:false})
      return null
    }
    uni.showModal({title:'调整路线未成功',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return null
  }
}

// 游后反馈：effort 取 EASY / COMFORTABLE / TIRED。
// 反馈不会自动改档案；后端可能生成一条“偏好更新待确认”，由页面让老人自己决定。
export async function serverSaveFeedback({effort,comfortableWalkMin,note}){
  const record=state['trip-record']
  if(!USE_SERVER||!record||!record.tripId){
    writeState('trip-record',{...record,feedback:{effort,comfortableWalkMin,note}})
    return {saved:true,preferenceUpdateId:null,comfortableWalkMin:null}
  }
  try{
    const view=await api.submitFeedback(record.tripId,{effort,comfortableWalkMin,note})
    writeState('trip-record',{...record,feedback:{effort:view.effort,comfortableWalkMin:view.comfortableWalkMin,note:view.note||'',profileUpdated:view.profileUpdated,preferenceStatus:view.preferenceStatus}})
    return {saved:true,preferenceUpdateId:view.preferenceUpdateId||null,comfortableWalkMin:view.comfortableWalkMin??comfortableWalkMin??null}
  }catch(e){
    uni.showModal({title:'反馈未保存',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return {saved:false,preferenceUpdateId:null}
  }
}

// 老人确认/拒绝把“舒适步行时长”写进档案。decision: APPROVE / REJECT
export async function serverDecidePreference(decision){
  const record=state['trip-record']
  const id=record&&(record.tripId||record.id)
  if(!USE_SERVER||!id)return false
  try{
    await api.decidePreference(id,decision)
    if(record)writeState('trip-record',{...record,preferenceUpdate:{...(record.preferenceUpdate||{}),status:decision==='APPROVE'?'APPROVED':'REJECTED'}})
    await syncServer({force:true})
    return true
  }catch(e){
    uni.showModal({title:'偏好没有更新',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return false
  }
}

export function tripPhotoList(tripId){
  return (state['trip-photos'] || readState('trip-photos'))[tripId] || []
}

// Blob URL 和进行中的请求只留在内存中，刷新后重新带身份头取图。
const photoUrls=reactive({})
const photoRequests={}
export async function ensurePhotoUrl(tripId,media){
  const key=currentUserId()+':'+tripId+':'+media.id
  if(photoUrls[key])return photoUrls[key]
  if(!photoRequests[key]){
    photoRequests[key]=api.fetchTripMediaUrl(tripId,media.id,media.mimeType)
      .then(url=>{photoUrls[key]=url;return url})
      .finally(()=>{delete photoRequests[key]})
  }
  return photoRequests[key]
}

export async function serverUploadVoice(blob,fileName){
  const tripId=state.tour?.tripId || state['trip-record']?.tripId
  if(!USE_SERVER || !state.server.online || !tripId){
    uni.showToast({title:'请连接后端并保存游览后再添加录音',icon:'none'})
    return null
  }
  try{
    const media=await api.uploadTripAudioBlob(tripId,blob,fileName)
    await loadRecord(tripId).catch(()=>null)
    return media
  }catch(e){
    uni.showModal({title:'录音未保存',content:e?.message||'请稍后重试',showCancel:false})
    return null
  }
}

export async function serverUploadPhoto(filePath){
  const tripId=state.tour?.tripId || state['trip-record']?.tripId
  if(!USE_SERVER || !state.server.online || !tripId){
    uni.showToast({title:'请连接后端并保存游览后再添加照片',icon:'none'})
    return null
  }
  try{
    const media=await api.uploadTripAttachment(tripId,filePath)
    const photos=readState('trip-photos')
    writeState('trip-photos',{...photos,[tripId]:[...(photos[tripId]||[]),media]})
    // 记录详情自带 media 列表：上传后立刻刷新，刷新页面也不会丢照片。
    if(state['trip-record']&&state['trip-record'].tripId===tripId)await loadRecord(tripId).catch(()=>null)
    return media
  }catch(e){
    uni.showModal({title:'照片未添加',content:e?.message||'请稍后重试',showCancel:false})
    return null
  }
}

// 生成 7 天有效的分享链接（最多带 3 个附件）。
export function shareForTrip(tripId){
  const share=(readState('trip-shares')||{})[tripId]
  if(!share)return null
  const expiresAt=share.expiresAt?new Date(share.expiresAt).getTime():Number(share.createdAt)+7*24*60*60*1000
  return expiresAt<=Date.now()?null:share
}

export async function serverShareRecord(){
  const record=state['trip-record']
  if(!USE_SERVER||!record||!record.tripId)return null
  try{
    const view = await api.createShare(record.tripId,{mediaIds:tripPhotoList(record.tripId).slice(0,3).map(media=>media.id)})
    if(view){
      const origin = (typeof location !== 'undefined' && location && location.origin) ? location.origin : ''
      view.displayUrl = origin ? origin + '/#/pages/share?shareId=' + encodeURIComponent(view.id) : ''
      const saved={...record,shareId:view.id,shareUrl:view.displayUrl||view.shareUrl||'',shareExpiresAt:view.expiresAt||''}
      writeState('trip-record',saved)
      const map=readState('trip-shares')||{}
      map[record.tripId]={shareId:view.id,shareUrl:view.displayUrl||view.shareUrl||'',expiresAt:view.expiresAt||'',createdAt:Date.now()}
      writeState('trip-shares',map)
    }
    return view
  }catch(e){
    uni.showModal({title:'生成分享链接失败',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return null
  }
}

export async function serverRevokeShare(){
  const record=state['trip-record']
  if(!record?.tripId)return null
  const shareId=record.shareId||shareForTrip(record.tripId)?.shareId
  if(!shareId)return null
  try{
    await api.revokeShare(record.tripId,shareId)
    writeState('trip-record',{...record,shareId:'',shareUrl:'',shareExpiresAt:''})
    const map=readState('trip-shares')||{}
    delete map[record.tripId]
    writeState('trip-shares',map)
    return true
  }catch(e){
    uni.showModal({title:'撤销分享失败',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return false
  }
}

// 首次建档：后端要求一次传全十项，缺失的用默认值补齐。
export async function serverCreateProfile(fields={}){
  if(!USE_SERVER)return false
  const payload={
    nickname:(fields.nickname||'未填写').trim(),
    age:Math.min(150,Math.max(1,Number(fields.age)||70)),
    residence:fields.city||fields.residence||'深圳',
    language:fields.language||'普通话',
    walkSpeed:fields.walkSpeed||'MEDIUM',
    walkDurationMin:Math.min(1440,Math.max(1,Number(fields.walkDurationMin)||40)),
    avoidSteps:fields.avoidSteps!==false,
    interests:Array.isArray(fields.interests)&&fields.interests.length?fields.interests:['公园散步'],
    interactionPreference:fields.interactionPreference||'VOICE',
    emergencyContacts:Array.isArray(fields.emergencyContacts)?fields.emergencyContacts:[]
  }
  try{
    const view=await api.patchProfile(payload,{version:0})
    const p=adaptProfile(view)
    if(p){state.profile=p;state.preferences=adaptPreferences(p);uni.setStorageSync('elder-profile',clone(p));uni.setStorageSync('elder-preferences',clone(state.preferences))}
    state.server.needsProfile=false
    return true
  }catch(e){
    uni.showModal({title:'建档没有成功',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return false
  }
}

export async function serverSaveProfile(patchBody){
  if(!USE_SERVER)return false
  const payload=profilePatch(patchBody)
  if(!Object.keys(payload).length)return true
  try{
    const view=await api.patchProfile(payload,{version:state.profile&&state.profile.version})
    const p=adaptProfile(view)
    state.profile=p
    state.preferences=adaptPreferences(p)
    uni.setStorageSync('elder-profile',clone(p))
    uni.setStorageSync('elder-preferences',clone(state.preferences))
    return true
  }catch(e){
    if(e&&e.status===409){await syncServer({force:true});uni.showModal({title:'档案已更新',content:'已重新读取最新档案，请确认后再保存。',showCancel:false});return false}
    uni.showModal({title:'保存档案失败',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return false
  }
}

export async function serverSwitchActor(key){
  if(!setActor(key))return false
  // 切身份后必须强制重新同步，否则会复用上一个身份还在跑的那次同步。
  lastSync=0
  if(syncing)try{await syncing}catch(e){}
  await syncServer({force:true})
  return true
}

/* ===================== 链路二：求助 / 家属 ===================== */

function spotNameMap(){const map={};Object.keys(spotsById).forEach(id=>{map[id]=spotsById[id].name});return map}
const ELDER_ID='u100' // 家属视图固定看 u100 的档案（本地 mock 只有一个老人）

// 老人发起求助：位置用当前站点，避免依赖真实定位。
export async function serverCreateHelp(){
  const t=tourView()
  if(!USE_SERVER||!t||!t.backend)return createHelp()
  const spotId=t.currentStop&&t.currentStop.spotId
  const payload={userId:currentUserId(),tripId:t.tripId,type:'GENERAL',locationNote:'走累了，需要协助'}
  if(spotId)payload.location={spotId}
  try{
    const view=await chain2.createHelpEvent(payload)
    const mapped=chain2.adaptHelp(view,spotNameMap())
    writeState('help',mapped)
    const events=readState('help-events')||[]
    writeState('help-events',[mapped,...events.filter(e=>e&&e.id!==mapped.id)])
    return mapped
  }catch(e){
    uni.showModal({title:'求助没有发出去',content:(e&&e.message)||'请稍后重试',showCancel:false})
    return null
  }
}

// 读取老人自己的求助（含最近一次已解决）。
export async function serverLoadHelp(){
  if(!USE_SERVER)return state.help
  try{
    const list=await chain2.listHelpEvents(currentUserId())
    // 后端不保证顺序，按创建时间倒序，页面永远先看到最近的一次。
    const mapped=(list||[]).map(v=>chain2.adaptHelp(v,spotNameMap())).sort((a,b)=>new Date(b.createdAt||0)-new Date(a.createdAt||0))
    writeState('help-events',mapped)
    const active=mapped.find(h=>h.status!=='RESOLVED')||mapped[0]||null
    writeState('help',active)
    return active
  }catch(e){return state.help}
}

// 工作人员视角：不带 userId 才能看到全部求助。
export async function serverStaffHelpList(){
  if(!USE_SERVER)return readState('help-events')||[]
  try{
    const list=await chain2.listHelpEvents()
    return (list||[]).map(v=>chain2.adaptHelp(v,spotNameMap())).sort((a,b)=>new Date(b.createdAt||0)-new Date(a.createdAt||0))
  }catch(e){throw e}
}

export async function serverAcknowledgeHelp(id){
  try{
    const view=await chain2.acknowledgeHelpEvent(id)
    return chain2.adaptHelp(view,spotNameMap())
  }catch(e){uni.showModal({title:'受理失败',content:(e&&e.message)||'请稍后重试',showCancel:false});return null}
}

export async function serverResolveHelp(id){
  try{
    const view=await chain2.resolveHelpEvent(id)
    const mapped=chain2.adaptHelp(view,spotNameMap())
    if(state.help&&state.help.id===mapped.id)writeState('help',mapped)
    return mapped
  }catch(e){uni.showModal({title:'标记解决失败',content:(e&&e.message)||'请稍后重试',showCancel:false});return null}
}

/* ---------- 家属关系（老人侧） ---------- */
export async function serverLoadFamilyRelations(){
  if(!USE_SERVER)return state.family&&state.family.relations
  try{
    const list=await chain2.listFamilyRelations(currentUserId())
    const relations=(list||[]).map(chain2.adaptFamilyRelation)
    writeState('family',{relations})
    return relations
  }catch(e){throw e}
}

export async function serverAddFamilyRelation({name,relation,phone}){
  try{
    const view=await chain2.createFamilyRelation(currentUserId(),{name,relation,phone})
    await serverLoadFamilyRelations().catch(()=>null)
    return chain2.adaptFamilyRelation(view)
  }catch(e){uni.showModal({title:'登记家属失败',content:(e&&e.message)||'请稍后重试',showCancel:false});return null}
}

export async function serverApproveFamilyRelation(id){
  try{await chain2.approveFamilyRelation(currentUserId(),id);await serverLoadFamilyRelations().catch(()=>null);return true}
  catch(e){uni.showModal({title:'批准失败',content:(e&&e.message)||'请稍后重试',showCancel:false});return false}
}

export async function serverRevokeFamilyRelation(id){
  try{await chain2.revokeFamilyRelation(currentUserId(),id);await serverLoadFamilyRelations().catch(()=>null);return true}
  catch(e){uni.showModal({title:'撤回失败',content:(e&&e.message)||'请稍后重试',showCancel:false});return false}
}

// key: position/progress/help/planning
export async function serverSetFamilyPermission(id,key,value){
  const field={position:'shareLocation',progress:'shareProgress',help:'shareAlert',planning:'remotePlanning'}[key]
  if(!field)return false
  try{
    await chain2.patchFamilyPermissions(currentUserId(),id,{[field]:!!value})
    await serverLoadFamilyRelations().catch(()=>null)
    return true
  }catch(e){uni.showModal({title:'授权修改失败',content:(e&&e.message)||'请稍后重试',showCancel:false});return false}
}

// 把家属关系绑定到固定 mock 家属身份，家属端页面才能读到数据。
export async function serverBindFamilyAccount(id,familyActorId='family-operator-001'){
  try{
    const link=await chain2.bindFamilyMockAccount(currentUserId(),id,familyActorId)
    uni.showModal({title:'已绑定演示家属账号',content:'家属身份：'+(link&&link.familyActorId)+'。到设置里切换成「家属」就能看到家属视角。',showCancel:false})
    return link
  }catch(e){uni.showModal({title:'绑定失败',content:(e&&e.message)||'请稍后重试',showCancel:false});return null}
}

/* ---------- 家属视图（家属侧） ---------- */
export async function serverFamilyHome(){
  if(!USE_SERVER)return null
  try{
    const [elder,messages,suggestions]=await Promise.all([
      chain2.familyElderView(ELDER_ID),
      chain2.familyMessages(ELDER_ID).catch(()=>[]),
      chain2.listRouteSuggestions(ELDER_ID).catch(()=>[])
    ])
    const view=chain2.adaptElderView(elder)
    state['family-elder']=view
    state['family-messages']=(messages||[]).map(chain2.adaptMessage)
    state['family-suggestions']=(suggestions||[]).map(s=>chain2.adaptSuggestion(s))
    return view
  }catch(e){
    state['family-elder-error']=(e&&e.message)||'家属视图读取失败'
    return null
  }
}

export async function serverSendFamilyMessage(text){
  try{
    await chain2.sendFamilyMessage(ELDER_ID,text)
    await serverFamilyHome()
    return true
  }catch(e){uni.showModal({title:'留言发送失败',content:(e&&e.message)||'请稍后重试',showCancel:false});return false}
}

export async function serverSuggestRoute(routeId,note){
  try{
    await chain2.suggestRoute(ELDER_ID,{routeId,note:note||undefined})
    await serverFamilyHome()
    return true
  }catch(e){uni.showModal({title:'建议没有发出',content:(e&&e.message)||'请稍后重试',showCancel:false});return false}
}

// 老人侧：读取家属发来的路线建议（只看待确认的）
export async function serverLoadFamilySuggestions(){
  if(!USE_SERVER)return []
  try{
    const list=await chain2.listRouteSuggestions(ELDER_ID)
    const mapped=(list||[]).map(s=>chain2.adaptSuggestion(s)).filter(s=>s&&s.status==='PENDING')
    state['family-suggestions-elder']=mapped
    return mapped
  }catch(e){return []}
}
// decision: ACCEPT / REJECT（老人采纳需要 remotePlanning 授权）
export async function serverDecideSuggestion(id,decision){
  try{
    await chain2.decideRouteSuggestion(ELDER_ID,id,{decision})
    await serverFamilyHome()
    return true
  }catch(e){uni.showModal({title:'处理建议失败',content:(e&&e.message)||'请稍后重试',showCancel:false});return false}
}

/* ===================== 本地演示路径（保持原样） ===================== */

export function beginTour(route,plan){if(state.tour&&!state.tour.ended)return false;const now=Date.now();writeState('tour',{id:String(now),route,plan:clone(plan),startedAt:now,startClock:new Date(now).toTimeString().slice(0,5),current:0,visited:[0],skipped:[],adjusted:false,elapsedMin:0,remainingMin:routes[route].minutes,ended:false,endedAt:null,restInserted:0});return true}
export function adjustTour(action,station){const t=tourView();if(!t||t.ended)return null;let remaining=t.remainingMin;let skipped=[...t.skipped],current=t.current,visited=[...t.visited],rest=t.restInserted||0;if(action==='skip'){const id=station??t.nextStop?.id;if(id==null||id<=current||skipped.includes(id))return null;skipped.push(id);remaining=Math.max(0,remaining-(t.routeData.stations[id].at-t.routeData.stations[id-1].at))}if(action==='rest'){remaining+=10;rest+=10}if(action==='return'){skipped=[...new Set([...skipped,...t.routeData.stations.filter(s=>s.id>current&&s.id<3).map(s=>s.id)])];remaining=10}if(action==='arrive'&&t.nextStop){current=t.nextStop.id;visited.push(current);remaining=current===3?0:Math.max(0,remaining-(t.nextStop.at-t.currentStop.at))}return {...state.tour,current,visited,skipped,remainingMin:remaining,elapsedMin:t.elapsedMin,restInserted:rest,adjusted:true}}
export function finishTour(){const t=tourView();if(!t)return;writeState('tour',{...state.tour,ended:true,endedAt:Date.now(),elapsedMin:t.elapsedMin,remainingMin:0})}
export function buildRecord(){const t=tourView();if(!t)return state['trip-record'];if(t.backend&&state['trip-record'])return state['trip-record'];return {id:t.id,route:t.route,plan:t.plan,dateLabel:new Date(t.startedAt).toLocaleDateString('zh-CN'),start:t.startClock,end:new Date(t.endedAt||Date.now()).toTimeString().slice(0,5),minutes:t.elapsedMin,km:Number((t.routeData.km*Math.min(1,(t.visited.length-1)/3)).toFixed(2)),visited:t.visited,skipped:t.skipped,restInserted:t.restInserted,photos:['/static/post-trip/photo-lake.png','/static/post-trip/photo-path.png'],feedback:null,createdAt:Date.now()}}
export function favorite(type,routeId=0){const list=readState('favorites'),name=type==='scenic'?'清风园':routes[routeId].name;const index=list.findIndex(f=>f.type===type&&f.name===name);if(index>=0)list.splice(index,1);else list.push({type,name,sub:type==='route'?routes[routeId].minutes+'分钟 · 演示路线':'演示景区',routeId,addedAt:Date.now()});writeState('favorites',list)}
export function again(record){writeState('route',Number(record.route)||0);writeState('plan',{...record.plan,createdAt:Date.now()});uni.navigateTo({url:'/pages/plan'})}
export function navigate(page){uni.navigateTo({url:'/pages/'+page})}
export function back(){if(getCurrentPages().length>1)uni.navigateBack();else uni.reLaunch({url:'/pages/home'})}
export function note(content,title='演示说明'){uni.showModal({title,content,showCancel:false})}
export function confirm(title,content,action){uni.showModal({title,content,success:r=>{if(r.confirm)action()}})}
migrate()
