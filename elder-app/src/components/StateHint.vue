<script setup>
import {computed} from 'vue'
const props = defineProps({kind: {type: String, default: 'loading'}, title: {type: String, default: ''}, text: {type: String, default: ''}, retryText: {type: String, default: ''}})
const emit = defineEmits(['retry'])
const defaults = {loading: '正在加载…', error: '加载失败', offline: '未连接后端'}
const icon = computed(() => (props.kind === 'loading' ? '' : '/static/outing/icons/info.svg'))
</script>
<template>
  <view class="state-hint">
    <view v-if="kind === 'loading'" class="state-spinner" aria-hidden="true"></view>
    <image v-else class="state-icon" :src="icon" mode="aspectFit"/>
    <text class="state-title">{{ title || defaults[kind] || '加载失败' }}</text>
    <text v-if="text" class="state-text">{{ text }}</text>
    <button v-if="retryText && kind !== 'loading'" class="state-retry" @click="emit('retry')">{{ retryText }}</button>
  </view>
</template>
<style scoped>
.state-hint{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px 16px;text-align:center}
.state-spinner{width:32px;height:32px;border-radius:50%;border:3px solid #dbe9fb;border-top-color:#006aff;animation:state-spin .9s linear infinite}
@keyframes state-spin{to{transform:rotate(360deg)}}
.state-icon{width:32px;height:32px;display:block}
.state-title{margin-top:12px;font-size:17px;font-weight:700;color:#071537;line-height:1.5}
.state-text{margin-top:6px;font-size:14px;color:#4e648a;line-height:1.6}
.state-retry{margin-top:16px;min-height:48px;height:48px;padding:0 28px;border-radius:24px;background:#006aff;color:#fff;font-size:16px;font-weight:600;line-height:48px;border:0}
.state-retry:after{border:0}
</style>
