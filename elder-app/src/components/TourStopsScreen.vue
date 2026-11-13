<script setup>
import StateHint from './StateHint.vue'
import {syncServer,serverSkipStop,serverStartRest,serverExtendRest,serverFinishRest} from './app-state.js'
import {computed} from 'vue';import FlowShell from './FlowShell.vue';import {state,tourView,adjustTour,serverAdjust,writeState,navigate,confirm,note} from './app-state.js';import {clockAt} from './travel-data.js';const tour=computed(tourView);async function adjust(action,id){const current=tourView();if(current&&current.backend){if(action==='skip')return note('后端只支持整条剩余路线的调整，不能单独跳过某一站。');if(action==='rest')return note('后端暂不支持插入休息时间，先休息一会儿再继续就行。');if(action==='arrive')return note('到站进度按时间自动上报，不需要手动点“我到了”。');confirm('确认调整行程','走累了可以把剩余路线换成更短的一条，已走过的记录会保留。',async()=>{if(await serverAdjust('return'))uni.redirectTo({url:'/pages/tour-ongoing'})});return}
const next=adjustTour(action,id);if(!next)return;const nextStop=tour.value.routeData.stations.find(s=>s.id>next.current&&!next.skipped.includes(s.id));confirm('确认调整行程','原计划剩余 '+tour.value.remainingMin+' 分钟 → 调整后 '+next.remainingMin+' 分钟 / 下一站 '+(nextStop?.name||'行程结束'),()=>{writeState('tour',next);if(!next.remainingMin)note('已到最后一站，请返回游览页确认结束。');uni.redirectTo({url:'/pages/tour-ongoing'})})}
async function skipStation(s){
  if(!tour.value.backend)return adjust('skip',s.id)
  confirm('跳过这一站','跳过「'+(s.name||'这一站')+'」后仍可以继续游览。',async()=>{await serverSkipStop(s.id)})
}
function startRest(){
  if(!tour.value.backend)return adjust('rest')
  uni.showActionSheet({itemList:['休息 5 分钟','休息 10 分钟','休息 20 分钟'],success:async r=>{await serverStartRest([5,10,20][r.tapIndex])},fail:()=>{}})
}
function handlePageAction0(){uni.redirectTo({url:'/pages/tour-ongoing'})}
function retryServer(){syncServer({force:true})}
</script>
<template>
  <FlowShell class="paper-page paper-final paper-social paper-tour-stops" title="行程重排">
    <template v-if="tour&&!tour.ended">
      <view class="paper-card paper-hero paper-stops-hero">
        <text class="paper-title">{{tour.routeData.name}}</text>
        <text class="paper-subtitle">{{tour.remainingMin==null?'暂无法估算':'预计剩余 '+tour.remainingMin+' 分钟'}}</text>
        <view class="paper-stops-progress" aria-hidden="true"><view :style="{width:tour.progress+'%'}"/></view>
        <view v-if="tour.restInserted" class="paper-chips"><text>已插入休息 {{tour.restInserted}} 分钟</text></view>
      </view>
      <view class="paper-card">
        <text class="paper-heading">今天这样走</text>
        <view v-for="s in tour.routeData.stations" :key="s.id" class="paper-field paper-stops-row">
          <text class="paper-help paper-stops-time">{{clockAt(tour.startClock,s.at+(s.id>tour.current?(tour.restInserted||0):0))}}</text>
          <view class="paper-copy"><text class="paper-body">{{s.name}}</text><text class="paper-help">{{s.kind}}</text></view>
          <view class="paper-stops-actions">
          <text class="paper-status" :class="{'is-shared':s.id===tour.current&&!tour.skipped.includes(s.id)}">{{tour.skipped.includes(s.id)?'已跳过':s.id===tour.current?'当前':tour.visited.includes(s.id)?'已到':'未到'}}</text>
          <button v-if="tour.backend?(!tour.visited.includes(s.id)&&!tour.skipped.includes(s.id)):(s.id>tour.current&&!tour.skipped.includes(s.id))" class="paper-stops-skip" @click="skipStation(s)">跳过这一站</button>
          </view>
        </view>
      </view>
      <view class="paper-card">
        <text class="paper-heading">调整行程</text>
        <template v-if="tour.backend&&tour.activeRest">
          <view class="paper-field paper-rest-status"><text class="paper-copy paper-body">休息中 · 计划 {{tour.activeRest.plannedMinutes}} 分钟</text></view>
          <view class="paper-rest-actions"><button class="paper-secondary" @click="serverExtendRest(5)">延长 5 分钟</button><button class="paper-secondary" @click="serverFinishRest()">结束休息</button></view>
        </template>
        <button v-else class="paper-field" @click="startRest"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/resting.svg"/></view><text class="paper-copy paper-body">插入休息</text><image class="paper-chevron" src="/static/outing/icons/back.svg"/></button>
        <button class="paper-field" @click="adjust('return')"><view class="paper-disc"><image src="/static/outing/icons/flag.svg"/></view><text class="paper-copy paper-body">提前返回入口</text><image class="paper-chevron" src="/static/outing/icons/back.svg"/></button>
        <button class="paper-secondary" :disabled="!tour.nextStop" @click="adjust('arrive')">演示：我到了下一站</button>
      </view>
      <view class="paper-actions"><button class="paper-primary" @click="handlePageAction0">返回游览</button></view>
    </template>
