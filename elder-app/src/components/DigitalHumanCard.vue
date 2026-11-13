<script setup>
import {computed} from 'vue'
import OIcon from './OutingIcon.vue'
import {routes} from './travel-data.js'
import {onShow} from '@dcloudio/uni-app'
import {state,refreshState,tourView} from './app-state.js'
const AVATAR_SRC='/static/digital-human/placeholder-pet.jpg'
onShow(refreshState)
const tour=computed(tourView)
const touring=computed(()=>state.tour?.startedAt&&!state.tour?.ended)
const finished=computed(()=>state['trip-record']?.createdAt && new Date(state['trip-record'].createdAt).toDateString()===new Date().toDateString())
const label=computed(()=>touring.value?'正在陪您游览':finished.value?'今天游览完成':'我的数字分身 · 小银')
const greeting=computed(()=>state.profile.nickname+'，'+(touring.value?'走得还顺利吗？':finished.value?'今天辛苦了':new Date().getHours()<12?'上午好':new Date().getHours()<18?'下午好':'晚上好'))
const memoryIcons=['file','clock','stairs']
const memory=computed(()=>touring.value?tour.value.routeData.name+' · 下一站 '+(tour.value.nextStop?.name||'行程结束')+' · 剩余'+tour.value.remainingMin+'分钟':finished.value?(routes[Number(state['trip-record'].route)]?.name||'本次游览')+' · '+state['trip-record'].minutes+'分钟 · 已保存':state.preferences?[...(state.preferences.interests||[]),state.preferences.walkDuration && !['unknown'].includes(state.preferences.walkDuration)?'约'+state.preferences.walkDuration+'分钟':'步行时长未设置',state.preferences.stairs].filter(Boolean).join(' · '):'我还不了解您的习惯，先聊聊？')
function open(){uni.navigateTo({url:'/pages/'+(touring.value?'tour-ongoing':finished.value?'trip-record':!state.preferences?'preferences':'chat')})}
function explain(){uni.showModal({title:'它是怎么记住我的？',content:'它记得：称呼、出游习惯、这次安排、走过的路线。\n怎么记住：每次只有您确认后才写入。\n您能改：我的 → 个人档案 / 出游偏好。\n它不会：不冒充真人、不替您做决定、不做医疗诊断。',showCancel:false})}
</script>
<template><view class="digital-human"><view class="dh-top"><button @click="explain">{{label}}</button><text>{{new Date().toLocaleDateString('zh-CN',{month:'long',day:'numeric'})}} · {{state.profile.city}}</text></view><view class="dh-chat"><view class="dh-portrait"><image :src="AVATAR_SRC" alt="小银数字分身演示占位形象" aria-label="小银数字分身演示占位形象" mode="aspectFill"/><view class="dh-name">小银 <text>您的智游分身 · 在线</text></view></view><view class="dh-bubble"><view class="dh-greeting">{{greeting}}</view><text class="dh-question">今天想去哪儿走走？</text><text v-if="state.preferences?.interests?.length" class="dh-known">我记得您喜欢{{state.preferences.interests.join('、')}}。</text><view class="dh-memory"><view v-for="(tag,i) in memory.split(' · ')" :key="i" class="dh-tag"><image v-if="i===0&&(state.preferences||touring||finished)" class="oi" src="/static/travel/star.png" mode="aspectFit"/><OIcon v-else-if="state.preferences||touring||finished" :name="memoryIcons[i%3]"/><text>{{tag}}</text></view></view><button class="dh-action" @click="open">{{touring?'继续陪您走':finished?'看看这次记录':!state.preferences?'告诉我您的习惯':'和小银说句话'}} ›</button></view></view></view></template>
<style scoped>
.digital-human{position:relative;margin:16px 0 20px;padding:18px;border-radius:30px;background:radial-gradient(at 90% 55%,#fff1b8,transparent 65%),#e7f2ff;color:#071537;box-sizing:border-box;min-width:0}
.dh-top{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:13px;margin-bottom:10px}
.dh-top button{padding:0;margin:0;background:transparent;font-size:13px;color:#164f91;min-height:44px;line-height:44px}
.dh-top button:after{border:0}
.dh-top button:before{content:'';display:inline-block;width:7px;height:7px;background:#17a86a;border-radius:50%;margin-right:6px}
.dh-top text{white-space:nowrap;font-size:12px}
.dh-chat{display:flex;align-items:flex-start;gap:12px;min-width:0}
.dh-portrait{position:relative;flex:0 0 120px;width:120px;text-align:center}

.dh-portrait image{display:block;position:relative;width:120px;height:120px;border:5px solid #fff;border-radius:50%;box-sizing:border-box;box-shadow:5px 10px 25px #507abc24}
.dh-name{margin:8px auto 0;padding:6px 8px;background:#fff;border-radius:12px;font-size:12px;font-weight:700;line-height:1.35;text-align:center;box-sizing:border-box}
.dh-name text{display:block;font-size:10px;font-weight:400;color:#4e648a;margin-top:1px}
.dh-bubble{position:relative;flex:1;min-width:0;padding:12px 14px;background:#fff;border:1px solid #dceaff;border-radius:18px;box-shadow:0 8px 20px #164f9110;box-sizing:border-box;overflow-wrap:anywhere}
.dh-bubble:before{content:'';position:absolute;left:-6px;top:30px;width:12px;height:12px;background:#fff;border-left:1px solid #dceaff;border-bottom:1px solid #dceaff;transform:rotate(45deg)}
.dh-greeting{font-size:18px;font-weight:700;line-height:1.5}
.dh-question{display:block;font-size:16px;line-height:1.7;margin-top:2px}
.dh-known{display:block;color:#006aff;font-size:14px;font-weight:700;line-height:1.6;margin-top:4px}
.dh-memory{display:flex;flex-wrap:wrap;gap:4px 8px;margin:8px 0 0;min-width:0}
.dh-tag{display:flex;align-items:center;gap:3px;font-size:12px;color:#4e648a;line-height:1.5;min-width:0;max-width:100%}
.dh-tag .oi{width:14px;height:14px;flex:none}
.dh-tag text{min-width:0;overflow-wrap:anywhere}
.dh-action{display:flex;align-items:center;justify-content:flex-end;width:100%;margin-top:2px;padding:0;background:transparent;border:0;border-radius:0;box-shadow:none;color:#006aff;font-size:16px;font-weight:600;min-height:36px;line-height:1.5}
.dh-action:after{border:0}
@media (max-width:380px){.dh-portrait{flex:0 0 104px;width:104px}.dh-portrait image{width:104px;height:104px}.dh-greeting{font-size:17px}.dh-bubble{padding:10px 12px}}
</style>
