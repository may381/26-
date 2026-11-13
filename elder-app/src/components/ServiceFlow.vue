<script setup>
import {ref,computed} from 'vue'
const title=uni.getStorageSync('elder-service-kind')||'健康管理'
const text=ref(''),error=ref(''),rows=ref(uni.getStorageSync('elder-service-entries')||[])
const mine=computed(()=>rows.value.filter(x=>x.kind===title))
const hints={'健康管理':'记录复诊时间、作息提醒或健康资料','生活照护':'填写陪诊、购物或探视需求及时间','防诈骗':'粘贴可疑信息，不要填写密码或验证码','志愿服务':'填写陪伴、助行或数字教学需求','能力银行':'填写您会的技能、分享意愿与时间','文化传承':'记录想学的技艺、课程或学习心得','社区活动':'填写想参加的活动、时间及备注','旅行计划':'填写想去的地点、日期与步行偏好'}
function persist(){uni.setStorageSync('elder-service-entries',rows.value)}
function save(){if(!text.value.trim()){error.value='请先填写内容';return}rows.value.unshift({id:Date.now(),kind:title,text:text.value.trim(),done:false});persist();text.value='';error.value='已保存到本机'}
function remove(id){uni.showModal({title:'删除记录',content:'确定删除这条记录吗？',success:r=>{if(r.confirm){rows.value=rows.value.filter(x=>x.id!==id);persist()}}})}
function toggle(r){r.done=!r.done;persist()}
function back(){if(getCurrentPages().length>1)uni.navigateBack();else uni.redirectTo({url:'/pages/services'})}
function route(){uni.navigateTo({url:'/pages/route-recommend'})}
</script>
<template>
  <view class="flow paper-page paper-final">
    <button class="paper-back" @click="back"><image src="/static/outing/icons/back.svg"/>返回服务</button>
    <view class="paper-hero"><view class="paper-disc paper-disc-large"><image src="/static/outing/icons/file.svg"/></view><text class="paper-title">{{title}}</text><text class="paper-subtitle">{{hints[title]}}</text></view>
    <view class="paper-note"><image src="/static/outing/icons/info.svg"/><text>本地体验：不会发送报名、预约或家属通知。</text></view>
    <view class="paper-card paper-entry-form">
      <text class="paper-heading">{{title==='旅行计划'?'安排下一次出行':'告诉我们您的安排'}}</text>
      <textarea v-model="text" :placeholder="hints[title]" :aria-label="hints[title]" maxlength="500"/>
      <view v-if="title==='防诈骗'" class="paper-note"><image src="/static/outing/icons/info.svg"/><text>关键词提示：{{/转账|验证码|中奖|刷单|链接|退款/.test(text)?'发现需警惕的内容':'未命中不代表安全'}}。请暂停付款，独立核实身份，再与家人商量。此功能不判断真伪。</text></view>
      <button class="paper-primary" @click="save">确认并保存</button>
      <view v-if="error" class="paper-note paper-feedback" role="status"><image :src="error==='已保存到本机'?'/static/outing/icons/check.svg':'/static/outing/icons/info.svg'"/><text>{{error}}</text></view>
    </view>
    <button v-if="title==='旅行计划'" class="paper-secondary paper-route-entry" @click="route">按体力选择景区路线<image class="paper-chevron" src="/static/outing/icons/back.svg"/></button>
    <view class="paper-card">
      <text class="paper-heading">我提交过的</text>
      <view v-if="!mine.length" class="paper-empty"><view class="paper-disc"><image src="/static/outing/icons/file.svg"/></view><text>还没有安排，填写上面的内容开始吧。</text></view>
      <view v-for="r in mine" :key="r.id" class="paper-submission">
        <view class="paper-submission-head"><view class="paper-disc"><image :src="r.done?'/static/outing/icons/check.svg':'/static/outing/icons/clock.svg'"/></view><view class="paper-copy"><text class="paper-badge">{{r.done?'已完成':'待办'}}</text><text class="paper-subtitle">{{new Date(r.id).toLocaleString()}}</text></view></view>
        <text class="paper-body paper-entry-copy">{{r.text}}</text>
        <view class="paper-final-pair"><button class="paper-secondary" @click="toggle(r)">{{r.done?'恢复待办':'标记完成'}}</button><button class="paper-skip" @click="remove(r.id)">删除</button></view>
      </view>
    </view>
    <view class="paper-note"><image src="/static/outing/icons/info.svg"/><text>当前仅保存本机记录。真实服务匹配、课程报名和机构审核需接入后台。健康资料不用于诊断或用药决策。</text></view>
  </view>
</template>
<style src="./paper.css"></style>
