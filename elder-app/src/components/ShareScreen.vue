<script setup>
import {ref, computed, watch} from 'vue'
import {getSharedRecord} from '../api/index.js'
import {API_BASE} from '../api/config.js'

const props = defineProps({shareId: {type: String, default: ''}})
const state = ref('loading')
const data = ref(null)
const errorText = ref('')

function asDate(value) {
  if (!value) return null
  const d = new Date(value)
  return isNaN(d.getTime()) ? null : d
}
function fmtDate(value) {
  const d = asDate(value)
  return d ? d.toLocaleDateString('zh-CN', {year: 'numeric', month: 'long', day: 'numeric'}) : '—'
}
function fmtTime(value) {
  const d = asDate(value)
  return d ? d.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit', hour12: false}) : ''
}

const minutes = computed(() => Math.max(1, Math.round(((data.value && data.value.durationSeconds) || 0) / 60)))
const visitedCount = computed(() => ((data.value && data.value.visitedSpotIds) || []).length)
const timeRange = computed(() => (data.value ? fmtTime(data.value.startedAt) + '—' + fmtTime(data.value.finishedAt) : ''))
const mediaList = computed(() =>
  ((data.value && data.value.mediaUrls) || []).map(url => (/^https?:\/\//i.test(url) ? url : API_BASE + url))
)

async function load() {
  if (!props.shareId) {
    state.value = 'error'
    errorText.value = '链接不完整，缺少分享编号。'
    return
  }
  state.value = 'loading'
  errorText.value = ''
  try {
    data.value = await getSharedRecord(props.shareId)
    state.value = 'ok'
  } catch (e) {
    data.value = null
    state.value = 'error'
    errorText.value = (e && e.message) || '分享加载失败，请稍后重试。'
  }
}

watch(() => props.shareId, load, {immediate: true})

function preview(index) {
  if (!mediaList.value.length) return
  uni.previewImage({current: mediaList.value[index], urls: mediaList.value})
}
function openApp() {
  uni.reLaunch({url: '/pages/home'})
}
</script>
<template>
  <view class="flow paper-page share-page">
    <view class="share-head">
      <view class="share-brand">
        <image src="/static/home/brand-mark.png" mode="aspectFit"/>
        <text>银龄智游</text>
      </view>
      <text class="share-kicker">游览小结</text>
    </view>

    <view v-if="state === 'loading'" class="paper-card share-card">
      <text class="paper-body">正在加载分享…</text>
    </view>

    <view v-else-if="state === 'error'" class="paper-card share-card share-error">
      <text class="paper-heading">分享已失效或链接不完整</text>
      <text class="paper-help">{{ errorText }} 请让家人重新生成分享链接。</text>
    </view>

    <template v-else>
      <view class="paper-card share-card share-hero">
        <text class="paper-title">{{ data.routeName || '游览小结' }}</text>
        <text class="paper-subtitle">{{ fmtDate(data.startedAt) }} · {{ timeRange }}</text>
      </view>

      <view class="paper-card share-card">
        <text class="paper-heading">这次游览</text>
        <view class="share-stats">
          <view class="share-stat">
            <text class="share-num">{{ minutes }}</text>
            <text class="share-cap">分钟</text>
          </view>
          <view class="share-stat">
            <text class="share-num">{{ visitedCount }}</text>
            <text class="share-cap">个景点</text>
          </view>
          <view class="share-stat">
            <text class="share-num share-num-sm">{{ fmtDate(data.expiresAt) }}</text>
            <text class="share-cap">分享有效期</text>
          </view>
        </view>
      </view>

      <view v-if="mediaList.length" class="paper-card share-card">
        <text class="paper-heading">照片</text>
        <view class="share-photos">
          <image v-for="(url, i) in mediaList" :key="url" :src="url" mode="aspectFill" @click="preview(i)"/>
        </view>
      </view>

      <view class="paper-card share-card">
        <text class="paper-heading">足迹</text>
        <text class="paper-body">到访 {{ visitedCount }} 个景点 · 明细以老人端游览记录为准。</text>
      </view>

      <text class="share-note">由银龄智游生成 · 链接 7 天后失效</text>
    </template>

    <view class="share-footer">
      <button class="paper-primary" @click="openApp">打开银龄智游</button>
    </view>
  </view>
</template>
<style src="./paper.css"></style>
<style src="./share-page.css"></style>