<StateHint v-else-if="!tour && state.server.loading" kind="loading" title="正在同步游览…" />
<StateHint v-else-if="!tour && state.server.error" kind="offline" title="游览状态暂时不可用" :text="state.server.error" retry-text="重试" @retry="retryServer" />
    <view v-else class="paper-card paper-empty"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/flag.svg"/></view><text class="paper-heading">暂无进行中的游览</text><button class="paper-primary" @click="navigate('plan')">这次怎么逛</button></view>
  </FlowShell>
</template>
<style src="./paper.css"></style>
<style>
.paper-tour-stops .paper-help{display:block;color:#4e648a;font-size:calc(var(--u)*var(--paper-scale)*29);line-height:1.7}
.paper-tour-stops .paper-stops-hero{padding:calc(var(--u)*22);margin-bottom:calc(var(--u)*16)}
.paper-tour-stops .paper-stops-hero .paper-chips{justify-content:flex-start}
.paper-tour-stops .paper-stops-progress{height:calc(var(--u)*14);margin-top:calc(var(--u)*22);overflow:hidden;border-radius:calc(var(--u)*14);background:#d3e3f5}
.paper-tour-stops .paper-stops-progress>view{height:100%;border-radius:inherit;background:#006aff}
.paper-tour-stops .paper-stops-row{display:grid;grid-template-columns:calc(var(--u)*88) minmax(0,1fr) auto;align-items:start;column-gap:calc(var(--u)*14);row-gap:calc(var(--u)*8)}
.paper-tour-stops .paper-stops-time{font-variant-numeric:tabular-nums;padding-top:calc(var(--u)*4)}
.paper-tour-stops .paper-stops-row .paper-status{margin-top:calc(var(--u)*4);white-space:nowrap}
.paper-tour-stops .paper-stops-row .paper-stops-skip{grid-column:2/-1;justify-self:end;min-height:48px;max-width:100%;padding:calc(var(--u)*8) calc(var(--u)*14);border-radius:calc(var(--u)*28);background:#edf5ff;color:#006aff;font-size:calc(var(--u)*var(--paper-scale)*29)}
</style>
<style>
.paper-tour-stops .paper-stops-actions{display:flex;flex-direction:column;align-items:flex-end;min-width:0;gap:4px}.paper-tour-stops .paper-stops-row .paper-stops-actions .paper-stops-skip{margin:0;min-height:0;padding:4px 6px;font-size:12px;line-height:1.6;white-space:nowrap}.paper-tour-stops .paper-stops-row .paper-copy{min-width:0;overflow-wrap:anywhere}
</style>

<style scoped>
:deep(.state-hint){min-width:0;max-width:100%;box-sizing:border-box;overflow-wrap:anywhere}
:deep(.state-hint .state-title),:deep(.state-hint .state-text){max-width:100%}
</style>
