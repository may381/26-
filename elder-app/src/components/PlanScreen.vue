<script setup>
import {ref,computed} from 'vue'
import FlowShell from './FlowShell.vue'
import {state,writeState,navigate,note,syncServer} from './app-state.js'
import {recommended} from './travel-data.js'
const draft=ref(JSON.parse(JSON.stringify(state.plan||{park:'清风园',duration:typeof state.preferences?.walkDuration==='number'?Math.min(60,state.preferences.walkDuration):null,energy:'',companions:'',checklist:{shoes:false,water:false,phone:false}})))
const touring=computed(()=>state.tour&&!state.tour.ended)
async function next(){if(touring.value)return navigate('tour-ongoing');writeState('plan',{...draft.value,createdAt:Date.now()});await syncServer({force:true});writeState('route',recommended(draft.value,state.preferences));navigate('route-recommend')}
</script>
<template>
  <FlowShell class="paper-page paper-final paper-plan" title="这次怎么逛">
    <view class="paper-hero paper-photo-hero">
      <image class="paper-cover" src="/static/travel/park.jpg" mode="aspectFill"/>
      <view class="paper-hero-caption">
        <text class="paper-title">按今天的状态来</text>
        <text class="paper-subtitle">选好后，我会按您的时间和体力推荐路线</text>
        <button class="paper-plan-park" @click="note('本轮仅开放清风园，其他景区后续接入。')">清风园 · 深圳</button>
      </view>
    </view>
    <view class="paper-card">
      <text class="paper-heading">今天想逛多久</text>
      <view class="paper-options">
        <button v-for="x in [20,40,60]" :key="x" class="paper-option" :class="{'paper-selected':draft.duration===x}" :aria-pressed="draft.duration===x" @click="draft.duration=x">
          <view class="paper-disc"><image src="/static/outing/icons/clock.svg"/></view>
          <view class="paper-copy"><text class="paper-body">{{x}} 分钟</text><text class="paper-help">{{x===20?'短途慢走':x===40?'慢慢欣赏':'多走一会儿'}}</text></view>
          <view class="paper-check"><image v-if="draft.duration===x" src="/static/outing/icons/check.svg"/></view>
        </button>
      </view>
    </view>
    <view class="paper-card">
      <text class="paper-heading">今天体力怎么样</text>
      <view class="paper-options">
        <button v-for="x in ['还不错','有点累']" :key="x" class="paper-option" :class="{'paper-selected':draft.energy===x}" :aria-pressed="draft.energy===x" @click="draft.energy=x">
          <view class="paper-disc"><image :src="x==='还不错'?'/static/outing/icons/walk.svg':'/static/outing/icons/resting.svg'"/></view>
          <view class="paper-copy"><text class="paper-body">{{x}}</text><text class="paper-help">{{x==='还不错'?'按平时节奏走':'优先推荐省力路线'}}</text></view>
          <view class="paper-check"><image v-if="draft.energy===x" src="/static/outing/icons/check.svg"/></view>
        </button>
      </view>
    </view>
    <view class="paper-card">
      <text class="paper-heading">这次和谁一起</text>
      <view class="paper-chips paper-plan-companions">
        <button v-for="x in ['自己去','和家人','和朋友']" :key="x" class="paper-option" :class="{'paper-selected':draft.companions===x}" :aria-pressed="draft.companions===x" @click="draft.companions=x">{{x}}</button>
      </view>
    </view>
    <view class="paper-card">
      <text class="paper-heading">行前准备</text>
      <view class="paper-field paper-plan-weather">
        <view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/checksun.svg"/></view>
        <view class="paper-copy"><text class="paper-body">24℃ · 多云</text><text class="paper-help">适合散步，记得带水</text></view>
        <text class="paper-badge">演示</text>
      </view>
      <label v-for="x in [['shoes','穿舒适鞋'],['water','带水'],['phone','带手机']]" :key="x[0]" class="paper-field">
        <text class="paper-copy paper-body">{{x[1]}}</text>
        <switch class="paper-toggle" :checked="draft.checklist[x[0]]" @change="draft.checklist[x[0]]=$event.detail.value" color="#006aff"/>
      </label>
    </view>
    <view class="paper-card">
      <text class="paper-heading">平时的习惯</text>
      <text class="paper-body">{{state.preferences?[(state.preferences.interests||[]).join('、'),state.preferences.stairs].filter(Boolean).join(' · ')||'已保存，部分尚未设置':'尚未设置'}}</text>
      <button class="paper-field paper-plan-edit" @click="navigate('preferences-edit')"><text class="paper-copy">修改</text><image class="paper-chevron" src="/static/outing/icons/back.svg"/></button>
      <text class="paper-help">这些选择只用于本次，不会修改长期偏好。</text>
    </view>
    <view class="paper-actions">
      <text class="paper-body" aria-live="polite">本次：{{[draft.duration?draft.duration+' 分钟':'',draft.energy,draft.companions].filter(Boolean).join(' · ')||'尚未选择'}}<text v-if="!draft.duration||!draft.energy||!draft.companions" class="paper-help">还差：{{[!draft.duration?'时长':'',!draft.energy?'体力':'',!draft.companions?'同行':''].filter(Boolean).join(' / ')}}</text></text>
      <button class="paper-primary" :disabled="!touring&&(!draft.duration||!draft.energy||!draft.companions)" @click="next">{{touring?'继续游览':'按这个推荐路线'}}</button>
      <text v-if="touring" class="paper-note">正在游览，不能同时开始另一条路线。</text>
    </view>
  </FlowShell>
</template>
<style src="./paper.css"></style>
<style>
.paper-plan .paper-body,.paper-plan .paper-help{display:block}
.paper-plan .paper-help{color:#4e648a}
.paper-plan .paper-hero-caption .paper-plan-park{display:inline-flex;align-items:center;width:auto;max-width:100%;margin-top:calc(var(--u)*16);padding:calc(var(--u)*6) calc(var(--u)*20);border-radius:calc(var(--u)*48);background:#edf5ff;color:#006aff;font-size:calc(var(--u)*var(--paper-scale)*29)}
.paper-plan .paper-plan-companions{justify-content:flex-start;gap:calc(var(--u)*12);margin-top:0}
.paper-plan .paper-plan-companions .paper-option{flex:1 1 80px;width:auto;justify-content:center;border-radius:calc(var(--u)*60);font-size:calc(var(--u)*var(--paper-scale)*33)}
.paper-plan .paper-plan-weather{flex-wrap:wrap}
.paper-plan .paper-toggle{flex-shrink:0}
.paper-plan .paper-plan-edit{color:#006aff;font-size:calc(var(--u)*var(--paper-scale)*31)}
</style>
