<script setup>
const props = defineProps({
  stepIndex: { type: Number, default: 0 },
  total: { type: Number, default: 1 },
  title: { type: String, default: '' },
  hint: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  selected: { type: null, default: null }
})
const emit = defineEmits(['select', 'next'])
const isLast = () => props.stepIndex + 1 >= props.total
</script>
<template>
  <view class="chat-choice" role="group" :aria-label="title">
    <view class="cc-head">
      <text class="cc-badge">第 {{ stepIndex + 1 }} / {{ total }} 步</text>
      <text class="cc-title">{{ title }}</text>
      <text v-if="hint" class="cc-hint">{{ hint }}</text>
    </view>
    <view class="cc-options" role="radiogroup" :aria-label="title">
      <button
        v-for="o in options"
        :key="String(o.value)"
        class="cc-option"
        :class="{ selected: selected === o.value }"
        role="radio"
        :aria-checked="selected === o.value"
        @click="emit('select', o.value)"
      >
        <view class="cc-copy">
          <text class="cc-label">{{ o.label }}</text>
          <text v-if="o.desc" class="cc-desc">{{ o.desc }}</text>
        </view>
        <view class="cc-radio" aria-hidden="true"><view v-if="selected === o.value" class="cc-dot"></view></view>
      </button>
    </view>
    <button class="cc-next" :disabled="selected === null || selected === undefined" @click="emit('next')">
      {{ isLast() ? '生成推荐路线' : '下一步' }}
    </button>
  </view>
</template>
<style scoped>
.chat-choice{width:100%;box-sizing:border-box;padding:calc(var(--c,0.417px)*28);background:#fff;border:1px solid #dceafa;border-radius:calc(var(--c,0.417px)*32);box-shadow:0 calc(var(--c,0.417px)*12) calc(var(--c,0.417px)*26) rgba(91,132,175,.13)}
.cc-badge{display:inline-flex;align-items:center;min-height:calc(var(--c,0.417px)*40);padding:0 calc(var(--c,0.417px)*18);border-radius:999px;background:#eaf4ff;color:#006aff;font-size:max(12px,calc(var(--c,0.417px)*24));font-weight:650;line-height:1.4}
.cc-title{display:block;margin-top:calc(var(--c,0.417px)*14);color:#071537;font-size:max(20px,calc(var(--c,0.417px)*42));font-weight:750;line-height:1.4}
.cc-hint{display:block;margin-top:calc(var(--c,0.417px)*6);color:#52698b;font-size:max(14px,calc(var(--c,0.417px)*28));line-height:1.5}
.cc-options{display:flex;flex-direction:column;gap:calc(var(--c,0.417px)*16);margin-top:calc(var(--c,0.417px)*20)}
.cc-option{display:flex;align-items:center;gap:calc(var(--c,0.417px)*16);width:100%;min-height:calc(var(--c,0.417px)*92);padding:calc(var(--c,0.417px)*16) calc(var(--c,0.417px)*20);background:#fff;border:1px solid #e3edf9;border-radius:calc(var(--c,0.417px)*22);text-align:left;transition:border-color .15s ease,background-color .15s ease,box-shadow .15s ease}
.cc-option:active{transform:scale(.995)}
.cc-option.selected{background:#eef6ff;border-color:#006aff;box-shadow:0 0 0 2px rgba(0,106,255,.12)}
.cc-copy{min-width:0;flex:1}
.cc-label{display:block;color:#071537;font-size:max(17px,calc(var(--c,0.417px)*34));font-weight:650;line-height:1.4}
.cc-desc{display:block;margin-top:calc(var(--c,0.417px)*4);color:#52698b;font-size:max(13px,calc(var(--c,0.417px)*26));line-height:1.45}
.cc-radio{width:calc(var(--c,0.417px)*38);height:calc(var(--c,0.417px)*38);border-radius:50%;border:2px solid #c9d9ec;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:#fff}
.cc-option.selected .cc-radio{border-color:#006aff}
.cc-dot{width:calc(var(--c,0.417px)*20);height:calc(var(--c,0.417px)*20);border-radius:50%;background:#006aff}
.cc-next{width:100%;min-height:calc(var(--c,0.417px)*92);margin-top:calc(var(--c,0.417px)*24);border-radius:999px;background:#006aff;color:#fff;font-size:max(17px,calc(var(--c,0.417px)*34));font-weight:650;line-height:1.4}
.cc-next[disabled]{background:#b9cfe6;color:#fff;opacity:1}
@media (prefers-reduced-motion: reduce){.cc-option{transition:none}.cc-option:active{transform:none}}
</style>
