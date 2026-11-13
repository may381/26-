<script setup>
import StateHint from './StateHint.vue'
import {ref,computed,nextTick,provide,onUnmounted} from 'vue'
import OIcon from './OutingIcon.vue'
import DigitalHumanCard from './DigitalHumanCard.vue'
import {onShow} from '@dcloudio/uni-app'
import {state,readState,writeState,removeState,refreshState,navigate,notify,loadRecord,syncServer} from './app-state.js'
import {routes,recommendation,recommended} from './travel-data.js'
import {submitAgentMessage,getAgentTask} from '../api/agent.js'
import ChatChoiceCard from './ChatChoiceCard.vue'
import {transcribeSpeechBlob} from '../api/index.js'
const props=defineProps({active:String})
onShow(()=>{refreshState();promptProfileIfNeeded()})
// 后端没有这个老人的档案时提示建档，而不是静默退回演示数据。
function promptProfileIfNeeded(){if(props.active!=='home')return;setTimeout(()=>{if(!state.server||!state.server.needsProfile)return;if(uni.getStorageSync('elder-profile-prompted'))return;uni.setStorageSync('elder-profile-prompted',true);uni.showModal({title:'先建一份档案',content:'这个账号在后端还没有档案。建好之后，路线推荐和游览才能按您的体力来。',confirmText:'去建档',cancelText:'先看看',success:r=>{if(r.confirm)uni.navigateTo({url:'/pages/profile-edit'})}})},1500)}
const unread=computed(()=>state.notifications.filter(n=>n.unread).length)
function contactFamily(){uni.showActionSheet({itemList:['给女儿留言（演示）','家人授权'],success:r=>{if(r.tapIndex===1)navigate('family');else uni.showModal({title:'给女儿留言 · 演示',editable:true,placeholderText:'请输入留言',success:x=>{if(x.confirm&&x.content?.trim()){notify('family','给女儿的留言',x.content.trim());uni.showToast({title:'已保存留言（演示）',icon:'none'})}}})}})}
provide('refined',props.active!=='home')
const legacyKey=k=>k.replace('elder-','');const readLegacy=k=>readState(legacyKey(k));const writeLegacy=(k,v)=>writeState(legacyKey(k),v);const removeLegacy=k=>removeState(legacyKey(k))
const nav=[['home','首页','home'],['services','服务','grid'],['chat','对话','chat'],['records','记录','clock'],['profile','我的','user']]
const hico=n=>'/static/home/'+n+(n==='mic'?'.svg':'.png')
const ico=n=>'/static/icons/'+n+'-blue.png'
const tab=ref('本周'),query=ref(''),input=ref(''),dialog=ref(''),large=computed(()=>state.settings.fontSize!=='standard'),slow=ref(readLegacy('elder-slow')||false),busy=ref(false),anchor=ref('')
const conversationId=ref(''),pendingAgentInput=ref(null)
function startNewConversation(){if(busy.value)return;conversationId.value='';pendingAgentInput.value=null;messages.value=[{role:'assistant',text:'已开始新对话，请告诉我您的需求。',time:time()}];writeLegacy('elder-chat',messages.value)}
const reminders=ref(readLegacy('elder-reminders')||[false,false,false])
const savedChat=null
// 只替换尚未产生用户追加消息的旧版三条演示，保留已有真实会话内容。
const oldDemo=Array.isArray(savedChat)&&savedChat.length===3&&savedChat[0]?.text==='王阿姨，您想了解什么？'&&savedChat[1]?.text==='附近有适合散步的地方吗？'
const messages=ref([{role:'assistant',text:'您好，请告诉我您的出行需求，或粘贴需要核对的可疑信息。',time:time()}])
const lastReply=computed(()=>[...messages.value].reverse().find(m=>m.role==='assistant'))
const followups=computed(()=>busy.value||pendingAgentInput.value||messages.value.some(m=>m.plan&&!m.plan.done)?[]:lastReply.value?.followups||(lastReply.value?.card?['想再走近一点','看看休息点']:['帮我规划出行','帮我设置提醒','帮我看看可疑短信']))
let replyTimer
onUnmounted(()=>clearTimeout(replyTimer))
function openPlan(){navigate('plan')}
function openRoute(){navigate(state.plan?'route-recommend':'plan')}
function openAction(action){if(action.category)writeLegacy('elder-facility-category',action.category);if(action.page)uni.navigateTo({url:'/pages/'+action.page});else if(action.dialog)show(action.dialog)}
function follow(text){if(text==='查看已有提醒'){show('今日提醒');return}send(text)}

