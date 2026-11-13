<script setup>
import {ref,computed} from 'vue'
import {onShow} from '@dcloudio/uni-app'
import {USE_SERVER} from '../api/config.js'
import {listMemories,deleteMemory} from '../api/extras.js'
import FlowShell from './FlowShell.vue'
import {state,writeState,back,serverSaveProfile} from './app-state.js'
const props=defineProps({edit:Boolean});const step=ref(1)
const draft=ref(JSON.parse(JSON.stringify(state.preferences||{walkDuration:null,pace:'',stairs:'',interests:[],avoid:[]})))
const memories=ref([]),memoryLoading=ref(false),memoryError=ref(''),deleting=ref('')
async function loadMemories(){if(!props.edit||!USE_SERVER)return;memoryLoading.value=true;memoryError.value='';try{const data=await listMemories();if(!Array.isArray(data))throw new Error();memories.value=data}catch{memoryError.value='偏好列表没有读出来，稍后可以再试。'}finally{memoryLoading.value=false}}
onShow(loadMemories)
function removeMemory(memory){if(deleting.value)return;uni.showModal({title:'删除这条记忆',content:'删除后我下次不会再参考这条偏好。确定删除吗？',confirmText:'删除',success:async r=>{if(!r.confirm||deleting.value)return;deleting.value=memory.memoryId;try{await deleteMemory(memory.memoryId,memory.version);memories.value=memories.value.filter(x=>x.memoryId!==memory.memoryId)}catch(e){uni.showToast({title:e?.status===409?'这条记忆已变化，请重开页面再删':'删除失败，请稍后再试',icon:'none'});if(e?.status===409)await loadMemories()}finally{deleting.value=''}}})}
const durations=[[20,'20分钟以内'],[40,'约40分钟'],[60,'一小时以上'],['unknown','不确定']]
const durationLabel=computed(()=>draft.value.walkDuration==='unknown'?'还不确定':durations.find(d=>d[0]===draft.value.walkDuration)?.[1]||'尚未设置')
function toggle(key,value){let list=draft.value[key];if(key==='avoid'){if(value==='暂时没有'){draft.value.avoid=list.includes(value)?[]:[value];return}list=draft.value.avoid=list.filter(x=>x!=='暂时没有')}const i=list.indexOf(value);i<0?list.push(value):list.splice(i,1)}
function skip(){writeState('onboarded',true);uni.reLaunch({url:'/pages/home'})}
function preferencePatch(){const p={};if(typeof draft.value.walkDuration==='number')p.walkDurationMin=Math.min(1440,Math.max(1,draft.value.walkDuration));const avoid=draft.value.avoid||[];p.avoidSteps=avoid.includes('台阶多')||draft.value.stairs==='少台阶'||draft.value.stairs==='避开台阶';if(Array.isArray(draft.value.interests)&&draft.value.interests.length)p.interests=draft.value.interests;if(draft.value.pace==='慢慢走')p.walkSpeed='SLOW';else if(draft.value.pace==='正常步速')p.walkSpeed='MEDIUM';return p}
async function save(){writeState('preferences',{...draft.value,stairs:draft.value.stairs||(draft.value.avoid.includes('台阶多')?'少台阶':''),updatedAt:Date.now()});await serverSaveProfile(preferencePatch());if(props.edit)back();else skip()}
const descriptions={20:'短途走走，轻松一些',40:'慢慢欣赏，途中休息',60:'多走一会儿，看看风景',unknown:'先了解路线，再决定'}
const interestIcons={'公园散步':'walk','自然风景':'mountain','历史文化':'file','看展学习':'flag'}
</script>

