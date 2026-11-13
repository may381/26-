<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getAssistantSystemStatus, queryAssistantStatus, resetAssistant, sendAssistant, type AssistantTopic } from '../../api/assistant'

interface Message { id: number; role: 'user' | 'assistant'; text: string; detail?: string; pending?: boolean }
const topics: Array<{ id: AssistantTopic; label: string; hint: string }> = [
  { id: 'auto', label: '综合助手', hint: '帮您判断该找哪项服务' },
  { id: 'tourism', label: '适老出行', hint: '景点、路线和行程规划' },
  { id: 'fraud', label: '防诈核对', hint: '可疑消息、链接和转账提醒' },
]
const quickPrompts: Record<AssistantTopic, string[]> = {
  auto: ['长沙有哪些适合老人的景点？', '这条退款短信可信吗？'],
  tourism: ['介绍长沙适合老人少走路的景点', '规划一条轻松的橘子洲路线'],
  fraud: ['客服让我点链接退款并提供验证码，是真的吗？', '有人自称公安让我转钱到安全账户'],
}
const topic = ref<AssistantTopic>('auto')
const input = ref('')
const busy = ref(false)
const online = ref(false)
const statusText = ref('正在检查智能服务…')
const scrollTop = ref(0)
let sequence = 2
const messages = ref<Message[]>([{ id: 1, role: 'assistant', text: '您好，我是银龄智游助手。出行计划和可疑消息都可以慢慢告诉我。', detail: '重要信息请再次核实，涉及转账时先暂停操作。' }])
const current = computed(() => topics.find(item => item.id === topic.value) || topics[0])

async function checkStatus() {
  try { const result = await getAssistantSystemStatus(); online.value = true; statusText.value = result.mode || 'A1 智能服务已连接' }
  catch { online.value = false; statusText.value = '智能服务暂未连接' }
}
onShow(checkStatus)
function selectTopic(value: AssistantTopic) { if (!busy.value) topic.value = value }
function usePrompt(value: string) { input.value = value }
function extractReply(result: Record<string, unknown>) {
  if (typeof result.reply === 'string' && result.reply.trim()) return result.reply
  const domainResult = result.domainResult as Record<string, unknown> | undefined
  if (domainResult && typeof domainResult.text === 'string') return domainResult.text
  return '服务已返回结果，请查看执行详情。'
}
function traceDetail(result: Record<string, unknown>) {
  const trace = Array.isArray(result.executionTrace) ? result.executionTrace : []
  const labels = trace.map(item => item && typeof item === 'object' ? String((item as Record<string, unknown>).label || '') : '').filter(Boolean)
  return labels.length ? `调用过程：${labels.join(' → ')}` : ''
}
async function waitForFraudResult(message: Message) {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 1500))
    const result = await queryAssistantStatus()
    const state = String(result.state || '')
    message.text = extractReply(result); message.detail = traceDetail(result)
    if (!['WAIT_RESULT', 'SUBMISSION_UNCERTAIN'].includes(state)) { message.pending = false; return }
  }
  message.text = '分析仍在进行，可以稍后继续查询。'; message.pending = false
}
async function send() {
  const text = input.value.trim(); if (!text || busy.value) return
  messages.value.push({ id: sequence++, role: 'user', text })
  const answer: Message = { id: sequence++, role: 'assistant', text: '正在为您处理…', pending: true }
  messages.value.push(answer); input.value = ''; busy.value = true
  await nextTick(); scrollTop.value += 10000
  try {
    const result = await sendAssistant(text, topic.value)
    answer.text = extractReply(result); answer.detail = traceDetail(result)
    if (String(result.state || '') === 'WAIT_RESULT') await waitForFraudResult(answer); else answer.pending = false
  } catch (error) {
    answer.text = error instanceof Error ? error.message : '本次请求未完成，请稍后重试。'
    answer.detail = topic.value === 'tourism' ? '旅游真实地点查询需要配置高德 Web 服务 Key。' : '未假定请求已经成功。'; answer.pending = false
  } finally { busy.value = false; await nextTick(); scrollTop.value += 10000 }
}
async function newConversation() {
  if (busy.value) return
  try { await resetAssistant() } catch { /* 仍允许清理本地展示 */ }
  messages.value = [{ id: sequence++, role: 'assistant', text: '已开始新的对话。请告诉我这次需要出行帮助还是防诈核对。' }]
}
function openFamily() { uni.navigateTo({ url: '/pages/family/index' }) }
</script>

