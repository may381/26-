<script setup>
import {ref,computed} from 'vue'
import {USE_SERVER} from '../api/config.js'
import {listScenicSpots,listScenicFacilities} from '../api/extras.js'
import {FACILITY_CATEGORY} from '../api/adapters.js'
import {onShow} from '@dcloudio/uni-app'
const props=defineProps({mode:String})
import {routes,clockAt,recommended,recommendation} from './travel-data.js'
const readLegacy=k=>readState(k==='elder-travel-preferences'?'preferences':k.replace('elder-',''));const writeLegacy=(k,v)=>writeState(k==='elder-travel-preferences'?'preferences':k.replace('elder-',''),v)
import {state,readState,writeState,refreshState,beginTour,finishTour,serverBeginTour,serverFinishTour,syncServer,serverLoadFamilySuggestions,serverDecideSuggestion,favorite as toggleSaved,navigate} from './app-state.js'
const selected=ref(Number(readLegacy('elder-route')||0)),favorite=ref(state.favorites.some(f=>f.type==='scenic')),preferences=computed(()=>state.preferences||{pace:'尚未设置',stairs:'尚未设置'}),editing=ref(false),draft=ref({...preferences.value})
onShow(()=>{refreshState();favorite.value=state.favorites.some(f=>f.type==='scenic');selected.value=Number(readLegacy('elder-route')||0);syncServer({force:true});loadScenic();if(props.mode==='route-recommend')loadFamilySuggestion()})
const route=computed(()=>routes[selected.value]||routes[0]);const detail=computed(()=>props.mode==='scenic-detail'),recommend=computed(()=>props.mode==='route-recommend')
const scenicSpots=ref(null),scenicFacilities=ref(null)
// 家属建议：家属在家人端提交后，老人这边显示成一条待确认建议。
async function loadFamilySuggestion(){const list=await serverLoadFamilySuggestions();const s=list[0];if(!s)return;const idx=routes.findIndex(r=>r.routeId===s.routeId);if(idx<0)return;writeState('family-suggestion',{id:s.id,relation:'家人',name:'家人',routeId:idx,note:s.note,createdAt:Date.now()})}
const facilityGroups=computed(()=>Object.entries(FACILITY_CATEGORY).map(([type,name])=>({type,name,items:(scenicFacilities.value||[]).map(item=>item.facility).filter(f=>f&&f.type===type)})))
async function loadScenic(){if(props.mode!=='scenic-detail'||!USE_SERVER)return;await Promise.all([listScenicSpots().then(data=>{scenicSpots.value=Array.isArray(data)?data:null}).catch(()=>{scenicSpots.value=null}),listScenicFacilities().then(data=>{scenicFacilities.value=Array.isArray(data)?data:null}).catch(()=>{scenicFacilities.value=null})])}
const title=computed(()=>detail.value?'景区详情':recommend.value?'路线推荐':'路线确认')
function back(){if(getCurrentPages().length>1)uni.navigateBack();else uni.reLaunch({url:'/pages/home'})}
function next(){if(detail.value&&!state.plan){navigate('plan');return}writeLegacy('elder-route',selected.value);uni.navigateTo({url:'/pages/'+(detail.value?'route-recommend':'route-confirm')})}
function choose(i){selected.value=i;writeLegacy('elder-route',i)}
function change(){if(getCurrentPages().some(p=>p.route==='pages/route-recommend'))uni.navigateBack();else uni.redirectTo({url:'/pages/route-recommend'})}
function info(text){uni.showModal({title:'游览提示',content:text,showCancel:false})}
function toggleFavorite(){toggleSaved('scenic');favorite.value=state.favorites.some(f=>f.type==='scenic');uni.showToast({title:favorite.value?'已收藏':'已取消收藏',icon:'none'})}
function edit(){navigate('preferences-edit')}
function save(){preferences.value={...draft.value};writeLegacy('elder-travel-preferences',preferences.value);editing.value=false}
async function startTour(){if(!state.plan){navigate('plan');return}if(state.tour&&!state.tour.ended){uni.showModal({title:'已有进行中的游览',content:'是否结束已有游览，再开始这条路线？结束后会先保存本次游览记录。',success:async r=>{if(r.confirm){await serverFinishTour();if(await serverBeginTour(selected.value,state.plan))navigate('tour-ongoing')}}});return}if(await serverBeginTour(selected.value,state.plan))navigate('tour-ongoing')}
function adopt(){const s=state['family-suggestion'];if(!s)return;choose(s.routeId);if(s.id)serverDecideSuggestion(s.id,'ACCEPT');writeState('family-suggestion',null)}
function ignoreSuggestion(){const s=state['family-suggestion'];if(s&&s.id)serverDecideSuggestion(s.id,'REJECT');writeState('family-suggestion',null)}
function familyChoose(){uni.showModal({title:'家人建议怎么来',content:'家人在「家人端」提交路线建议后，这里会出现一条待确认的建议；采纳只改变选中路线，不会自动开始游览。',showCancel:false})}

