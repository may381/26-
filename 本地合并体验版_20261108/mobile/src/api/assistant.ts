export type AssistantTopic = 'auto' | 'tourism' | 'fraud'

export interface AssistantReply {
  reply?: string
  domain?: string
  state?: string
  error?: string
  executionTrace?: Array<{ stage?: string; label?: string; status?: string; detail?: string }>
  domainResult?: unknown
  [key: string]: unknown
}

interface SystemStatus {
  mode?: string
  memory?: string
  checks?: Record<string, unknown>
}

const configuredBase = import.meta.env.VITE_A1_BASE_URL || 'http://127.0.0.1:8095'
const baseUrl = import.meta.env.DEV ? '/a1' : configuredBase

function request<T>(path: string, method: 'GET' | 'POST' = 'GET', data?: Record<string, unknown>): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${baseUrl}${path}`,
      method,
      data,
      timeout: 100000,
      success(response) {
        const body = response.data as T & { error?: string }
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(body)
        else reject(new Error(body?.error || `服务返回 ${response.statusCode}`))
      },
      fail(error) {
        reject(new Error(error.errMsg || '暂时无法连接智能服务'))
      },
    })
  })
}

export function sendAssistant(text: string, topic: AssistantTopic) {
  return request<AssistantReply>('/api/message', 'POST', { text, topic })
}

export function queryAssistantStatus() {
  return request<AssistantReply>('/api/status', 'POST', {})
}

export function resetAssistant() {
  return request<AssistantReply>('/api/reset', 'POST', {})
}

export function getAssistantSystemStatus() {
  return request<SystemStatus>('/api/system-status')
}