// 对话式规划问卷：三个问题与 PlanScreen 的 duration/energy/companions 完全对齐。
function dateParts(offset) {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  const iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
  return { value: iso, label: (d.getMonth() + 1) + '月' + d.getDate() + '日' }
}
function weekendParts() {
  const d = new Date()
  const add = d.getDay() === 6 ? 0 : 6 - d.getDay()
  d.setDate(d.getDate() + add)
  const iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
  return { value: iso, label: (d.getMonth() + 1) + '月' + d.getDate() + '日' }
}
const DATE_STEP_OPTIONS = (() => {
  const today = dateParts(0)
  const tomorrow = dateParts(1)
  const weekend = weekendParts()
  return [
    { value: today.value, label: '今天 · ' + today.label, desc: '今天出发' },
    { value: tomorrow.value, label: '明天 · ' + tomorrow.label, desc: '明天出发' },
    { value: weekend.value, label: '周末 · ' + weekend.label, desc: '周末出发' },
    { value: 'skip', label: '暂不设置', desc: '先看路线，之后再定' }
  ]
})()
const PLAN_STEPS=[
  {key:'date',title:'哪天去？',hint:'选个大概日子，之后还能改。',options:DATE_STEP_OPTIONS},
  {key:'duration',title:'想逛多久？',hint:'选一个大概时长，之后还可以调整。',options:[
    {value:20,label:'20 分钟',desc:'附近走一走'},
    {value:40,label:'40 分钟',desc:'轻松逛一圈'},
    {value:60,label:'1 小时',desc:'多逛几个地方'}
  ]},
  {key:'energy',title:'今天体力怎么样？',hint:'我会按您的状态推荐路线。',options:[
    {value:'还不错',label:'还不错',desc:'可以多走一点'},
    {value:'有点累',label:'有点累',desc:'优先平缓、少台阶'}
  ]},
  {key:'companions',title:'和谁一起？',hint:'',options:[
    {value:'自己去',label:'自己去'},
    {value:'和家人',label:'和家人'},
    {value:'和朋友',label:'和朋友'}
  ]}
]
const planAnswers=ref({})
function planIntent(text){return /规划|安排|出行计划|出门走走|怎么逛/.test(text)&&!/路线|附近/.test(text)}
function startPlan(){
  planAnswers.value={}
  messages.value.push({role:'assistant',text:'好的，先问您几个小问题，方便按您的节奏推荐路线。',time:time()})
  pushPlanStep(0)
  writeLegacy('elder-chat',messages.value);scroll()
}
function pushPlanStep(stepIndex){
  const q=PLAN_STEPS[stepIndex]
  if(!q)return
  messages.value.push({role:'assistant',plan:{stepIndex,total:PLAN_STEPS.length,type:q.type||'choice',title:q.title,hint:q.hint,options:q.options,selected:null,done:false},time:time()})
  writeLegacy('elder-chat',messages.value)
}
function choosePlan(m,value){if(!m.plan)return;m.plan.selected=value;writeLegacy('elder-chat',messages.value)}
function nextPlan(m){
  const p=m.plan
  if(!p||p.done||p.selected===null||p.selected===undefined)return
  const q=PLAN_STEPS[p.stepIndex]
  const option=(q.options||[]).find(o=>o.value===p.selected)
  const label=(option&&option.label)||String(p.selected)
  if(q.key==='date'){
    planAnswers.value.date=(p.selected==='skip'||p.selected==null)?null:p.selected
    planAnswers.value.dateLabel=(p.selected==='skip'||p.selected==null)?'暂不设置':label
  }else{
    planAnswers.value[q.key]=p.selected
  }
  messages.value.push({role:'user',text:label,time:time()})
  p.done=true
  if(p.stepIndex<PLAN_STEPS.length-1){
    pushPlanStep(p.stepIndex+1)
  }else{
    writeState('plan',{...planAnswers.value,createdAt:Date.now()})
    const dateText=planAnswers.value.date?planAnswers.value.dateLabel:''
    const summary=[dateText,planAnswers.value.duration+' 分钟',planAnswers.value.energy,planAnswers.value.companions].filter(Boolean).join(' · ')
    send('请帮我规划适老出行。已选择条件：'+summary+'。请先确认目的地，不要默认使用演示景区。',true)
  }
  writeLegacy('elder-chat',messages.value);scroll()
}

