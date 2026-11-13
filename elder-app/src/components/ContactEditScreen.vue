<script setup>import {ref} from 'vue';import FlowShell from './FlowShell.vue';import {state,writeState,back,note,serverSaveProfile} from './app-state.js';const draft=ref({...state.profile.emergencyContact});async function save(){if(!draft.value.name.trim()||!draft.value.relation||!/^1[3-9]\d{9}$/.test(draft.value.phone))return note('请填写姓名、关系和有效的11位手机号码。');writeState('profile',{...state.profile,emergencyContact:{...draft.value}});await serverSaveProfile({emergencyContacts:[{name:draft.value.name.trim(),phone:draft.value.phone,relation:draft.value.relation}]});back()}
</script>

<template>
  <FlowShell class="paper-page" title="紧急联系人">
    <view class="paper-hero paper-contact-hero">
      <view class="paper-illustration"><image src="/static/refined/family.png" mode="aspectFit"/></view>
      <text class="paper-title">需要时，联系得到</text>
      <text class="paper-subtitle">留下一位亲友的联系方式</text>
    </view>
    <view class="paper-card paper-contact-form">
      <text class="paper-heading">联系人资料</text>
      <label class="paper-contact-field" for="contact-name">
        <view class="paper-form-heading"><view class="paper-disc"><image src="/static/outing/icons/person.svg"/></view><text class="paper-value">姓名</text></view>
        <input id="contact-name" v-model="draft.name" :maxlength="20" placeholder="请输入联系人姓名"/>
      </label>
      <view class="paper-form-heading"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/people.svg"/></view><text class="paper-value">与您的关系</text></view>
      <view class="paper-relation-options" role="group" aria-label="与您的关系">
        <button v-for="relation in ['子女','配偶','其他']" :key="relation" :class="{'paper-selected':draft.relation===relation}" :aria-pressed="draft.relation===relation" @click="draft.relation=relation">{{relation}}</button>
      </view>
      <label class="paper-contact-field" for="contact-phone">
        <view class="paper-form-heading"><view class="paper-disc"><image src="/static/outing/icons/phone.svg"/></view><text class="paper-value">手机号</text></view>
        <input id="contact-phone" v-model="draft.phone" type="tel" :maxlength="11" placeholder="请输入手机号码"/>
      </label>
    </view>
    <view class="paper-note"><image src="/static/outing/icons/info.svg"/><text>添加联系人不会自动共享位置和游览信息。</text></view>
    <view class="paper-actions"><button class="paper-primary" @click="save">保存联系人</button></view>
  </FlowShell>
</template>

<style src="./paper.css"></style>
<style scoped>
.paper-contact-field{display:block;margin-top:24px}
.paper-contact-field .paper-form-heading{margin:0 0 12px}
.paper-contact-form .paper-contact-field input{box-sizing:border-box;height:58px;min-height:58px}
.paper-contact-field :deep(.uni-input-input){height:100%;min-height:0;padding:0;margin:0;border:0;border-radius:0;background:transparent}
.paper-relation-options{display:flex;flex-wrap:wrap;gap:10px}
.paper-contact-form .paper-relation-options button{flex:1 1 25%;min-width:72px;min-height:54px;padding:12px 8px;border:1px solid #ccdef5;border-radius:27px;background:#f2f8ff;color:#071537}
.paper-contact-form .paper-relation-options .paper-selected{border-color:#006aff;background:#e0efff;color:#006aff}
</style>
