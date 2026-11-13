<script setup>
import {onUnmounted} from 'vue'
import {serverUploadVoice} from './app-state.js'
import {loadRecord,shareForTrip} from './app-state.js'

import {ref,computed,watch} from 'vue';import {onShow} from '@dcloudio/uni-app';import OIcon from './OutingIcon.vue';import {state,readState,writeState,refreshState,buildRecord,notify,again,favorite,serverSaveFeedback,serverDecidePreference,serverShareRecord,serverRevokeShare,confirm,tripPhotoList,serverUploadPhoto,ensurePhotoUrl} from './app-state.js';import {routes,clockAt} from './travel-data.js';const props=defineProps({mode:String});const record=computed(()=>state['trip-record']),fatigue=ref('有点累'),like=ref('喜欢'),comment=ref(''),remember=ref(false),editing=ref(false),shorter=ref(true),flat=ref(true),saving=ref(false),sharing=ref(false);const data=computed(()=>props.mode==='complete'?buildRecord():record.value);const routeData=computed(()=>routes[Number(data.value?.route)]||routes[0]);const route=computed(()=>routeData.value.name);const title=computed(()=>({complete:'游览完成',record:'游览记录',feedback:'游后反馈'}[props.mode]));const summary=computed(()=>data.value?'清风园 · '+route.value+'\n'+data.value.dateLabel+' '+data.value.start+'—'+data.value.end+'\n游览'+data.value.minutes+'分钟，步行约'+data.value.km+'公里（按步行时长估算）':'暂无记录');onShow(()=>{refreshState();const f=record.value?.feedback;if(f){fatigue.value=f.fatigue;like.value=f.like;comment.value=f.comment||''}});function note(content){uni.showModal({title:'演示说明',content,showCancel:false})}function back(){if(getCurrentPages().length>1)uni.navigateBack();else records()}function skip(){uni.redirectTo({url:'/pages/trip-record'})}function records(){uni.reLaunch({url:'/pages/records'})}function goFeedback(){uni.navigateTo({url:'/pages/trip-feedback'})}function save(){const r=buildRecord();if(!r)return note('暂无本次游览，请先完成游览。');if(!state.tour?.ended&&!r.backend)return note('请先确认结束游览。');writeState('trip-record',r);notify('trip','游览记录已保存',route.value,'trip-record');uni.redirectTo({url:'/pages/trip-feedback'})}async function submit(){if(!record.value)return note('请先保存本次游览记录。');const feedback={fatigue:fatigue.value,like:like.value,comment:comment.value.trim(),remember:remember.value};writeState('trip-record',{...record.value,feedback});const effortOf={'轻松':'EASY','有点累':'COMFORTABLE','很累':'TIRED'}[fatigue.value]||'COMFORTABLE';const result=await serverSaveFeedback({effort:effortOf,comfortableWalkMin:remember.value&&shorter.value?20:undefined,note:comment.value.trim()});if(result&&result.preferenceUpdateId){const update=await new Promise(resolve=>{uni.showModal({title:'要不要更新步行偏好？',content:'这次记录显示您舒服的步行时长约'+(result.comfortableWalkMin||20)+'分钟。更新后下次推荐会参考它。',confirmText:'更新',cancelText:'先不改',success:r=>resolve(r.confirm)})});await serverDecidePreference(update?'APPROVE':'REJECT')}else if(remember.value){const old=state.preferences||{walkDuration:null,pace:'',stairs:'',interests:[],avoid:[]};writeState('preferences',{...old,walkDuration:shorter.value?20:old.walkDuration,stairs:flat.value?'少台阶':old.stairs,avoid:[...new Set([...old.avoid,...(shorter.value?['走得太久']:[]),...(flat.value?['台阶多']:[])])],updatedAt:Date.now()})}uni.redirectTo({url:'/pages/trip-record'})}function voice(){note('语音输入尚未接入，请直接输入感受。')}async function share(){if(!record.value)return note('记录尚未保存。');const view=await serverShareRecord();if(view){uni.showModal({title:'已生成 7 天分享链接',content:view.displayUrl||view.shareUrl||view.summaryText||'',confirmText:'复制链接',cancelText:'关闭',success:r=>{if(r.confirm)uni.setClipboardData({data:view.displayUrl||view.shareUrl||view.summaryText||''})}});return}sharing.value=true}function photos(i){const urls=record.value?.backend?uploadedPhotos.value.map(m=>photoViews.value[m.id]?.url).filter(Boolean):demoPhotos;const current=record.value?.backend?photoViews.value[i]?.url:urls[i];if(current)uni.previewImage({current,urls})}