function ask(){writeLegacy('elder-topic','我想了解清风园');uni.reLaunch({url:'/pages/chat'})}
</script>
<template>
<view class="travel" :class="{'travel-detail':detail,'travel-recommend':recommend,'travel-confirm':!detail&&!recommend}">
<image class="travel-watermark" src="/static/logo.svg" mode="aspectFit"/>
<view class="travel-header"><button class="back" aria-label="返回" @click="back"><view class="back-chevron"/></button><text>{{title}}</text><button v-if="detail" class="favorite" :aria-label="favorite?'取消收藏':'收藏景区'" @click="toggleFavorite"><image src="/static/travel/star.png"/><view v-if="favorite" class="saved-dot"/></button></view>
<template v-if="detail||recommend">
<image class="park-hero" src="/static/travel/park.jpg" mode="aspectFill"/>
<view class="park-heading"><text class="park-name">清风园</text><text v-if="detail" class="park-tag">适合散步</text></view>
<view class="park-location"><image src="/static/travel/pin.png"/>深圳 · 公园游览</view>
</template>
<template v-if="detail">
<view class="park-description">湖景与绿荫相伴，按自己的节奏慢慢逛。</view>
<view class="travel-panel"><text class="travel-section">游览前先了解</text><view class="info-list"><button v-for="item in [['walk','步行安排','可按体力选择路线'],['stairs','台阶情况','选路线时查看'],['route','途中设施','厕所、休息点、出口']]" :key="item[1]" @click="item[0]==='route'?info('此处展示模拟设施信息。厕所、休息点和出口以景区现场信息为准。'):next()"><view class="travel-disc"><image :src="'/static/travel/'+item[0]+'.png'"/></view><view class="travel-grow"><text class="travel-bold">{{item[1]}}</text><text class="travel-sub">{{item[2]}}</text></view><text class="travel-chevron">›</text></button></view></view>
<view v-if="scenicSpots&&scenicSpots.length" class="travel-panel"><text class="travel-section">这里的景点</text><view class="info-list"><button v-for="s in scenicSpots" :key="s.id" @click="navigate('spot')"><view class="travel-disc"><image src="/static/travel/pin.png"/></view><view class="travel-grow"><text class="travel-bold">{{s.name}}</text><text class="travel-sub">{{s.description||'点开查看景点讲解'}}</text></view><text class="travel-chevron">›</text></button></view></view>
<view v-if="scenicFacilities&&scenicFacilities.length" class="travel-panel"><text class="travel-section">景区设施</text><view class="facility-grid"><button v-for="g in facilityGroups.filter(x=>x.items.length)" :key="g.type" @click="info(g.name+'：'+g.items.map(x=>x.name).join('、'))"><image :src="'/static/travel/'+({TOILET:'people',BENCH:'seat',EXIT:'exit',MEDICAL:'walk',SERVICE_DESK:'route'}[g.type]||'route')+'.png'"/><text>{{g.name}} {{g.items.length}}</text></button></view></view>
<view class="travel-panel"><text class="travel-section">您可以这样逛</text><button class="suggest-route" @click="next"><image src="/static/travel/park.jpg" mode="aspectFill"/><view class="travel-grow"><text class="travel-bold">{{routes[0].name}}</text><text class="travel-sub">{{routes[0].desc}}</text><text class="travel-link">查看路线推荐 ›</text></view></button></view>
<view class="travel-panel facilities"><text class="travel-section">需要时找得到</text><view class="facility-grid"><button v-for="item in [['people','找厕所'],['seat','找休息点'],['exit','找出口']]" :key="item[1]" @click="info(item[1]+'：当前为模拟设施入口，实际位置需接入景区数据。')"><image :src="'/static/travel/'+item[0]+'.png'"/><text>{{item[1]}}</text></button></view></view>
<view class="travel-notice"><text>!</text>演示数据 · 路线与设施以景区现场信息为准。</view>
<view class="travel-actions"><button class="travel-secondary" @click="ask"><image src="/static/travel/chat.png"/>问问我</button><button class="travel-primary" @click="next">帮我选路线</button></view>
</template>
<template v-else-if="recommend"><view class="travel-panel"><text class="travel-section">本次安排</text><text class="travel-sub">{{state.plan?state.plan.duration+'分钟 · '+state.plan.energy+' · '+state.plan.companions:'先说说这次怎么逛'}}</text><button class="travel-link" @click="navigate('plan')">{{state.plan?'修改':'这次怎么逛'}}</button></view><view v-if="state['family-suggestion']" class="travel-panel"><text>{{state['family-suggestion'].relation}}建议：{{routes[state['family-suggestion'].routeId].name}}</text><button @click="adopt">采用</button><button @click="ignoreSuggestion">忽略</button></view><button class="travel-link" @click="familyChoose">让家人帮我选</button>
<button class="preferences" @click="edit"><view class="travel-disc"><image src="/static/travel/walk.png"/></view><text>您的步行偏好：{{preferences.pace}} · {{preferences.stairs}}</text><text class="travel-link">修改 ›</text></button>
<text class="travel-section route-list-heading">为您准备了{{routes.length}}条路线</text>
<button v-for="(r,i) in routes" :key="r.name" class="route-choice" :class="{chosen:selected===i}" :aria-label="r.name+(selected===i?'，已选中':'，未选中')" @click="choose(i)"><view class="choice-radio"><text v-if="selected===i">✓</text></view><view class="route-info"><view class="route-name">{{r.name}}<text v-if="i===recommended(state.plan,state.preferences)" class="recommend-tag">推荐</text></view><view class="route-stat"><image src="/static/travel/clock.png"/>约{{r.minutes}}分钟 · 约{{r.km}}公里</view><view class="route-stat"><image src="/static/travel/stairs.png"/>{{r.terrain}} · {{r.stairs}}</view><view class="route-stat"><image src="/static/travel/seat.png"/>休息点{{r.seats}}处 · 厕所{{r.toilets}}处</view><text class="route-description">{{r.desc}} {{recommendation(r,state.plan,state.preferences)}}</text></view><image class="route-map-small" :src="'/static/travel/map-'+i+'.jpg'" mode="aspectFill"/></button>
<view class="travel-notice"><text>!</text>时长包含短暂休息，可在途中调整。</view>
<view class="travel-actions recommend-actions"><text>已选：<text class="travel-link">{{route.name}}</text></text><button class="travel-primary" @click="next">查看并确认路线 ›</button></view>
</template>
<template v-else>
<view class="confirm-park-name">清风园</view>
<view class="travel-panel route-summary"><view class="travel-section-row"><text class="travel-section">{{route.name}}</text><button class="travel-link" @click="change">换一条 ›</button></view><view class="summary-metrics"><text>约{{route.minutes}}分钟</text><text>约{{route.km}}公里</text><text>{{route.stairs}}</text></view><image class="large-map" :src="selected===0?'/static/travel/map-large.jpg':'/static/travel/map-'+selected+'.jpg'" mode="aspectFill"/></view>
<view class="travel-panel"><text class="travel-section">这次这样走</text><view class="itinerary"><view v-for="(stop,i) in route.stops" :key="stop" class="itinerary-stop"><view class="stop-number">{{i+1}}</view><view class="travel-grow"><text class="travel-bold">{{stop}}</text><text class="travel-sub">{{clockAt('09:00',route.stations[i].at)}} · {{route.stations[i].kind}} · {{route.notes[i]}}</text></view></view></view></view>
<view class="travel-panel"><text class="travel-section">途中设施</text><view class="confirm-facilities"><view><image src="/static/travel/seat.png"/><view><text class="travel-bold">休息点{{route.seats}}处</text><text class="travel-sub">沿途设有休息点</text></view></view><view><image src="/static/travel/people.png"/><view><text class="travel-bold">厕所{{route.toilets}}处</text><text class="travel-sub">沿途设有厕所</text></view></view></view></view>
<view class="travel-panel arrangement"><view class="travel-section-row"><text class="travel-section">您的游览安排</text><text class="travel-sub">{{state.plan?state.plan.duration+'分钟 · '+state.plan.energy+' · '+state.plan.companions:'尚未设置本次安排'}}</text><button class="travel-link" @click="navigate('plan')">修改本次安排</button><button class="travel-link" @click="edit">修改 ›</button></view><button @click="edit"><image src="/static/travel/walk.png"/><text>步行节奏</text><text>{{preferences.pace}} ›</text></button><button @click="edit"><image src="/static/travel/stairs.png"/><text>路线偏好</text><text>{{preferences.stairs}} ›</text></button></view>
<view class="travel-notice"><text>!</text>走累了可以随时说“我累了”，调整路线。</view>
<button class="travel-link" @click="toggleSaved('route',selected)">{{state.favorites.some(f=>f.type==='route'&&f.routeId===selected)?'取消路线收藏':'收藏这条路线'}}</button><view class="travel-actions"><button class="travel-secondary" @click="change">再看看</button><button class="travel-primary" @click="startTour()">确认并开始游览</button></view>
</template>
<view v-if="editing" class="travel-modal-mask" @click.self="editing=false"><view class="travel-modal"><text class="travel-section">修改步行偏好</text><text class="travel-bold">步行节奏</text><view class="preference-options"><button v-for="p in ['慢慢走','正常步速']" :key="p" :class="{on:draft.pace===p}" @click="draft.pace=p">{{p}}</button></view><text class="travel-bold">路线偏好</text><view class="preference-options"><button v-for="p in ['少台阶','避开台阶']" :key="p" :class="{on:draft.stairs===p}" @click="draft.stairs=p">{{p}}</button></view><view class="modal-buttons"><button class="travel-secondary" @click="editing=false">取消</button><button class="travel-primary" @click="save">保存</button></view><text class="travel-sub">偏好会保存到个人档案；路线来自后端演示数据。</text></view></view>
</view>
</template>
<style src="./travel.css"></style>
