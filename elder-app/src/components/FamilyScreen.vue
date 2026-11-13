<script setup>
import StateHint from './StateHint.vue'
import {ref} from 'vue'
const loading=ref(false),error=ref('')
async function reload(){loading.value=true;error.value='';try{await serverLoadFamilyRelations()}catch(e){error.value=(e&&e.message)||'读取家属关系失败'}finally{loading.value=false}}
import FlowShell from './FlowShell.vue';import {onShow} from '@dcloudio/uni-app';import {state,writeState,navigate,note,confirm,serverLoadFamilyRelations,serverAddFamilyRelation,serverApproveFamilyRelation,serverRevokeFamilyRelation,serverSetFamilyPermission,serverBindFamilyAccount} from './app-state.js';onShow(()=>reload());function permission(id,key,value){serverSetFamilyPermission(id,key,value)}function revoke(id){confirm('撤回家属授权','撤回后，该家属不能继续查看您的进度、位置和求助信息。',()=>{serverRevokeFamilyRelation(id)})}function approve(id){confirm('批准家属关系','批准后该家属才能按授权查看您的信息。',()=>{serverApproveFamilyRelation(id)})}function bind(id){confirm('绑定演示家属账号','本地演示会把这层关系绑定到固定家属身份 family-operator-001；之后在设置里切换成「家属」就能看到家属视角。',()=>{serverBindFamilyAccount(id,'family-operator-001')})}function addMember(){uni.showModal({title:'添加家属 · 姓名',editable:true,placeholderText:'例如：李女士',success:r=>{if(!r.confirm||!r.content?.trim())return;const name=r.content.trim();uni.showActionSheet({itemList:['子女','配偶','其他'],success:s=>{const relation=['子女','配偶','其他'][s.tapIndex];uni.showModal({title:'添加家属 · 手机号',editable:true,placeholderText:'11 位手机号',success:m=>{const phone=(m.content||'').trim();if(!m.confirm)return;if(!/^1[3-9]\d{9}$/.test(phone))return note('手机号格式不对，请重新添加。');serverAddFamilyRelation({name,relation,phone})}})}})}})}
</script>
<template>
  <FlowShell class="paper-page paper-social" title="家属授权">
    <view class="paper-hero paper-contact-hero">
      <view class="paper-illustration"><image src="/static/refined/family.png" mode="aspectFit"/></view>
      <text class="paper-title">共享哪些信息，由您决定</text>
      <text class="paper-subtitle">逐项选择授权，随时可以撤回</text>
    </view>
    <StateHint v-if="loading" kind="loading" title="正在读取家属关系…" />
    <StateHint v-else-if="error" kind="error" title="家属关系加载失败" :text="error" retry-text="重试" @retry="reload" />
    <view v-for="r in state.family.relations" :key="r.id" class="paper-card">
      <view class="paper-member">
        <view class="paper-avatar paper-avatar-small">{{(r.name||'').slice(0,1)}}</view>
        <view class="paper-copy"><text class="paper-value">{{r.name}} · {{r.relation}}</text><text class="paper-status" :class="{'is-shared':r.status==='ACTIVE','is-waiting':r.status==='PENDING'}">{{({ACTIVE:'已绑定',PENDING:'待确认',REVOKED:'已撤回'})[r.status]||r.status}}</text></view>
      </view>
      <template v-if="r.status==='ACTIVE'">
        <button v-for="x in [['position','位置共享','让家人了解您的位置','pin'],['progress','游览进度','共享路线与游览进度','flag'],['help','求助通知','求助状态变化时通知家人','headset'],['planning','家属建议','允许家属提交路线建议','walk']]" :key="x[0]" class="paper-permission" role="switch" :aria-checked="!!r.permissions[x[0]]" :aria-label="x[1]" @click="permission(r.id,x[0],!r.permissions[x[0]])">
          <image class="paper-row-icon" :src="'/static/outing/icons/'+x[3]+'.svg'"/>
          <view class="paper-copy"><text class="paper-body">{{x[1]}}</text><text class="paper-label">{{x[2]}}</text></view>
          <view class="paper-toggle" :class="{'is-on':r.permissions[x[0]]}"><view/></view>
        </button>
        <view class="paper-button-pair"><button class="paper-secondary" @click="bind(r.id)">绑定演示家属账号</button><button class="paper-secondary" @click="revoke(r.id)">撤回授权</button></view>
      </template>
      <template v-else-if="r.status==='PENDING'"><text class="paper-subtitle">{{r.phone}} · 等待您确认，批准后才会按授权共享。</text><button class="paper-primary paper-card-action" @click="approve(r.id)">批准这层关系</button></template>
      <text v-else class="paper-subtitle">{{r.phone}} · 已撤回，不再共享任何信息</text>
    </view>
    <view class="paper-card">
      <view v-if="!loading && !error && !state.family.relations.length" class="paper-empty"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/people.svg"/></view><text>还没有登记家属</text><text class="paper-label">添加后先进入待确认，由您批准后才会生效。</text></view>
      <text class="paper-heading">添加家属</text><text class="paper-subtitle">登记一位家人，再决定与对方共享哪些信息。</text>
      <button class="paper-secondary" @click="addMember">添加家属</button>
    </view>
    <view class="paper-note"><image src="/static/outing/icons/info.svg"/><text>紧急联系人与家属授权相互独立。关闭位置共享后，家人看不到位置详情。</text></view>
    <view class="paper-actions"><button class="paper-primary" @click="navigate('family-view')">查看家人端</button></view>
  </FlowShell>
</template>
<style src="./paper.css"></style>
