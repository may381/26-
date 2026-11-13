<script setup>
import FlowShell from './FlowShell.vue';import {state,navigate} from './app-state.js'
function handlePageAction0(){uni.reLaunch({url:'/pages/profile'})}
</script>

<template>
  <FlowShell class="paper-page" title="个人档案">
    <view class="paper-hero paper-profile-hero">
      <image class="paper-hero-art" src="/static/refined/profile-art.png" mode="aspectFit" />
      <view class="paper-avatar">{{state.profile.nickname.slice(0,1).toUpperCase()}}</view>
      <text class="paper-title">{{state.profile.nickname}}</text>
      <text class="paper-subtitle">{{state.profile.age}}岁 · {{state.profile.city}} · {{state.profile.language}}</text>
      <view v-if="state.preferences && state.preferences.interests.length" class="paper-chips">
        <text v-for="x in state.preferences.interests" :key="x">{{x}}</text>
      </view>
    </view>
    <view class="paper-card">
      <text class="paper-heading">基本资料</text>
      <view v-for="x in [['nickname','称呼','person'],['age','年龄','calendar'],['city','常住城市','pin'],['language','常用语言','speaker']]" :key="x[0]" class="paper-data-row">
        <view class="paper-disc"><image :src="'/static/outing/icons/'+x[2]+'.svg'" /></view>
        <view class="paper-copy"><text class="paper-label">{{x[1]}}</text><text class="paper-value">{{state.profile[x[0]]}}{{x[0]==='age'?'岁':''}}</text></view>
      </view>
      <button class="paper-secondary" @click="navigate('profile-edit')">修改基本资料</button>
    </view>
    <view class="paper-card">
      <text class="paper-heading">出游偏好</text>
      <template v-if="state.preferences">
        <view class="paper-metrics">
          <view><image src="/static/outing/icons/clock.svg"/><text class="paper-value">{{typeof state.preferences.walkDuration==='number'?state.preferences.walkDuration+'分钟':'尚未确定'}}</text><text class="paper-label">一次走多久</text></view>
          <view><image src="/static/outing/icons/walk.svg"/><text class="paper-value">{{state.preferences.pace||'尚未设置'}}</text><text class="paper-label">走路节奏</text></view>
          <view><image src="/static/outing/icons/stairs.svg"/><text class="paper-value">{{state.preferences.stairs||'尚未设置'}}</text><text class="paper-label">台阶偏好</text></view>
        </view>
        <text class="paper-subtitle">喜欢：{{state.preferences.interests.join('、')||'尚未设置'}}</text>
        <text class="paper-subtitle">尽量避开：{{state.preferences.avoid.join('、')||'尚未设置'}}</text>
      </template>
      <view v-else class="paper-empty"><view class="paper-disc"><image src="/static/outing/icons/walk.svg"/></view><text>还不了解您的出游习惯</text></view>
      <button class="paper-secondary" @click="navigate('preferences-edit')">{{state.preferences?'修改出游偏好':'去设置出游偏好'}}</button>
    </view>
    <view class="paper-card">
      <text class="paper-heading">紧急联系人</text>
      <view v-if="state.profile.emergencyContact.name" class="paper-contact">
        <view class="paper-avatar paper-avatar-small">{{state.profile.emergencyContact.name.slice(0,1)}}</view>
        <view class="paper-copy"><text class="paper-value">{{state.profile.emergencyContact.name}}</text><text class="paper-subtitle">{{state.profile.emergencyContact.relation}}</text><text class="paper-value paper-phone">{{state.profile.emergencyContact.phone}}</text></view>
      </view>
      <view v-else class="paper-empty"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/people.svg"/></view><text>还未添加紧急联系人</text></view>
      <button class="paper-secondary" @click="navigate('contact-edit')">{{state.profile.emergencyContact.name?'修改联系人':'添加紧急联系人'}}</button>
    </view>
    <view class="paper-actions"><button class="paper-primary" @click="handlePageAction0">返回我的</button></view>
  </FlowShell>
</template>

<style src="./paper.css"></style>
