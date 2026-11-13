<script setup>
import FlowShell from './FlowShell.vue'
import {writeState,navigate,confirm} from './app-state.js'
function skip(){writeState('onboarded',true);uni.reLaunch({url:'/pages/home'})}
function assist(family){confirm(family?'家属帮忙设置 · 演示':'工作人员协助 · 演示',family?'演示邀请码 YL2026。尚未连接家属服务，可以继续自己设置。':'请到景区服务台咨询。当前未实际通知工作人员，可以先自己看看。',()=>family?navigate('preferences'):skip())}
</script>
<template>
  <FlowShell class="paper-page paper-final paper-welcome" title="欢迎来到银龄智游">
    <view class="paper-hero paper-profile-hero">
      <view class="paper-avatar paper-welcome-portrait"><image src="/static/digital-human/placeholder-pet.jpg" mode="aspectFit" alt="小银数字分身" aria-label="小银数字分身"/></view>
      <text class="paper-title">您好，我是小银</text>
      <text class="paper-subtitle">陪您慢慢走，帮您安排行程</text>
      <view class="paper-chips"><text>看路线</text><text>找工作人员</text><text>通知家人</text></view>
    </view>
    <view class="paper-card">
      <view class="paper-actions paper-welcome-actions">
        <button class="paper-primary" @click="navigate('preferences')">我自己用</button>
        <button class="paper-secondary" @click="assist(true)">家属帮我设置</button>
        <button class="paper-secondary" @click="assist(false)">找工作人员帮忙</button>
        <button class="paper-skip" @click="skip">先看看，稍后再设置</button>
      </view>
    </view>
    <text class="paper-help paper-welcome-help">设置随时可以在『我的』里修改</text>
  </FlowShell>
</template>
<style src="./paper.css"></style>
<style>
.paper-welcome .paper-welcome-portrait{width:calc(var(--u)*330);height:calc(var(--u)*330);margin-bottom:calc(var(--u)*22);overflow:hidden}
.paper-welcome .paper-welcome-portrait image{display:block;width:100%;height:100%;border-radius:50%}
.paper-welcome .paper-welcome-actions{margin-top:0;gap:calc(var(--u)*16)}
.paper-welcome .paper-welcome-help{display:block;text-align:center;color:#4e648a;font-size:calc(var(--u)*var(--paper-scale)*29);line-height:1.7}
</style>
