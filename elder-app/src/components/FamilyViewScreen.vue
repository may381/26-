<script setup>
import {ref,computed} from 'vue';import FlowShell from './FlowShell.vue';import {onShow} from '@dcloudio/uni-app';import {state,actorKey,serverSwitchActor,serverFamilyHome,serverSendFamilyMessage,serverSuggestRoute} from './app-state.js';const isFamily=ref(actorKey()==='family'),message=ref(''),loading=ref(false),elder=computed(()=>state['family-elder']||null),messages=computed(()=>state['family-messages']||[]),suggestions=computed(()=>state['family-suggestions']||[]),error=computed(()=>state['family-elder-error']||'');async function load(){if(!isFamily.value)return;loading.value=true;await serverFamilyHome();loading.value=false}onShow(()=>{isFamily.value=actorKey()==='family';load()});async function becomeFamily(){if(await serverSwitchActor('family')){isFamily.value=true;load()}}async function send(){const text=message.value.trim();if(!text)return;if(await serverSendFamilyMessage(text))message.value=''}function suggest(){const routes=state.routes||[];uni.showActionSheet({itemList:['省力线','适中线','登高线'],success:async r=>{const names=['省力线','适中线','登高线'];const routeId=['r1','r2','r3'][r.tapIndex];if(await serverSuggestRoute(routeId,'建议走'+names[r.tapIndex]+'，慢慢走、多休息。')){uni.showToast({title:'建议已发出',icon:'none'})}}})}function openTrip(){if(elder.value&&elder.value.trip)uni.navigateTo({url:'/pages/tour-ongoing'})}
function handlePageAction0(){uni.reLaunch({url:'/pages/home'})}
</script>
<template>
  <FlowShell class="paper-page paper-social" title="家人端">
    <view class="paper-hero paper-contact-hero">
      <view class="paper-illustration"><image src="/static/refined/family.png" mode="aspectFit"/></view>
      <text v-if="isFamily && elder" class="paper-value">{{elder.nickname}}</text>
      <text class="paper-title">家人视角</text><text class="paper-subtitle">在授权范围内，关心家人的每一程</text>
      <view v-if="isFamily && elder" class="paper-share-chips"><text v-for="x in [['position','位置'],['progress','进度'],['help','求助'],['planning','路线建议']]" :key="x[0]" class="paper-status" :class="{'is-shared':elder.permissions[x[0]]}">{{x[1]}} · {{elder.permissions[x[0]]?'已共享':'未共享'}}</text></view>
    </view>
    <view v-if="!isFamily" class="paper-card paper-empty"><view class="paper-disc paper-disc-warm"><image src="/static/outing/icons/people.svg"/></view><text class="paper-value">需要家属身份</text><text>当前是「{{({elder:'老人',elder2:'老人'})[actorKey()]||actorKey()}}」身份，家属视角要用家属身份才能读取授权范围。</text><button class="paper-primary" @click="becomeFamily">切换为家属身份</button></view>
    <template v-else-if="elder">
      <view class="paper-card"><text class="paper-heading">游览进度</text>
        <template v-if="elder.trip && elder.permissions.progress">
          <text class="paper-value">{{(state.routes||[]).find(r=>r.id===elder.trip.routeId)?.name||elder.trip.routeId}}</text>
          <text class="paper-status is-shared">{{elder.trip.status==='ACTIVE'?'正在游览':'已结束'}}</text>
          <view class="paper-inset"><text class="paper-body">已到景点 {{elder.trip.visitedCount}} 个</text><text v-if="elder.trip.nextSpotId" class="paper-subtitle">下一站 · {{elder.trip.nextSpotId}}</text></view>
          <text v-if="!elder.trip.progressAvailable" class="paper-subtitle">老人尚未上报位置进度</text><button class="paper-secondary" @click="openTrip">查看游览页</button>
        </template><view v-else class="paper-inline-empty"><image src="/static/outing/icons/flag.svg"/><text>{{elder.permissions.progress?'暂无进行中的游览':'老人尚未共享游览进度'}}</text></view>
      </view>
      <view class="paper-card"><text class="paper-heading">位置</text><view class="paper-inline-empty"><image src="/static/outing/icons/pin.svg"/><text>{{elder.permissions.position?(elder.locationAvailable?'已共享最近位置':'已开启位置共享，老人尚未上报位置。'):'老人尚未共享位置'}}</text></view></view>
      <view class="paper-card"><text class="paper-heading">求助</text><view v-if="!elder.permissions.help || !elder.helpEvents.length" class="paper-inline-empty"><image src="/static/outing/icons/headset.svg"/><text>{{elder.permissions.help?'暂无求助，收到求助后会显示在这里。':'老人尚未共享求助信息'}}</text></view><view v-for="h in elder.helpEvents" :key="h.id" class="paper-list-item"><text class="paper-label">{{h.timeLabel}}</text><view class="paper-between"><text class="paper-body">{{h.typeLabel}}</text><text class="paper-status">{{h.statusLabel}}</text></view></view></view>
      <view class="paper-card"><text class="paper-heading">家人留言</text><view v-if="!messages.length" class="paper-inline-empty"><image src="/static/outing/icons/heart.svg"/><text>还没有留言，写几句关心的话吧。</text></view><view v-for="m in messages" :key="m.id" class="paper-list-item"><text class="paper-label">{{m.timeLabel}} · {{m.fromFamily?'家属':'老人'}}</text><text class="paper-body">{{m.text}}</text></view><label class="paper-label" for="family-message">给老人留言</label><textarea id="family-message" v-model="message" class="paper-message" maxlength="300" aria-label="家属留言" placeholder="写下想对家人说的话"/><button class="paper-primary paper-card-action" :disabled="!message.trim()" @click="send">发送留言</button></view>
      <view class="paper-card"><text class="paper-heading">路线建议</text><view v-if="!suggestions.length" class="paper-inline-empty"><image src="/static/outing/icons/walk.svg"/><text>还没有建议，可以为老人推荐一条路线。</text></view><view v-for="s in suggestions" :key="s.id" class="paper-list-item"><text class="paper-body">{{s.routeName}}</text><text class="paper-status" :class="{'is-shared':s.status==='ACCEPTED','is-waiting':!['ACCEPTED','REJECTED'].includes(s.status)}">{{s.status==='ACCEPTED'?'老人已采纳':s.status==='REJECTED'?'老人未采纳':'等待老人确认'}}</text></view><button class="paper-secondary" @click="suggest">给老人推荐路线</button></view>
      <view v-if="elder.notice" class="paper-note"><image src="/static/outing/icons/info.svg"/><text>{{elder.notice}}</text></view>
    </template>
    <view v-else class="paper-card paper-empty"><view class="paper-disc"><image src="/static/outing/icons/people.svg"/></view><text>{{loading?'正在读取授权信息…':'未绑定或授权已撤回，无法查看游览与求助信息。'}}</text><text v-if="error" class="paper-label">{{error}}</text><button class="paper-primary" @click="load">重新读取</button></view>
    <view class="paper-actions"><button class="paper-primary" @click="handlePageAction0">返回老人端</button></view>
  </FlowShell>
</template>
<style src="./paper.css"></style>