<template>
  <view class="page">
    <view class="hero"><view><text class="eyebrow">银龄智游</text><view class="title">慢慢说，我们一起看</view><view class="intro">旅游规划与防诈核对，都从这里开始。</view></view><view class="status" :class="{ online }"><view class="dot" />{{ online ? '服务在线' : '服务检查中' }}</view></view>
    <view class="service-card"><view class="service-title">选择服务</view><view class="topic-grid"><button v-for="item in topics" :key="item.id" class="topic-button" :class="{ selected: topic === item.id }" :disabled="busy" @click="selectTopic(item.id)"><text class="topic-label">{{ item.label }}</text><text class="topic-hint">{{ item.hint }}</text></button></view><view class="runtime-note">{{ statusText }}</view></view>
    <scroll-view class="conversation" scroll-y :scroll-top="scrollTop"><view v-for="message in messages" :key="message.id" class="message-row" :class="message.role"><view class="bubble" :class="{ pending: message.pending }"><text class="message-text">{{ message.text }}</text><text v-if="message.detail" class="message-detail">{{ message.detail }}</text></view></view></scroll-view>
    <view class="quick-title">您也可以这样问</view><scroll-view class="quick-list" scroll-x><button v-for="prompt in quickPrompts[topic]" :key="prompt" class="quick" @click="usePrompt(prompt)">{{ prompt }}</button></scroll-view>
    <view class="composer"><textarea v-model="input" class="input" :placeholder="`输入${current.label}问题…`" :disabled="busy" :maxlength="2000" auto-height/><button class="send" :disabled="busy || !input.trim()" @click="send">{{ busy ? '处理中' : '发送' }}</button></view>
    <view class="actions"><button class="secondary" @click="newConversation">新对话</button><button class="secondary" @click="openFamily">家属服务</button></view>
    <view class="safety">AI 回答供参考；涉及转账、验证码和身份信息时，请先联系家属或拨打 96110。</view>
  </view>
</template>