const demoPhotos=['/static/post-trip/photo-lake.png','/static/post-trip/photo-path.png']
async function revokeShare(){
  confirm('撤销分享','撤销后分享链接立刻失效（最长 7 天有效期内），确定撤销？',async()=>{
    const ok=await serverRevokeShare()
    if(ok)uni.showToast({title:'已撤销分享',icon:'success'})
  })
}
const recordRouteFavorited=computed(()=>{const list=Array.isArray(state.favorites)?state.favorites:[];const routeId=Number(record.value?.route)||0;const name=(routes[routeId]&&routes[routeId].name)||record.value?.routeName||'';return list.some(f=>f.type==='route'&&(f.routeId===routeId||f.name===name))})
const uploading=ref(false),photoViews=ref({})
const refreshedPhotoTrips=new Set()
const photoTripId=computed(()=>record.value?.tripId)
const uploadedPhotos=computed(()=>{
  if(!record.value?.backend)return []
  const serverList=Array.isArray(record.value.mediaList)?record.value.mediaList:[]
  const localList=tripPhotoList(photoTripId.value)
  const seen=new Set()
  return [...serverList,...localList].filter(m=>m&&m.id&&!seen.has(m.id)&&seen.add(m.id)&&(!m.mimeType||m.mimeType.startsWith('image/')))
})
async function loadPhoto(media,tripId=photoTripId.value){
  if(media.url){photoViews.value[media.id]={url:media.url};return}
  photoViews.value[media.id]={loading:true}
  try{
    const url=await ensurePhotoUrl(tripId,media)
    if(tripId===photoTripId.value)photoViews.value[media.id]={url}
  }catch(e){if(tripId===photoTripId.value)photoViews.value[media.id]={error:true}}
}
async function photoError(media){
  photoViews.value[media.id]={error:true}
  const tripId=photoTripId.value
  if(!media.url||!tripId||refreshedPhotoTrips.has(tripId))return
  refreshedPhotoTrips.add(tripId)
  uni.showToast({title:'照片链接已失效，正在刷新',icon:'none'})
  await loadRecord(tripId)
}
watch([photoTripId,uploadedPhotos],([tripId,list],[oldTripId]=[])=>{
  if(tripId!==oldTripId)photoViews.value={}
  list.forEach(media=>{if(!photoViews.value[media.id]||(media.url&&media.url!==photoViews.value[media.id].url))loadPhoto(media,tripId)})
},{immediate:true})
async function addPhoto(){
  if(uploading.value)return
  uploading.value=true
  try{
    const choice=await new Promise((resolve,reject)=>uni.chooseImage({count:1,sourceType:['camera','album'],success:resolve,fail:reject}))
    if(choice.tempFiles?.[0]?.size>10*1024*1024){uni.showModal({title:'照片未添加',content:'请选择不超过 10MiB 的 JPG、PNG 或 WebP 照片。',showCancel:false});return}
    const filePath=choice.tempFilePaths?.[0]
    if(filePath && await serverUploadPhoto(filePath))uni.showToast({title:'照片已添加',icon:'success'})
  }catch(e){if(!/cancel/i.test(e?.errMsg||''))uni.showModal({title:'照片未添加',content:e?.message||e?.errMsg||'无法选择照片，请稍后重试',showCancel:false})}
  finally{uploading.value=false}
}


