<script setup>import {ref} from 'vue';import FlowShell from './FlowShell.vue';import {state,writeState,back,note,serverSaveProfile,serverCreateProfile} from './app-state.js';const draft=ref({...state.profile});async function save(){if(!draft.value.nickname.trim()||!draft.value.city.trim()||!Number.isInteger(Number(draft.value.age))||Number(draft.value.age)<1||Number(draft.value.age)>120)return note('请填写称呼、城市和有效年龄。');writeState('profile',{...draft.value,nickname:draft.value.nickname.trim(),age:Number(draft.value.age)});const basic={nickname:draft.value.nickname.trim(),age:Number(draft.value.age),city:draft.value.city.trim()};if(state.server&&state.server.needsProfile){// 首次建档：后端要求一次传全十项
if(await serverCreateProfile({...basic,language:draft.value.language||'普通话',walkDurationMin:(state.preferences&&state.preferences.walkDuration)||40,avoidSteps:true,interests:(state.preferences&&state.preferences.interests)||[],emergencyContacts:draft.value.emergencyContact&&draft.value.emergencyContact.phone?[draft.value.emergencyContact]:[]}))uni.showToast({title:'档案已建立',icon:'none'})}else{await serverSaveProfile(basic)}back()}function editField(key,label){uni.showModal({title:'修改'+label,editable:true,placeholderText:String(draft.value[key]),success:r=>{if(r.confirm&&r.content?.trim())draft.value[key]=r.content.trim()}})}</script>

<template>
  <FlowShell class="paper-page" title="修改基本资料">
    <view class="paper-hero paper-profile-hero">
      <image class="paper-hero-art" src="/static/refined/profile-art.png" mode="aspectFit"/>
      <view class="paper-avatar">{{draft.nickname.slice(0,1).toUpperCase()||'您'}}</view>
      <text class="paper-title">{{draft.nickname}}</text>
      <text class="paper-subtitle">{{draft.age}}岁 · {{draft.city}}</text>
      <text class="paper-subtitle">资料越完整，推荐越准</text>
    </view>
    <view class="paper-card">
      <text class="paper-heading">基本资料</text>
      <text class="paper-subtitle">轻点一项，即可修改</text>
      <button v-for="x in [['nickname','称呼','person'],['age','年龄','calendar'],['city','常住城市','pin']]" :key="x[0]" class="paper-field" @click="editField(x[0],x[1])">
        <view class="paper-disc"><image :src="'/static/outing/icons/'+x[2]+'.svg'"/></view>
        <view class="paper-copy"><text class="paper-label">{{x[1]}}</text><text class="paper-value">{{draft[x[0]]}}</text></view>
        <image class="paper-chevron" src="/static/outing/icons/back.svg"/>
      </button>
    </view>
    <view class="paper-actions"><button class="paper-secondary" @click="back">取消</button><button class="paper-primary" @click="save">保存修改</button></view>
  </FlowShell>
</template>

<style src="./paper.css"></style>