<style scoped>
.page{min-height:100vh;padding:36rpx 30rpx 48rpx;box-sizing:border-box;color:#193e31;background:linear-gradient(180deg,#eef6f0 0,#f8faf8 45%,#f4f8f5 100%)}
.hero{display:flex;justify-content:space-between;gap:24rpx;align-items:flex-start;margin-bottom:30rpx}.eyebrow{font-size:28rpx;font-weight:700;color:#4d8069;letter-spacing:4rpx}.title{font-size:48rpx;font-weight:750;margin:14rpx 0;line-height:1.3}.intro{font-size:29rpx;color:#638071;line-height:1.6}
.status{display:flex;flex-shrink:0;align-items:center;gap:10rpx;background:#fff;border-radius:999rpx;padding:14rpx 18rpx;color:#8b7961;font-size:24rpx;box-shadow:0 10rpx 30rpx rgba(35,74,55,.08)}.status.online{color:#26704e}.dot{width:14rpx;height:14rpx;border-radius:50%;background:#d7a85e}.online .dot{background:#3ca56c;box-shadow:0 0 0 8rpx rgba(60,165,108,.12)}
.service-card{background:rgba(255,255,255,.92);border:1rpx solid #dce9df;border-radius:28rpx;padding:26rpx;box-shadow:0 16rpx 50rpx rgba(31,78,54,.08)}.service-title,.quick-title{font-size:28rpx;font-weight:700;margin-bottom:18rpx}.topic-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14rpx}.topic-button{min-height:118rpx;margin:0;padding:20rpx 10rpx;display:flex;flex-direction:column;justify-content:center;background:#edf4ef;color:#335d49;border-radius:20rpx;line-height:1.35}.topic-button.selected{color:#fff;background:#2f7655;box-shadow:0 12rpx 28rpx rgba(47,118,85,.24)}.topic-label{font-size:29rpx;font-weight:700}.topic-hint{margin-top:8rpx;font-size:21rpx;opacity:.78}.runtime-note{margin-top:18rpx;font-size:23rpx;color:#819188;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.conversation{height:590rpx;margin:24rpx 0;padding:12rpx 4rpx;box-sizing:border-box}.message-row{display:flex;margin-bottom:22rpx}.message-row.user{justify-content:flex-end}.bubble{max-width:82%;padding:24rpx 26rpx;border-radius:8rpx 28rpx 28rpx 28rpx;background:#fff;box-shadow:0 10rpx 30rpx rgba(39,73,57,.08)}.user .bubble{color:#fff;background:#397a5c;border-radius:28rpx 8rpx 28rpx 28rpx}.bubble.pending{opacity:.72}.message-text{display:block;font-size:31rpx;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere}.message-detail{display:block;margin-top:14rpx;padding-top:12rpx;border-top:1rpx solid rgba(105,135,120,.2);color:#789084;font-size:23rpx;line-height:1.5}.user .message-detail{color:rgba(255,255,255,.75)}
.quick-list{white-space:nowrap;margin-bottom:20rpx}.quick{display:inline-block;width:auto;max-width:620rpx;min-height:68rpx;padding:12rpx 22rpx;margin:0 14rpx 0 0;border:1rpx solid #cfe0d5;border-radius:999rpx;background:#fff;color:#315d48;font-size:25rpx;line-height:1.5}.composer{display:flex;align-items:flex-end;gap:14rpx;padding:14rpx;background:#fff;border:1rpx solid #d7e4da;border-radius:26rpx;box-shadow:0 14rpx 40rpx rgba(31,74,53,.09)}.input{flex:1;min-height:68rpx;max-height:180rpx;padding:14rpx 12rpx;font-size:30rpx;line-height:1.5;box-sizing:border-box}.send{flex-shrink:0;width:128rpx;min-height:76rpx;margin:0;border-radius:20rpx;background:#2f7655;color:#fff;font-size:28rpx}.send[disabled]{background:#b9c9c0;color:#fff}.actions{display:grid;grid-template-columns:1fr 1fr;gap:18rpx;margin-top:20rpx}.secondary{min-height:76rpx;margin:0;border-radius:20rpx;background:#e3eee6;color:#315b48;font-size:27rpx}.safety{margin-top:24rpx;text-align:center;color:#87988f;font-size:22rpx;line-height:1.6}button::after{border:none}
@media screen and (min-width:768px){
  .page{width:480px;min-height:calc(100vh - 44px);margin:0 auto;padding:22px 20px 28px;border-left:1px solid #dce9df;border-right:1px solid #dce9df;box-shadow:0 0 50px rgba(27,65,47,.12)}
  .hero{gap:16px;margin-bottom:18px}.eyebrow{font-size:14px;letter-spacing:2px}.title{font-size:28px;margin:8px 0}.intro{font-size:15px}.status{gap:6px;padding:8px 10px;font-size:12px}.dot{width:8px;height:8px}
  .service-card{border-radius:18px;padding:16px}.service-title,.quick-title{font-size:15px;margin-bottom:10px}.topic-grid{gap:8px}.topic-button{min-height:72px;padding:10px 6px;border-radius:13px}.topic-label{font-size:15px}.topic-hint{margin-top:4px;font-size:11px}.runtime-note{margin-top:10px;font-size:12px}
  .conversation{height:360px;margin:14px 0;padding:8px 2px}.message-row{margin-bottom:12px}.bubble{padding:13px 15px;border-radius:5px 18px 18px 18px}.user .bubble{border-radius:18px 5px 18px 18px}.message-text{font-size:16px}.message-detail{margin-top:8px;padding-top:7px;font-size:12px}
  .quick-list{margin-bottom:12px}.quick{max-width:390px;min-height:38px;padding:7px 12px;margin-right:8px;font-size:13px}.composer{gap:8px;padding:8px;border-radius:16px}.input{min-height:42px;max-height:100px;padding:8px 7px;font-size:15px}.send{width:72px;min-height:44px;border-radius:12px;font-size:14px}.actions{gap:10px;margin-top:12px}.secondary{min-height:44px;border-radius:12px;font-size:14px}.safety{margin-top:14px;font-size:11px}
}
</style>