const services=[{name:'智能出行',sub:'旅游 · 路线规划',icon:'route'}]
const visibleServices=computed(()=>services.filter(s=>(s.name+s.sub).includes(query.value.trim())))
const demoRecords=[{name:'清风园',sub:'历史演示 · 2小时30分钟',type:'游览',image:'park'},{name:'血压记录',sub:'历史演示 · 120/75 mmHg',type:'健康',image:'health'},{name:'深圳非遗展览',sub:'历史演示 · 已完成打卡',type:'学习',image:'culture'},{name:'社区太极活动',sub:'历史演示 · 参与活动',type:'服务',image:'community'}]
const records=computed(()=>{const server=(state.records||[]).map(r=>({name:r.routeName||'游览记录',sub:r.dateLabel+' · '+r.minutes+'分钟 · 约'+r.km+'公里',type:'游览',image:'park',id:r.id,server:true}));if(server.length)return server;return state['trip-record']?[{name:'本次游览记录',sub:state['trip-record'].dateLabel+' · '+state['trip-record'].minutes+'分钟 · 约'+state['trip-record'].km+'公里',type:'游览',image:'park'},...demoRecords]:demoRecords})
const filteredRecords=computed(()=>records.value.filter(r=>tab.value==='本周'||r.type===tab.value))
function go(n){if(n!==props.active)uni.redirectTo({url:'/pages/'+n})}
function show(name){const page={'家属管理':'family','家属授权':'family','我的档案':'profile-detail','消息通知':'notifications','我的收藏':'favorites','使用设置':'settings'}[name];if(page){navigate(page);return}if(name==='深圳非遗展览'){uni.showModal({title:'演示说明',content:'文化内容后续接入。',showCancel:false});return}if(name==='本次游览记录'){uni.navigateTo({url:'/pages/trip-record'});return}if(name==='清风园'){uni.navigateTo({url:'/pages/scenic-detail'});return}dialog.value=name}
async function openRecord(r){if(r&&r.id){const rec=await loadRecord(r.id);if(rec){uni.navigateTo({url:'/pages/trip-record'});return}}show(r&&r.name)}
function done(i){if(i===0){reminders.value[0]=!reminders.value[0];writeLegacy('elder-reminders',reminders.value)}else show(i===1?'复诊提醒':'家人留言')}
function saveSettings(){writeLegacy('elder-large',large.value);writeLegacy('elder-slow',slow.value)}
function service(){navigate('service-detail')}
function ask(text){writeLegacy('elder-topic',text);go('chat')}
async function send(text=input.value,direct=false){
 text=String(text).trim();if(!text||busy.value)return
 input.value='';messages.value.push({role:'user',text,time:time()})
 if(!direct&&!pendingAgentInput.value&&planIntent(text)){startPlan();return}
 busy.value=true;scroll()
 try{
  const previous=pendingAgentInput.value
  const accepted=await submitAgentMessage(text,conversationId.value,previous)
  conversationId.value=accepted.conversationId;pendingAgentInput.value=null
  const stop=Date.now()+90000;let task
  while(Date.now()<stop){
   task=await getAgentTask(accepted.taskId)
   if(!['QUEUED','RUNNING','WAITING_DEPENDENCIES'].includes(task.status)&&(!previous||task.version>previous.version&&task.inputRequest?.inputRequestId!==previous.inputRequest?.inputRequestId))break
   task=null;await new Promise(resolve=>setTimeout(resolve,1200))
  }
  if(!task)throw new Error('任务仍在处理，请稍后查看任务 '+accepted.taskId+'，不要重复提交。')
  if(task.status==='WAITING_INPUT')pendingAgentInput.value=task
  messages.value.push({role:'assistant',text:task.reply?.text||task.error?.message||'任务未返回正文',time:time(),status:task.status==='WAITING_INPUT'?'等待您补充信息':task.status==='SUCCEEDED'?'本次处理已返回':'任务尚未完整完成'})
 }catch(error){messages.value.push({role:'assistant',text:error.message||'请求失败，请检查后端状态。',time:time(),status:'请求未完成'})}
 finally{busy.value=false;writeLegacy('elder-chat',messages.value);scroll()}
}
function time(){const d=new Date();return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')}
function scroll(){nextTick(()=>{anchor.value='';nextTick(()=>anchor.value='chat-end')})}
const voiceState=ref('idle'),voiceMsg=ref('')
const voiceLabel=computed(()=>voiceState.value==='recording'?'正在听… 点一下结束':voiceState.value==='transcribing'?'识别中…':'按住说话')
let recorder,voiceStream,voiceStarting=false,voiceDisposed=false
function stopVoiceTracks(){voiceStream?.getTracks().forEach(track=>track.stop());voiceStream=null}
function voiceFailure(message){
  if(voiceDisposed)return
  voiceMsg.value='语音暂不可用，请用文字输入'
  uni.showModal({title:'语音暂不可用',content:(message||'录音未成功')+'。您可以输入文字提问。',showCancel:false})
}
async function voice(){
  if(voiceDisposed||voiceStarting||voiceState.value==='transcribing')return
  if(voiceState.value==='recording'){
    voiceState.value='transcribing';voiceMsg.value='正在识别，请稍候'
    try{recorder.stop()}catch(e){voiceState.value='idle';voiceFailure(e?.message)}finally{stopVoiceTracks()}
    return
  }
  if(typeof navigator==='undefined'||!navigator.mediaDevices?.getUserMedia||typeof window==='undefined'||!window.MediaRecorder){
    voiceMsg.value='当前设备不支持录音，请输入文字';return
  }
  voiceStarting=true;voiceMsg.value='请允许使用麦克风'
  try{
    voiceStream=await navigator.mediaDevices.getUserMedia({audio:true})
    if(voiceDisposed){stopVoiceTracks();return}
    try{recorder=new window.MediaRecorder(voiceStream,{mimeType:'audio/webm;codecs=opus'})}catch(_){recorder=new window.MediaRecorder(voiceStream)}
    const currentRecorder=recorder,chunks=[]
    let failed=false
    currentRecorder.ondataavailable=e=>{if(e.data?.size)chunks.push(e.data)}
    currentRecorder.onerror=e=>{
      failed=true;stopVoiceTracks();voiceState.value='idle'
      voiceFailure(e.error?.message||'录音设备发生错误')
    }
    currentRecorder.onstop=async()=>{
      stopVoiceTracks()
      if(voiceDisposed||failed)return
      voiceState.value='transcribing'
      try{
        const mime=currentRecorder.mimeType||'audio/webm'
        const extension=mime.includes('mp4')?'mp4':mime.includes('ogg')?'ogg':mime.includes('wav')?'wav':mime.includes('mpeg')?'mp3':'webm'
        const data=await transcribeSpeechBlob(new Blob(chunks,{type:mime}),'voice.'+extension)
        if(voiceDisposed)return
        const text=typeof data?.text==='string'?data.text.trim():''
        if(text){voiceMsg.value='';if(props.active==='chat'){input.value=text;send(text)}else ask(text)}
        else voiceMsg.value='没有听清，请再说一次或输入文字'
      }catch(e){voiceFailure(e?.message)}finally{if(!voiceDisposed)voiceState.value='idle'}
    }
    currentRecorder.start();voiceState.value='recording';voiceMsg.value='请说话，说完点一下结束'
  }catch(e){stopVoiceTracks();voiceState.value='idle';voiceFailure(e?.message||'无法使用麦克风，请检查录音权限')}
  finally{voiceStarting=false}
}
onUnmounted(()=>{
  voiceDisposed=true
  try{if(recorder&&recorder.state!=='inactive')recorder.stop()}catch(_){}finally{stopVoiceTracks()}
})
if(props.active==='chat'){const topic=readLegacy('elder-topic');if(topic){removeLegacy('elder-topic');send(topic)}}
function clearMemory(){removeState('preferences');removeLegacy('elder-confirmed-preferences');removeLegacy('elder-travel-preferences');uni.showToast({title:'已删除推荐偏好',icon:'none'});dialog.value=''}
const dialogRows=computed(()=>({'家属管理':['女儿 · 已绑定（演示）','紧急联系人 · 女儿'],'家属授权':['位置共享','游览进度共享','求助通知'],'我的档案':[...(state.profile?['称呼：'+state.profile.nickname,'年龄：'+state.profile.age+'岁','城市：'+state.profile.city]:[]),'步行偏好：'+(state.preferences?state.preferences.pace+'、'+state.preferences.stairs:'尚未设置')],'家人留言':['女儿：今天降温，记得添衣'],'复诊提醒':['10:30 · 深圳市人民医院 · 内科','这是模拟提醒，请以实际预约为准。'],'消息通知':['女儿：今天降温，记得添衣','复诊提醒：10:30'],'我的收藏':['清风园','深圳非遗展览'],'会员中心':['普通会员','当前原型未配置付费功能。'],'隐私与安全':['交互数据保存在本机缓存，业务数据由本地后端演示库保存。','未接入真实登录，使用本地 mock 身份头。'],'关于我们':['银龄智游 · 演示版','老人个人数字分身服务平台'],'帮助与反馈':['点击底部导航切换页面。','在对话页输入问题，体验本地模拟回复。'],'今日提醒':['09:00 · 喝水提醒','10:30 · 复诊提醒','家人留言：今天降温，记得添衣']}[dialog.value]||['此功能为本地演示入口。','此项尚未接入真实服务。']))
const grants=ref(readLegacy('elder-grants')||[false,false,true]);function grant(i,e){grants.value[i]=e.detail.value;writeLegacy('elder-grants',grants.value)}
function retryServer(){syncServer({force:true})}
</script>
<template>
<view class="app" :class="{large,'chat-page':active==='chat','unified-chat':active==='chat','home-page':active==='home','font-huge':state.settings.fontSize==='huge','refined-page':active!=='home',[active+'-refined']:active!=='home'}">
<image v-if="active==='home'" class="home-header-art" src="/static/home/header-art.png" mode="scaleToFill"/><image v-else-if="['chat','services','profile'].includes(active)" class="chat-watermark" src="/static/logo.svg" mode="aspectFit"/><image v-else class="refined-art" :src="'/static/refined/'+active+'-art.png'" mode="scaleToFill"/>
<view class="tab-stage" :key="active">
<template v-if="active==='home'">
<view class="brand"><image class="home-brand-mark" src="/static/home/brand-mark.png" mode="aspectFit"/><text class="home-brand-name">银龄智游</text><button class="icon-button" aria-label="消息通知" @click="show('消息通知')"><image src="/static/icons/bell.svg"/><text v-if="unread" class="unread-count">{{unread}}</text></button></view>
<DigitalHumanCard/>
<view class="askbar"><button class="text-entry" @click="go('chat')"><image class="home-keyboard" :src="hico('keyboard')"/>输入文字提问</button><button class="primary voice" :class="{recording:voiceState==='recording'}" :disabled="voiceState==='transcribing'" @click="voice"><image :src="hico('mic')"/><text>{{voiceLabel}}</text></button></view>
<text v-if="voiceMsg" class="voice-message" role="status" aria-live="polite">{{voiceMsg}}</text>
<view class="quick-asks"><button @click="ask('附近有什么好玩的？')">附近有什么好玩的？<text>›</text></button><button @click="ask('帮我规划出行')">帮我规划出行<text>›</text></button></view>
<view class="panel shortcuts"><button v-for="s in [['walk','出门走走'],['chat','问问我'],['people','找家人'],['clock','我的记录']]" :key="s[1]" @click="s[1]==='我的记录'?go('records'):s[1]==='找家人'?contactFamily():s[1]==='出门走走'?openPlan():go('chat')"><image :src="hico(s[0])"/><text>{{s[1]}}</text></button></view>
<view class="panel"><view class="section-head"><text class="section-title">我的出游习惯</text><button class="link" @click="navigate(state.preferences?'preferences-edit':'preferences')">{{state.preferences?'修改':'去设置'}} ›</button></view><text class="sub">{{state.preferences?[(state.preferences.interests||[]).join('、'),typeof state.preferences.walkDuration==='number'?'约'+state.preferences.walkDuration+'分钟':'时长尚未确定',state.preferences.stairs].filter(Boolean).join(' · '):'还不了解您的出游习惯'}}</text></view><view class="panel accented"><view class="section-head"><text class="section-title">今日推荐 · 演示</text></view><text class="sub">{{recommendation(routes[recommended(state.plan,state.preferences)],state.plan,state.preferences)}}</text><view class="photo-grid"><button v-for="s in [['park','清风园','景区'],['culture','深圳非遗展览','文化']]" :key="s[1]" class="photo-card" @click="show(s[1])"><image :src="'/static/photos/'+s[0]+'.jpg'" mode="aspectFill"/><view class="photo-label">{{s[1]}}<text>›</text></view><text class="sub">{{s[2]}}</text></button></view></view><view class="panel"><view class="section-head"><text class="section-title">今日提醒 · 演示</text><button class="link" @click="show('今日提醒')">全部提醒 ›</button></view><view v-for="(r,i) in [['喝水提醒','','09:00'],['复诊提醒','深圳市人民医院 · 内科','10:30'],['家人留言','女儿：今天降温，记得添衣','']]" :key="r[0]" class="reminder"><view class="icon-disc"><image :src="hico(['water','calendar','message'][i])"/></view><view class="grow"><text class="row-title">{{r[0]}}</text><text v-if="r[1]" class="sub">{{r[1]}}</text></view><text class="time">{{r[2]}}</text><button class="outline small" @click="done(i)">{{i===0?(reminders[0]?'已喝水':'去喝水'):'查看'}}</button></view></view>

</template>
<template v-else-if="active==='services'"><view class="page-title">服务</view><view class="panel accented"><button class="service-row" @click="service"><view class="icon-disc"><Icon name="route"/></view><view class="grow"><text class="row-title">智能出行</text><text class="sub">旅游 · 路线规划 · 演示数据</text></view><text class="chevron">›</text></button></view><text class="sub">更多服务正在接入</text></template>
<template v-else-if="active==='chat'">
<view class="chat-heading"><view class="page-title">对话</view><button @click="startNewConversation">新对话</button><button class="icon-button" aria-label="对话历史" @click="show('对话历史')"><image src="/static/outing/icons/history.svg" mode="aspectFit"/></button></view>
<scroll-view :show-scrollbar="false" class="messages" scroll-y :scroll-into-view="anchor" :scroll-with-animation="true">
  <view v-for="(m,i) in messages" :key="i" v-show="!m.plan||!m.plan.done" class="message-group" :class="{'has-result':m.card||m.action||m.plan}">
   <view class="message" :class="m.role">
    <view v-if="m.role==='assistant'" class="avatar"><image src="/static/outing/icons/assistant.svg" mode="aspectFit"/></view>
    <view class="message-content">
      <view v-if="!m.plan" class="bubble">{{m.text}}</view>
      <text v-if="!m.plan&&!m.status&&!m.card" class="message-time">{{m.time}}</text>
      <view v-if="m.status||m.card" class="reply-status"><OIcon name="check"/><text>{{m.status||'已找到适合慢走的路线'}}</text></view>
    </view>
   </view>
   <view v-if="m.card||m.action" class="result-shelf">
      <view v-if="m.card" class="route-result recommendation-card">
        <image class="result-photo" src="/static/travel/park.jpg" mode="aspectFill"/>
        <view class="result-body">
          <text class="result-title">清风园</text><text class="result-subtitle">{{routes[recommended(state.plan,state.preferences)].name}}</text>
          <view class="result-facts"><view><OIcon name="clock"/><text>约{{routes[recommended(state.plan,state.preferences)].minutes}}分钟</text></view><view><OIcon name="walk"/><text>约{{routes[recommended(state.plan,state.preferences)].km}}公里</text></view><view><OIcon name="stairs"/><text>{{routes[recommended(state.plan,state.preferences)].stairs}}</text></view></view>
          <text class="result-note">{{recommendation(routes[recommended(state.plan,state.preferences)],state.plan,state.preferences)}}</text>
          <view class="result-actions"><button class="detail-action" @click="show('清风园')">景区详情</button><button class="route-action" @click="openRoute">查看路线</button></view>
        </view>
      </view>
      <button v-if="m.action" class="message-action" @click="openAction(m.action)">{{m.action.label}}<text>›</text></button>
   </view>
   <view v-if="m.plan" class="chat-choice-wrap">
     <ChatChoiceCard :step-index="m.plan.stepIndex" :total="m.plan.total" :title="m.plan.title" :hint="m.plan.hint" :options="m.plan.options" :selected="m.plan.selected" @select="choosePlan(m,$event)" @next="nextPlan(m)" />
   </view>
  </view>
  <view v-if="busy" class="typing" role="status"><view class="typing-dots"><text/><text/><text/></view><text>正在整理回复…</text></view>
  <view v-if="followups.length" class="context-suggestions"><button v-for="q in followups" :key="q" @click="follow(q)">{{q}}</button></view>
  <view id="chat-end"/>
</scroll-view>
<text v-if="voiceMsg" class="voice-message" role="status" aria-live="polite">{{voiceMsg}}</text>
<view class="composer"><OIcon class="composer-keyboard" name="keyboard"/><input v-model="input" :placeholder="state.settings.inputMode==='voice'?'可输入文字，或点击语音输入':'输入您想说的话'" placeholder-class="chat-placeholder" confirm-type="send" @confirm="send()" maxlength="300" aria-label="输入您想说的话"/><button v-if="input.trim()&&voiceState==='idle'" class="primary send" :disabled="busy" @click="send()">发送</button><button v-else class="primary mic" :class="{recording:voiceState==='recording','voice-active':voiceState!=='idle'}" :disabled="voiceState==='transcribing'||(busy&&voiceState==='idle')" :aria-label="voiceState==='idle'?'语音输入，点击开始录音':voiceLabel" @click="voice"><image :src="hico('mic')"/><text v-if="voiceState!=='idle'">{{voiceLabel}}</text></button></view>
</template>
<template v-else-if="active==='records'">
<StateHint v-if="!state.records.length && state.server.loading" kind="loading" title="正在读取游览记录…" />
<StateHint v-else-if="!state.records.length && state.server.error" kind="offline" title="记录暂时无法加载" :text="state.server.error" retry-text="重试" @retry="retryServer" />
<view class="page-title">记录</view><view class="record-tabs"><button v-for="t in ['本周','游览','健康','学习','服务']" :key="t" :class="{selected:tab===t}" @click="tab=t">{{t}}</button></view>
<view v-if="tab==='本周'" class="panel accented"><view class="section-head"><text class="section-title">本周概览</text><text class="sub">演示数据</text></view><view class="stats"><view v-for="s in [['walk','2','游览出行'],['heart','5','健康记录'],['book','1','学习打卡'],['group','2','参与活动']]" :key="s[2]"><view class="icon-disc"><Icon :name="s[0]"/></view><view><view class="stat-number">{{s[1]}}<text>次</text></view><text class="sub">{{s[2]}}</text></view></view></view></view>
<view class="panel"><view class="section-head"><text class="section-title">{{tab==='本周'?'最近记录':tab+'记录'}}</text><button class="link" @click="show('全部记录')">查看全部 ›</button></view><button v-for="r in filteredRecords" :key="r.name+(r.id||'')" class="record-row" @click="openRecord(r)"><image :src="r.image==='community'?'/static/refined/record-community.jpg':'/static/photos/'+r.image+'.jpg'" mode="aspectFill"/><view class="grow"><text class="row-title">{{r.name}}</text><text class="sub">{{r.sub}}</text></view><text class="chevron">›</text></button></view>
</template>
<template v-else>
<view class="chat-heading"><view class="page-title">我的</view><button class="icon-button" aria-label="使用设置" @click="show('使用设置')"><Icon name="settings"/></button></view><view class="panel profile"><button class="profile-main" @click="show('我的档案')"><view class="name-avatar">{{state.profile.nickname.slice(0,1).toUpperCase()}}</view><view class="grow"><text class="profile-name">{{state.profile.nickname}}</text><text class="sub">{{state.profile.age}}岁 · {{state.profile.city}} | 演示资料</text></view><text class="chevron">›</text></button><button class="membership" @click="show('会员中心')"><text>普通会员 · 演示</text><text>会员中心 ›</text></button></view>
<view class="panel shortcuts"><button v-for="s in [['family','家属管理'],['archive','我的档案'],['alert','消息通知'],['favorite','我的收藏']]" :key="s[1]" @click="show(s[1])"><Icon :name="s[0]"/><text>{{s[1]}}</text></button></view>
<view class="panel settings"><button v-for="s in [['family','家属授权'],['settings','使用设置'],['help','帮助与反馈'],['privacy','隐私与安全'],['info','关于我们']]" :key="s[1]" @click="show(s[1])"><Icon :name="s[0]"/><view class="grow"><text class="row-title">{{s[1]}}</text><text v-if="s[1]==='使用设置'" class="sub">字号、语速与语言</text></view><text v-if="s[1]==='关于我们'" class="sub">1.0.0</text><text class="chevron">›</text></button></view>
</template>
</view>
<view class="bottom-nav unified-nav"><button v-for="n in nav" :key="n[0]" :class="{current:active===n[0]}" :aria-label="n[1]" @click="go(n[0])"><view v-if="active===n[0]" class="tab-halo" aria-hidden="true"/><view class="nav-icon"><image :src="'/static/tabs/'+n[0]+(active===n[0]?'-active':'-idle')+'.svg'" mode="aspectFit"/></view><text>{{n[1]}}</text></button></view>
<view v-if="dialog" class="modal-mask" @click.self="dialog=''" @touchmove.stop.prevent><view class="modal" role="dialog" :aria-label="dialog"><view class="section-head"><text class="modal-title">{{dialog}}</text><button class="close" aria-label="关闭" @click="dialog=''">×</button></view><scroll-view :show-scrollbar="false" scroll-y class="modal-body"><view v-if="dialog==='我的档案'" class="modal-row"><text>游后推荐偏好由您主动确认，可随时删除。</text><button class="outline small" @click="clearMemory">删除已记住的推荐偏好</button></view><template v-if="dialog==='使用设置'"><view class="switch-row"><text>大字号</text><switch :checked="large" color="#006aff" @change="large=$event.detail.value;saveSettings()"/></view><view class="switch-row"><text>慢语速偏好</text><switch :checked="slow" color="#006aff" @change="slow=$event.detail.value;saveSettings()"/></view><text class="sub">语言：普通话。语速设置已保存在本机，语音服务尚未接入。</text></template><template v-else-if="dialog==='家属授权'"><view v-for="(r,i) in dialogRows" :key="r" class="switch-row"><text>{{r}}</text><switch :checked="grants[i]" color="#006aff" @change="grant(i,$event)"/></view><text class="sub">仅保存本机演示设置，不会实际共享信息。</text></template><template v-else-if="dialog==='全部记录'"><view v-for="r in records" :key="r.name" class="modal-row"><text class="row-title">{{r.name}}</text><text class="sub">{{r.sub}}</text></view></template><template v-else-if="dialog==='对话历史'"><view v-for="(m,i) in messages" :key="i" class="modal-row"><text>{{m.role==='user'?'我':'助手'}}：{{m.text}}</text></view></template><template v-else-if="records.find(r=>r.name===dialog)"><image class="detail-photo" :src="'/static/photos/'+records.find(r=>r.name===dialog).image+'.jpg'" mode="aspectFill"/><text class="modal-row">{{records.find(r=>r.name===dialog).sub}}</text><text class="sub">本地模拟记录，仅用于页面交互演示。</text></template><template v-else><view v-for="r in dialogRows" :key="r" class="modal-row">{{r}}</view></template></scroll-view><button class="primary modal-done" @click="dialog=''">我知道了</button></view></view>
</view>
</template>
<script>
import Icon from './Icon.vue';export default {components:{Icon}}
</script>
<style src="./screen.css"></style>

<style src="./home.css"></style>

<style src="./refined.css"></style>

<style src="./tabs.css"></style>

<style src="./unified-chat.css"></style>

<style scoped>
@keyframes tabIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.tab-stage{animation:tabIn .18s ease-out both;min-width:0}
.chat-page>.tab-stage{display:flex;flex-direction:column;flex:1;min-height:0}
.chat-choice-wrap{width:calc(100% - var(--c)*100);margin:calc(var(--c)*-2) auto calc(var(--c)*26)}
@media (prefers-reduced-motion: reduce){.chat-choice-wrap{animation:none}}

.home-page .askbar .voice{min-width:0;max-width:48%;padding:4px 8px;gap:6px;box-sizing:border-box;white-space:normal;line-height:1.35}
.home-page .askbar .voice image{flex-shrink:0;width:24px;height:28px}
.home-page .askbar .voice text{min-width:0;overflow-wrap:anywhere}
.home-page .askbar .text-entry{min-width:0;flex:1}
.voice-message{display:block;margin:8px 12px;color:#4e648a;font-size:16px;line-height:1.5;overflow-wrap:anywhere}
.primary.recording{outline:2px solid #ffcc00;outline-offset:2px}
.home-page .voice[disabled]{opacity:.65}
.unified-chat .composer .mic.voice-active{width:auto;max-width:48%;height:auto;min-height:44px;min-width:0;border-radius:26px;padding:8px;gap:4px;white-space:normal;line-height:1.35;font-size:16px;box-sizing:border-box}
.unified-chat .composer .mic.voice-active image{width:20px;height:24px;flex-shrink:0}
.unified-chat .composer .mic.voice-active text{min-width:0;overflow-wrap:anywhere}
</style>

<style scoped>
:deep(.state-hint){min-width:0;max-width:100%;box-sizing:border-box;overflow-wrap:anywhere}
:deep(.state-hint .state-title),:deep(.state-hint .state-text){max-width:100%}
</style>
