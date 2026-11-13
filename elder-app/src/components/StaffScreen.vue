<script setup>
import StateHint from './StateHint.vue'
import FlowShell from './FlowShell.vue';import {ref,computed} from 'vue';import {onShow} from '@dcloudio/uni-app';import {state,serverStaffHelpList,serverAcknowledgeHelp,serverResolveHelp,actorKey,serverSwitchActor} from './app-state.js'
function handlePageAction0(){uni.reLaunch({url:'/pages/home'})}
const events=ref([]),loading=ref(false),error=ref(''),staff=ref(false)
const online=computed(()=>!!state.server&&!!state.server.online)
function isStaff(){return ['scenic','official','admin'].includes(actorKey())}
async function load(){staff.value=isStaff();if(!staff.value)return;loading.value=true;error.value='';try{events.value=await serverStaffHelpList()}catch(e){error.value=e&&e.message?e.message:'读取失败'}loading.value=false}
onShow(load)
async function ack(h){const m=await serverAcknowledgeHelp(h.id);if(m)await load()}
async function resolve(h){const m=await serverResolveHelp(h.id);if(m)await load()}
function progress(){uni.showModal({title:'后端暂不支持',content:'当前接口只有「接单」和「标记解决」，没有中间进度更新；这一栏先保留。',showCancel:false})}
async function becomeStaff(){if(await serverSwitchActor('scenic'))load()}
function stages(h){const timeline=h.timeline||[];const level=h.status==='RESOLVED'?3:h.status==='ACKNOWLEDGED'?(timeline.some(e=>e.label.includes('处理中'))?2:1):0;return ['已发出','已接单','处理中','已解决'].map((label,i)=>{const entry=timeline.find(e=>e.label.includes(label));return {label,done:i<=level,time:entry?new Date(entry.time).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}):''}})}
</script>
<template>
  <FlowShell class="paper-page paper-social" title="景区接单端">
    <view class="paper-hero paper-contact-hero"><view class="paper-illustration"><image src="/static/outing/staff.png" mode="aspectFit"/></view><text class="paper-title">求助受理</text><text class="paper-subtitle">及时接单，让每一次求助都有人回应</text></view>
    <view v-if="!staff" class="paper-card paper-empty"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/headset.svg"/></view><text class="paper-value">需要景区工作人员身份</text><text>当前身份是「{{({elder:'老人',elder2:'老人',family:'家属'})[actorKey()]||actorKey()}}」，只有景区工作人员身份才能接单。</text><button class="paper-primary" @click="becomeStaff">切换为景区工作人员</button></view>
    <template v-else>
      <StateHint v-if="loading" kind="loading" title="正在读取求助记录…" />
      <StateHint v-else-if="error" kind="error" title="求助记录加载失败" :text="error" retry-text="重试" @retry="load" />
      <view v-if="!loading && !error && !events.length" class="paper-card paper-empty"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/headset.svg"/></view><text class="paper-value">景区暂未收到求助</text><text class="paper-label">老人端发起求助后会出现在这里。</text><button class="paper-secondary" @click="load">刷新列表</button></view>
      <view v-for="h in events" :key="h.id" class="paper-card">
        <text class="paper-status" :class="{'is-shared':h.status==='ACKNOWLEDGED','is-waiting':h.status==='OPEN'}">{{({OPEN:'求助已发出',ACKNOWLEDGED:'已接单',RESOLVED:'已解决'})[h.status]||h.status}}</text>
        <text class="paper-heading paper-help-title">{{h.typeLabel||h.reason}}</text>
        <text v-if="h.typeLabel && h.reason && h.reason!==h.typeLabel" class="paper-subtitle">{{h.reason}}</text>
        <view class="paper-info-line"><image src="/static/outing/icons/pin.svg"/><text>{{(h.location||'').replace(/（演示）|演示位置：/g,'')||'尚未上报位置'}}</text></view>
        <view class="paper-info-line"><image src="/static/outing/icons/clock.svg"/><text>{{h.timeLabel||(h.timeline?.[0]?.time?new Date(h.timeline[0].time).toLocaleString('zh-CN'):'暂无时间信息')}}</text></view>
        <text class="paper-body paper-section-label">处理进度</text>
        <view class="paper-help-steps"><view v-for="(s,i) in stages(h)" :key="s.label" class="paper-help-step" :class="{'is-done':s.done}"><view class="paper-step-node"><image v-if="s.done" src="/static/outing/icons/check.svg"/><text v-else>{{i+1}}</text></view><view class="paper-copy"><text class="paper-body">{{s.label}}</text><text class="paper-label">{{s.time||'待更新'}}</text></view></view></view>
        <button v-if="h.status==='OPEN'" class="paper-primary paper-card-action" @click="ack(h)">接单</button>
        <template v-if="h.status==='ACKNOWLEDGED'"><text class="paper-subtitle">请及时协助处理，处理结束后再点“完成处理”。</text><button class="paper-secondary paper-card-action" @click="progress">更新进度</button><button class="paper-primary paper-card-action" @click="resolve(h)">完成处理</button></template>
      </view>
    </template>
    <view class="paper-actions"><button class="paper-secondary" @click="handlePageAction0">返回老人端</button></view>
  </FlowShell>
</template>
<style src="./paper.css"></style>