const recording=ref(false),recordingMs=ref(0),savingVoice=ref(false),voiceError=ref('')
const startingVoice=ref(false),playingVoice=ref(null),loadingVoice=ref(null)
const audioItems=computed(()=>(record.value?.mediaList||[]).filter(m=>m?.mimeType?.startsWith('audio/')))
const recordingTime=computed(()=>voiceTime(recordingMs.value))
let recorder=null,micStream=null,voiceTimer=null,audio=null,disposed=false,playRequest=0
let activeVoice=null,retriedVoice=false
function voiceTime(ms){
  const seconds=Math.floor(Math.max(0,Number(ms)||0)/1000)
  return Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')
}
function voiceItemTime(media){
  if(media.durationMs!=null)return voiceTime(media.durationMs)
  if(media.durationSeconds!=null)return voiceTime(media.durationSeconds*1000)
  const date=new Date(media.createdAt||media.uploadedAt||'')
  return Number.isNaN(date.getTime())?'已保存':date.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})
}
function releaseMic(){
  clearInterval(voiceTimer);voiceTimer=null
  micStream?.getTracks().forEach(track=>track.stop());micStream=null
}
async function recordVoice(){
  if(!record.value?.backend)return note('这是设计图中的模拟语音记录，尚无可播放音频。')
  if(savingVoice.value||startingVoice.value)return
  if(recording.value){
    recording.value=false;savingVoice.value=true
    clearInterval(voiceTimer)
    try{recorder.stop()}catch(e){releaseMic();savingVoice.value=false;voiceError.value='录音未保存，请重新录制'}
    return
  }
  voiceError.value=''
  if(!state.server?.online){uni.showToast({title:'后端未连接，请稍后再录音',icon:'none'});return}
  startingVoice.value=true
  try{
    if(typeof navigator==='undefined'||!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined')throw new Error('microphone')
    const stream=await navigator.mediaDevices.getUserMedia({audio:true})
    if(disposed){stream.getTracks().forEach(track=>track.stop());return}
    micStream=stream
    audio?.stop();playingVoice.value=null
    const preferred=['audio/webm','audio/ogg','audio/mp4'].find(type=>MediaRecorder.isTypeSupported?.(type))
    const current=new MediaRecorder(stream,preferred?{mimeType:preferred}:undefined)
    recorder=current
    const chunks=[]
    current.ondataavailable=event=>{if(event.data?.size)chunks.push(event.data)}
    current.onerror=()=>{
      current.onstop=null;recording.value=false;savingVoice.value=false
      releaseMic();voiceError.value='录音中断，请重新录制'
    }
    current.onstop=async()=>{
      releaseMic();recording.value=false
      if(disposed)return
      savingVoice.value=true
      try{
        const type=current.mimeType||chunks[0]?.type||'audio/webm'
        const blob=new Blob(chunks,{type})
        if(!blob.size)throw new Error('没有录到声音，请重新录制')
        if(blob.size>10*1024*1024)throw new Error('录音超过 10MiB，请缩短后重试')
        const extension=type.includes('mp4')?'mp4':type.includes('ogg')?'ogg':'webm'
        const media=await serverUploadVoice(blob,'voice.'+extension)
        if(disposed)return
        if(media)uni.showToast({title:'录音已保存',icon:'success'})
        else voiceError.value='录音未保存，请检查后端连接后重新录制'
      }catch(e){if(!disposed)voiceError.value=e?.message||'录音未保存，请重试'}
      finally{savingVoice.value=false}
    }
    current.start(1000)
    recordingMs.value=0;recording.value=true
    const startedAt=Date.now()
    voiceTimer=setInterval(()=>{recordingMs.value=Date.now()-startedAt},1000)
  }catch(e){
    releaseMic();voiceError.value='浏览器没有麦克风权限，可以先输入文字'
  }finally{startingVoice.value=false}
}
function getVoiceAudio(){
  if(audio)return audio
  audio=uni.createInnerAudioContext()
  audio.onPlay(()=>{playingVoice.value=activeVoice?.id||null;loadingVoice.value=null})
  audio.onPause(()=>{playingVoice.value=null})
  audio.onStop(()=>{playingVoice.value=null})
  audio.onEnded(()=>{playingVoice.value=null;loadingVoice.value=null})
  audio.onError(()=>{handleVoiceError()})
  return audio
}
async function playVoice(media){
  if(recording.value||savingVoice.value||startingVoice.value)return
  voiceError.value=''
  if(activeVoice?.id===media.id&&playingVoice.value===media.id){audio.pause();return}
  const request=++playRequest
  try{
    const player=getVoiceAudio()
    player.stop();playingVoice.value=null;loadingVoice.value=media.id
    activeVoice=media;retriedVoice=false
    const tripId=record.value?.tripId
    const url=media.url||await ensurePhotoUrl(tripId,media)
    if(disposed||request!==playRequest)return
    player.src=url;player.play()
  }catch(e){if(request===playRequest){loadingVoice.value=null;voiceError.value='录音播放失败，请检查连接后重试'}}
}
async function handleVoiceError(){
  const media=activeVoice,request=playRequest,tripId=record.value?.tripId
  playingVoice.value=null
  if(media?.url&&!retriedVoice){
    retriedVoice=true;loadingVoice.value=media.id
    try{
      const refreshed=await loadRecord(tripId)
      if(disposed||request!==playRequest)return
      const fresh=refreshed?.mediaList?.find(item=>item.id===media.id)
      if(!fresh)throw new Error('missing audio')
      const url=fresh.url||await ensurePhotoUrl(tripId,fresh)
      if(disposed||request!==playRequest)return
      activeVoice=fresh;audio.src=url;audio.play();return
    }catch(e){if(disposed||request!==playRequest)return}
  }
  loadingVoice.value=null;voiceError.value='录音播放失败，请检查连接后重试'
}
onUnmounted(()=>{
  disposed=true;playRequest++
  if(recorder){recorder.onstop=null;recorder.onerror=null;if(recorder.state!=='inactive')recorder.stop()}
  releaseMic();audio?.destroy();audio=null
})

function handlePageAction0(){uni.setClipboardData({data:summary.value})}
</script>
<template><view class="post-trip" :class="mode"><image class="post-mark" src="/static/logo.svg" mode="aspectFit"/><view class="post-header"><button aria-label="返回" @click="back"><OIcon name="back"/></button><text>{{title}}</text></view><view class="post-subtitle">清风园 · {{route}} · {{record?.backend?'后端数据':'演示数据'}}</view>
<template v-if="mode==='complete'"><view class="p-panel completed"><OIcon class="completed-icon" name="checksun"/><view><text class="p-bold">本次游览已结束</text><text class="p-sub">您已返回公园入口，可以坐下休息一会儿。</text></view></view><view class="p-panel"><view class="post-metrics"><view><OIcon name="clock"/><view><text class="p-bold">游览时长</text><text class="p-value">{{data?.minutes||0}}分钟</text></view></view><view><OIcon name="mountain"/><view><text class="p-bold">步行</text><text class="p-value">约{{data?.km||0}}公里</text></view></view></view><view class="date-strip"><OIcon name="calendar"/><text>{{data?.dateLabel}} {{data?.start}}—{{data?.end}}</text></view></view><view class="p-panel"><text class="p-heading">本次走过的路线</text><image class="p-map" src="/static/post-trip/completed-map.png" mode="widthFix"/><view class="stop-chips"><template v-for="(x,i) in routeData.stations.filter(s=>(data?.visited||[]).includes(s.id)).map(s=>s.name)" :key="x"><text v-if="i" class="arrow">→</text><text class="chip">{{x}}</text></template></view></view><view class="p-panel"><text class="p-heading">留下这次经历</text><view class="save-list"><view><OIcon name="pin"/><text>游览路线</text><text>›</text></view><view><OIcon name="clock"/><text>景点与时长</text><text>›</text></view></view><view class="p-note"><OIcon name="info"/><text>保存后可在“记录”中查看。</text></view></view><view class="p-panel feeling-prompt"><OIcon name="smile"/><view><text class="p-bold">这次走得累不累？</text><text class="p-sub">说说感受，方便下次安排。</text></view></view><view class="p-footer"><button class="secondary" @click="records">暂不保存</button><button class="primary" :disabled="saving" @click="save">保存并反馈</button></view></template>
<template v-else-if="mode==='record'"><template v-if="record"><view class="p-panel record-overview"><OIcon name="mountain"/><view><text class="p-bold">{{data?.dateLabel}}</text><text>{{data?.start}}—{{data?.end}}</text></view><view class="record-values"><text><OIcon name="clock"/>{{data?.minutes||0}}分钟</text><text><OIcon name="mountain"/>约{{data?.km||0}}公里</text></view><text class="saved-badge">✓ 已保存</text></view><view class="p-panel"><text class="p-heading">游览足迹</text><image class="p-map" src="/static/post-trip/record-map.png" mode="widthFix"/><view class="map-caption"><text/>演示足迹图 · 已走路线（{{data?.minutes||0}}分钟，约{{data?.km||0}}公里）</view></view><view class="p-panel"><text class="p-heading">这次去了哪里</text><view class="visit-timeline"><view v-for="(x,i) in routeData.stations.filter(s=>(data?.visited||[]).includes(s.id)||(data?.skipped||[]).includes(s.id)).map(s=>[clockAt(data.start,s.at),s.name,(data.skipped||[]).includes(s.id)?'已跳过':'已到'])" :key="x[0]"><text class="visit-dot" :class="{end:i===0||i===3}"/><text>{{x[0]}}</text><text>{{x[1]}}</text><text>{{x[2]}}</text></view></view></view><view class="p-panel"><p v-if="data?.restInserted" class="p-sub">插入休息 {{data.restInserted}} 分钟</p><text class="p-heading">我的照片</text><template v-if="record && record.backend"><view v-if="uploadedPhotos.length" class="trip-photo-grid"><view v-for="media in uploadedPhotos" :key="media.id" class="trip-photo-cell"><image v-if="photoViews[media.id]?.url" :src="media.url || photoViews[media.id].url" mode="aspectFill" :aria-label="media.fileName || '游览照片'" @click="photos(media.id)" @error="photoError(media)"/><button v-else-if="photoViews[media.id]?.error" class="trip-photo-placeholder" @click="loadPhoto(media)">加载失败，点击重试</button><view v-else class="trip-photo-placeholder">照片加载中…</view></view></view><view v-else class="trip-photo-empty">还没有照片，添加一张留作纪念吧。</view><text class="p-sub">支持 JPG、PNG、WebP，每张不超过 10MiB</text><view class="record-photo-actions"><button class="secondary trip-photo-add record-photo-add" :disabled="uploading" @click="addPhoto">{{uploading?'正在添加…':'＋ 添加照片'}}</button><text v-if="uploadedPhotos.length" class="record-photo-count">已添加 {{uploadedPhotos.length}} 张</text></view></template><template v-else><text class="p-sub">演示照片</text><view class="trip-photos"><image v-for="(url,i) in demoPhotos" :key="url" :src="url" mode="aspectFill" @click="photos(i)"/></view></template><button class="record-voice-row" :disabled="savingVoice||startingVoice" :class="{'is-recording':recording}" @click="recordVoice"><OIcon name="mic"/><text class="record-voice-label">{{savingVoice?'正在保存录音…':startingVoice?'正在打开麦克风…':recording?'正在录音 · '+recordingTime:'语音记录'}}</text><text class="record-voice-status">{{recording?'轻点结束':savingVoice||startingVoice?'':'轻点录音'}}</text></button><text v-if="voiceError" class="paper-help record-voice-error" role="alert">{{voiceError}}</text><view v-for="(media,i) in audioItems" :key="media.id" class="record-audio-row"><button class="record-audio-play" :disabled="recording||savingVoice||startingVoice||loadingVoice===media.id" :aria-label="(playingVoice===media.id?'暂停':'播放')+'语音记录 '+(i+1)" @click="playVoice(media)">{{loadingVoice===media.id?'加载中':playingVoice===media.id?'暂停':'播放'}}</button><text class="record-audio-label">语音记录 {{i+1}} · {{voiceItemTime(media)}}</text></view></view><view class="p-panel record-feeling"><OIcon name="heart"/><text class="p-bold">游览感受</text><text class="p-sub">{{record.feedback?record.feedback.fatigue:'尚未填写'}}</text><button class="secondary" @click="goFeedback">{{record.feedback?'修改反馈':'去反馈'}}</button></view><view class="record-route-actions"><button class="secondary" @click="again(record)">再走一次</button><button class="secondary" @click="favorite('route',Number(record.route)||0)">{{recordRouteFavorited?'已收藏':'收藏路线'}}</button></view><view v-if="record.backend && (record.shareId || shareForTrip(record.tripId))" class="record-route-actions"><button class="secondary" @click="revokeShare">撤销分享</button></view><view class="p-footer"><button class="secondary" @click="records">返回记录</button><button class="primary" @click="share">分享游览小结</button></view></template><view v-else class="p-panel"><text class="p-bold">暂无已保存的游览记录</text><text class="p-sub">请在游览结束后选择保存。</text><button class="secondary" @click="records">返回记录</button></view></template>
<template v-else><view class="p-panel feedback-summary"><OIcon name="seat"/><text>本次游览：{{data?.minutes||0}}分钟 · 约{{data?.km||0}}公里</text></view><view class="p-panel"><text class="p-heading">这次走得累不累？</text><view class="fatigue-choices"><button v-for="(x,i) in ['轻松','有点累','很累']" :key="x" :class="{chosen:fatigue===x}" @click="fatigue=x"><view class="face" :class="'face-'+i"><text class="eyes">••</text><view class="mouth"/></view><view><text class="radio" :class="{checked:fatigue===x}"/><text>{{x}}</text></view></button></view></view><view class="p-panel"><text class="p-heading">喜欢这条路线吗？</text><view class="like-choices"><button v-for="x in ['喜欢','一般','不太喜欢']" :key="x" :class="{chosen:like===x}" @click="like=x"><text class="radio" :class="{checked:like===x}"/>{{x}}</button></view></view><view class="p-panel"><text class="p-heading">还有什么想告诉我？ <text class="optional">（可选）</text></text><view class="comment-area"><textarea v-model="comment" placeholder="示例：下次想少走一点" maxlength="300" aria-label="游览感受补充"/><button class="primary" @click="voice"><OIcon name="mic"/>说一说</button></view></view><view class="p-panel memory-panel"><view class="memory-heading"><OIcon name="calendar"/><text>下次这样安排，可以吗？</text></view><view class="memory-suggestions"><view v-if="shorter"><OIcon name="clock"/><text>建议缩短步行时间</text></view><view v-if="flat"><OIcon name="pin"/><text>优先安排平缓路线、增加休息点</text></view><text v-if="!shorter&&!flat" class="p-sub">不新增推荐偏好</text></view><view class="suggestion-explain"><text>根据本次反馈提出，您可以修改或不采用。</text><button @click="editing=true">修改建议 ›</button></view><button class="remember-choice" :aria-label="remember?'取消记住偏好':'记住偏好'" @click="remember=!remember"><view class="checkbox" :class="{checked:remember}">{{remember?'✓':''}}</view><text>记住这些偏好，用于下次推荐。</text></button></view><view class="p-note"><OIcon name="info"/><text>您可在“我的档案”中修改或删除。</text></view><view class="p-footer"><button class="secondary" @click="skip">跳过反馈</button><button class="primary" :disabled="saving" @click="submit">提交反馈</button></view></template>
<view v-if="sharing" class="p-mask"><view class="p-dialog"><text class="p-bold">分享游览小结 · 预览</text><image class="p-map" src="/static/post-trip/record-map.png" mode="widthFix"/><text style="white-space:pre-line">{{summary}}</text><button class="primary" @click="handlePageAction0">复制文字</button><button class="secondary" @click="sharing=false">关闭</button></view></view><view v-if="editing" class="p-mask"><view class="p-dialog"><text class="p-bold">修改下次推荐建议</text><view><text>缩短步行时间</text><switch :checked="shorter" @change="shorter=$event.detail.value" color="#006aff"/></view><view><text>平缓路线、增加休息点</text><switch :checked="flat" @change="flat=$event.detail.value" color="#006aff"/></view><button class="primary" @click="editing=false">完成</button></view></view>
</view></template><style src="./post-trip.css"></style>
<style scoped>
.post-trip .record-voice-label,.post-trip .record-audio-label{min-width:0;flex:1;white-space:normal;overflow-wrap:anywhere}
.post-trip .record-voice-status{flex-shrink:0}
.post-trip .record-voice-row.is-recording{color:#006aff;font-variant-numeric:tabular-nums}
.post-trip .record-voice-error{display:block;margin-top:calc(var(--u)*14);color:#9b3434;font-size:calc(var(--u)*28);line-height:1.5;overflow-wrap:anywhere}
.post-trip .record-audio-row{display:flex;align-items:center;gap:calc(var(--u)*16);padding:calc(var(--u)*16) 0;border-top:1px solid #e8eff8;color:#071537;font-size:calc(var(--u)*29)}
.post-trip .record-audio-row .record-audio-play{flex:none;width:auto;min-width:calc(var(--u)*100);min-height:44px;padding:calc(var(--u)*10) calc(var(--u)*16);border-radius:calc(var(--u)*22);background:#eef6ff;color:#006aff;font-size:calc(var(--u)*28)}
</style>