<template>
  <FlowShell class="paper-page" :title="edit?'修改出游偏好':'出游习惯'">
    <view class="paper-preferences">
      <view v-if="!edit&&step<4" class="paper-progress">
        <view class="paper-progress-top"><text>第 {{step}} 步，共 3 步</text><button v-if="step>1" @click="step--">上一步</button></view>
        <view class="paper-progress-track"><view v-for="n in 3" :key="n" :class="{complete:n<=step}"/></view>
      </view>
      <view class="paper-hero paper-preference-hero">
        <view class="paper-disc paper-disc-large"><image :src="'/static/outing/icons/'+(edit||step===4?'heart':step===1?'walk':step===2?'mountain':'seat')+'.svg'"/></view>
        <text class="paper-title">{{edit?'按您的习惯，轻松出游':step===1?'平时走多久舒服？':step===2?'喜欢看些什么？':step===3?'想尽量避开什么？':'我的出游习惯'}}</text>
        <text class="paper-subtitle">{{edit?'让路线更合您的心意':step===1?'按平时的体力选，不确定也没关系':step===2?'可以多选，也可以先不选':step===3?'选择您在意的，让路线更合适':'只有点保存后，我才会记住。'}}</text>
        <view v-if="edit" class="paper-chips"><text>{{durationLabel}}</text><text v-if="draft.pace">{{draft.pace}}</text><text v-if="draft.stairs">{{draft.stairs}}</text><text v-for="x in draft.interests" :key="x">{{x}}</text></view>
      </view>
      <view v-if="edit||step===1" :class="edit?'paper-card':'paper-choice-section'">
        <text v-if="edit" class="paper-heading">能走多久</text>
        <view class="paper-options">
          <button v-for="d in durations" :key="d[1]" class="paper-option" :class="{'paper-selected':draft.walkDuration===d[0]}" :aria-pressed="draft.walkDuration===d[0]" @click="draft.walkDuration=d[0]">
            <view class="paper-disc"><image src="/static/outing/icons/clock.svg"/></view>
            <view class="paper-copy"><text class="paper-value">{{d[1]}}</text><text class="paper-label">{{descriptions[d[0]]}}</text></view>
            <view class="paper-check"><image v-if="draft.walkDuration===d[0]" src="/static/outing/icons/check.svg"/></view>
          </button>
        </view>
      </view>
      <view v-if="edit" class="paper-card">
        <text class="paper-heading">走路节奏</text>
        <view class="paper-options"><button v-for="x in ['慢慢走','正常步速']" :key="x" class="paper-option" :class="{'paper-selected':draft.pace===x}" :aria-pressed="draft.pace===x" @click="draft.pace=x">
          <view class="paper-disc"><image src="/static/outing/icons/walk.svg"/></view><view class="paper-copy"><text class="paper-value">{{x}}</text><text class="paper-label">{{x==='慢慢走'?'放慢脚步，沿途欣赏':'按平时的节奏走'}}</text></view><view class="paper-check"><image v-if="draft.pace===x" src="/static/outing/icons/check.svg"/></view>
        </button></view>
      </view>
      <view v-if="edit" class="paper-card">
        <text class="paper-heading">路线选择</text>
        <view class="paper-options"><button v-for="x in ['少台阶','避开台阶','不限']" :key="x" class="paper-option" :class="{'paper-selected':draft.stairs===x}" :aria-pressed="draft.stairs===x" @click="draft.stairs=x">
          <view class="paper-disc"><image src="/static/outing/icons/stairs.svg"/></view><view class="paper-copy"><text class="paper-value">{{x}}</text><text class="paper-label">{{x==='少台阶'?'尽量选择平缓路线':x==='避开台阶'?'优先选择无台阶路线':'根据路线再决定'}}</text></view><view class="paper-check"><image v-if="draft.stairs===x" src="/static/outing/icons/check.svg"/></view>
        </button></view>
      </view>
      <view v-if="edit||step===2" :class="edit?'paper-card':'paper-choice-section'">
        <text v-if="edit" class="paper-heading">喜欢的活动</text>
        <view class="paper-options"><button v-for="x in ['公园散步','自然风景','历史文化','看展学习']" :key="x" class="paper-option" :class="{'paper-selected':draft.interests.includes(x)}" :aria-pressed="draft.interests.includes(x)" @click="toggle('interests',x)">
          <view class="paper-disc"><image :src="'/static/outing/icons/'+interestIcons[x]+'.svg'"/></view><view class="paper-copy"><text class="paper-value">{{x}}</text><text class="paper-label">{{x==='公园散步'?'沿着步道慢慢走':x==='自然风景'?'看看绿荫与湖景':x==='历史文化'?'了解地方的故事':'看一看，学一点'}}</text></view><view class="paper-check"><image v-if="draft.interests.includes(x)" src="/static/outing/icons/check.svg"/></view>
        </button></view>
      </view>
      <view v-if="!edit&&step===3" class="paper-choice-section">
        <view class="paper-options"><button v-for="x in ['台阶多','走得太久','休息点少','暂时没有']" :key="x" class="paper-option" :class="{'paper-selected':draft.avoid.includes(x)}" :aria-pressed="draft.avoid.includes(x)" @click="toggle('avoid',x)">
          <view class="paper-disc"><image :src="'/static/outing/icons/'+(x==='台阶多'?'stairs':x==='走得太久'?'clock':x==='休息点少'?'seat':'smile')+'.svg'"/></view><view class="paper-copy"><text class="paper-value">{{x}}</text><text class="paper-label">{{x==='暂时没有'?'暂时没有特别要避开的':'推荐时尽量为您避开'}}</text></view><view class="paper-check"><image v-if="draft.avoid.includes(x)" src="/static/outing/icons/check.svg"/></view>
        </button></view>
      </view>
      <template v-if="!edit&&step===4">
        <view v-for="(x,i) in [['我喜欢',draft.interests.join('、')||'尚未设置'],['我平时能走',durationLabel],['我想尽量避开',draft.avoid.join('、')||'尚未设置']]" :key="x[0]" class="paper-card">
          <view class="paper-data-row"><view class="paper-disc"><image :src="'/static/outing/icons/'+['heart','clock','seat'][i]+'.svg'"/></view><view class="paper-copy"><text class="paper-label">{{x[0]}}</text><text class="paper-value">{{x[1]}}</text></view></view>
          <button class="paper-secondary" @click="step=[2,1,3][i]">修改</button>
        </view>
      </template>
      <view v-if="edit" class="paper-card paper-memory">
        <text class="paper-heading">小银记住的偏好</text>
        <view v-if="memoryLoading" class="paper-empty"><view class="paper-disc"><image src="/static/outing/icons/clock.svg"/></view><text>正在读取记住的偏好…</text><button class="paper-secondary" disabled>正在读取…</button></view>
        <view v-else-if="memoryError" class="paper-empty"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/info.svg"/></view><text>{{memoryError}}</text><button class="paper-secondary" @click="loadMemories">重新读取</button></view>
        <view v-else-if="!memories.length" class="paper-empty"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/heart.svg"/></view><text>还没有记住的偏好</text><button class="paper-secondary" @click="loadMemories">刷新偏好</button></view>
        <view v-for="memory in memories" :key="memory.memoryId" class="paper-memory-row">
          <view class="paper-disc"><image src="/static/outing/icons/heart.svg"/></view>
          <text class="paper-memory-content">{{memory.content}}</text>
          <button class="paper-delete" @click="removeMemory(memory)">{{deleting===memory.memoryId?'删除中…':'点击删除'}}</button>
        </view>
      </view>
      <view class="paper-actions">
        <button v-if="!edit&&step<4" class="paper-primary" :disabled="step===1&&draft.walkDuration===null" @click="step++">{{step===3?'看看我的偏好':'下一步'}}</button>
        <button v-else class="paper-primary" @click="save">{{edit?'保存偏好':'保存，去看看'}}</button>
        <button v-if="!edit" class="paper-skip" @click="skip">暂时跳过</button>
      </view>
    </view>
  </FlowShell>
</template>

<style src="./paper.css"></style>
