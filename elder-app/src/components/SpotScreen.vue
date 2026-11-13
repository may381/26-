<script setup>
import {onShow} from '@dcloudio/uni-app'
import {routes} from './travel-data.js'
import {USE_SERVER} from '../api/config.js'
import {getSpotDetail} from '../api/extras.js'
import {synthesizeSpeech, refreshSynthesis} from '../api/index.js'
import {syncServer} from './app-state.js'

import {computed,ref,watch,onUnmounted} from 'vue';import FlowShell from './FlowShell.vue';import {state,tourView,writeState,adjustTour,navigate,confirm,note} from './app-state.js';const tour=computed(tourView),playing=ref(false),progress=ref(0),rate=ref(state.settings.speechRate);const timer=USE_SERVER?null:setInterval(()=>{if(playing.value){progress.value=Math.min(100,progress.value+1);if(progress.value===100)playing.value=false}},1000);function next(){if(!tour.value?.nextStop)return;if(tour.value.backend){note('到站进度会按时间自动上报，不需要手动推进。');return}confirm('演示到达下一站','仅模拟站点推进，不会调用真实定位。',()=>writeState('tour',adjustTour('arrive')))}
const spot=ref(null),spotId=computed(()=>tour.value&&!tour.value.ended?tour.value.currentStop?.spotId:routes[0]?.stations[0]?.spotId)
let spotRequest=0
async function loadSpot(id=spotId.value){const request=++spotRequest;spot.value=null;if(!USE_SERVER||!id)return;try{const data=await getSpotDetail(id);if(request===spotRequest)spot.value=data}catch{}}
watch(spotId,id=>loadSpot(id),{immediate:true})
onShow(()=>{syncServer();loadSpot()})
const fallbackStop=computed(()=>tour.value?.currentStop||routes[0]?.stations[0])
const introductionText=computed(()=>spot.value?(spot.value.descriptionAvailable!==false&&spot.value.description?.trim()?spot.value.description:'这个景点暂时没有文字介绍，可以在现场看看标识牌，或问问工作人员。'):fallbackStop.value?.text)
const narrationText=computed(()=>[introductionText.value,'放慢脚步，看看沿途景色。您可以按自己的体力停留，不必赶时间。','需要休息时，可以查看附近设施。路线与设施以景区现场标识为准。'].filter(Boolean).join('\n'))
const rateMap={slow:0.8,normal:1.0,fast:1.2}
const ttsLoading=ref(false),audioUrl=ref(''),audioId=ref(null),speechError=ref('')
const playLabel=computed(()=>!USE_SERVER?(playing.value?'暂停演示进度':'开始演示进度'):ttsLoading.value?'正在准备语音…':playing.value?'暂停播放':audioUrl.value?'继续播放':'播放讲解')
let audio=null, speechRequest=0, disposed=false, refreshed=false
function unavailable(){
  playing.value=false
  ttsLoading.value=false
  audioUrl.value=''
  audioId.value=null
  speechError.value='语音暂不可用，先看文字'
  if(audio){try{audio.pause()}catch{}}
}
function resetSpeech(){
  ++speechRequest
  const oldAudio=audio
  audio=null
  if(oldAudio){try{oldAudio.stop()}catch{};try{oldAudio.destroy()}catch{}}
  playing.value=false
  ttsLoading.value=false
  audioUrl.value=''
  audioId.value=null
  speechError.value=''
  progress.value=0
  refreshed=false
}
function getAudio(){
  if(audio)return audio
  const player=uni.createInnerAudioContext()
  audio=player
  player.onTimeUpdate(()=>{
    if(audio!==player||disposed)return
    progress.value=player.duration?Math.max(0,Math.min(100,Math.round(player.currentTime/player.duration*100))):0
  })
  player.onPlay(()=>{if(audio===player&&!disposed){playing.value=true;speechError.value=''}})
  player.onPause(()=>{if(audio===player)playing.value=false})
  player.onEnded(()=>{if(audio===player){playing.value=false;progress.value=100}})
  player.onError(()=>{if(audio===player&&!disposed)recoverSpeech()})
  return player
}
function playAudio(fromStart=false){
  const player=getAudio()
  if(player.src!==audioUrl.value)player.src=audioUrl.value
  if(fromStart||progress.value===100){player.seek(0);progress.value=0}
  speechError.value=''
  player.play()
}
async function prepareSpeech(){
  const request=++speechRequest
  ttsLoading.value=true
  speechError.value=''
  try{
    const data=await synthesizeSpeech(narrationText.value,rateMap[rate.value]||1)
    if(disposed||request!==speechRequest)return
    if(!data?.audioUrl){unavailable();return}
    audioUrl.value=data.audioUrl
    audioId.value=data.id
    progress.value=0
    ttsLoading.value=false
    playAudio(true)
  }catch{if(!disposed&&request===speechRequest)unavailable()}
  finally{if(!disposed&&request===speechRequest)ttsLoading.value=false}
}
async function recoverSpeech(){
  if(ttsLoading.value)return
  playing.value=false
  if(!audioId.value||refreshed){unavailable();return}
  refreshed=true
  const request=++speechRequest
  ttsLoading.value=true
  try{
    let data
    try{data=await refreshSynthesis(audioId.value)}catch(error){
      if(disposed||request!==speechRequest)return
      if(error.status!==404)throw error
      data=await synthesizeSpeech(narrationText.value,rateMap[rate.value]||1)
    }
    if(disposed||request!==speechRequest)return
    if(!data?.audioUrl){unavailable();return}
    audioUrl.value=data.audioUrl
    audioId.value=data.id||audioId.value
    ttsLoading.value=false
    playAudio(true)
  }catch{if(!disposed&&request===speechRequest)unavailable()}
  finally{if(!disposed&&request===speechRequest)ttsLoading.value=false}
}
function togglePlayback(){
  if(!USE_SERVER){playing.value=!playing.value;return}
  if(ttsLoading.value)return
  try{
    if(playing.value){audio?.pause();playing.value=false}
    else if(audioUrl.value)playAudio()
    else{refreshed=false;prepareSpeech()}
  }catch{unavailable()}
}
function replay(){
  if(!USE_SERVER){progress.value=0;playing.value=false;return}
  if(ttsLoading.value)return
  try{if(audioUrl.value)playAudio(true);else{refreshed=false;prepareSpeech()}}catch{unavailable()}
}
watch(rate,()=>{
  if(!USE_SERVER)return
  const resume=playing.value||ttsLoading.value
  resetSpeech()
  if(resume)prepareSpeech()
})
watch([spotId,narrationText],()=>{if(USE_SERVER)resetSpeech()})
onUnmounted(()=>{disposed=true;clearInterval(timer);resetSpeech()})
function handlePageAction0(){uni.redirectTo({url:'/pages/tour-ongoing'})}
</script>
<template><FlowShell class="paper-page paper-final paper-spot" title="景点讲解">
  <view class="paper-hero paper-photo-hero">
    <image class="paper-cover" src="/static/travel/park.jpg" mode="aspectFill"/>
    <view class="paper-hero-caption">
      <text class="paper-title">{{(spot?.name||fallbackStop?.name)?.split(' · ')[0]}}</text>
      <text class="paper-subtitle">{{tour?.routeData.name||routes[0]?.name}}</text>
      <view class="paper-chips"><text>演示讲解</text><text>以现场标识为准</text></view>
    </view>
  </view>
  <view class="paper-card">
    <text class="paper-heading">景点介绍</text>
    <text class="paper-body">{{introductionText}}</text>
    <text class="paper-body paper-paragraph">放慢脚步，看看沿途景色。您可以按自己的体力停留，不必赶时间。</text>
    <text class="paper-body paper-paragraph">需要休息时，可以查看附近设施。路线与设施以景区现场标识为准。</text>
  </view>
  <view class="paper-card">
    <view class="paper-audio-heading"><text class="paper-heading paper-copy">听讲解</text></view>
    <view class="paper-spot-progress">
      <view class="paper-stops-progress" role="progressbar" :aria-label="USE_SERVER?'讲解播放进度':'演示播放进度'" :aria-valuenow="progress" :aria-valuemin="0" :aria-valuemax="100"><view :style="{width:progress+'%'}"/></view>
      <text class="paper-help">{{progress}}%</text>
    </view>
    <button class="paper-primary" :disabled="ttsLoading" @click="togglePlayback">{{playLabel}}</button>
    <text v-if="speechError" class="paper-help paper-paragraph" role="status">{{speechError}}</text>
    <text class="paper-help paper-paragraph">播放速度</text><view class="paper-speed"><button v-for="x in [['slow','慢'],['normal','正常'],['fast','快']]" :key="x[0]" :class="{'paper-speed-selected':rate===x[0]}" :aria-pressed="rate===x[0]" @click="rate=x[0]">{{x[1]}}</button></view>
    <button class="paper-secondary" :disabled="ttsLoading" @click="replay">重听</button>
    
  </view>
  <view v-if="spot?.facilities?.length" class="paper-card"><text class="paper-heading">这里的设施</text><view class="paper-chips"><text v-for="(facility,index) in spot.facilities" :key="facility.id||index">{{typeof facility==='string'?facility:facility.name}}</text></view></view>
  <view class="paper-actions paper-spot-actions"><button class="paper-primary" :disabled="!tour?.nextStop||tour?.ended" @click="next">下一站</button><button class="paper-secondary" @click="navigate('tour-facilities')"><image src="/static/outing/icons/seat.svg"/>设施</button><button class="paper-secondary" @click="handlePageAction0"><image src="/static/outing/icons/back.svg"/>返回</button></view>
  <view v-if="!tour&&!spot" class="paper-card paper-empty paper-no-tour"><view class="paper-disc"><image src="/static/outing/icons/flag.svg"/></view><text>尚未开始游览</text><button class="paper-primary" @click="navigate('plan')">这次怎么逛</button></view>
</FlowShell></template>
<style src="./paper.css"></style>
<style>
.paper-spot .paper-chips{justify-content:flex-start}
.paper-spot .paper-chips>text{max-width:100%;overflow-wrap:anywhere}
.paper-spot .paper-card>.paper-chips{margin-top:0}
.paper-spot .paper-body{line-height:1.6}
.paper-spot .paper-help{display:block;color:#4e648a}
.paper-spot .paper-spot-progress{display:flex;align-items:center;gap:calc(var(--u)*16);margin-bottom:calc(var(--u)*18)}
.paper-spot .paper-spot-progress .paper-stops-progress{flex:1;margin-top:0}
.paper-spot .paper-spot-progress .paper-help{flex-shrink:0;font-variant-numeric:tabular-nums}
.paper-spot .paper-final-pair{margin-top:0}
</style>
