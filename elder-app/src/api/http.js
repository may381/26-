// 统一请求：后端信封 {code,message,data}，成功 HTTP200；业务错误看 code 和 message。
import {API_BASE, REQUEST_TIMEOUT} from './config.js'
import {actorHeaders} from './session.js'

export class ApiError extends Error {
  constructor(message, {status = 0, code = '', path = ''} = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.path = path
  }
}

function buildQuery(params) {
  if (!params) return ''
  const pairs = []
  Object.keys(params).forEach(key => {
    const value = params[key]
    if (value === undefined || value === null || value === '') return
    pairs.push(encodeURIComponent(key) + '=' + encodeURIComponent(value))
  })
  return pairs.length ? '?' + pairs.join('&') : ''
}

// 后端部分操作要求 Idempotency-Key，同一 Key 24 小时内重放返回首次结果。
export function idempotencyKey(prefix = 'ui') {
  return prefix + '-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10)
}

export function request(path, options = {}) {
  const {method = 'GET', query, data, header = {}} = options
  const url = API_BASE + path + buildQuery(query)
  return new Promise((resolve, reject) => {
    uni.request({
      url,
      method,
      data,
      timeout: REQUEST_TIMEOUT,
      header: {'Content-Type': 'application/json', ...actorHeaders(), ...header},
      success(res) {
        const body = res.data
        const status = res.statusCode
        if (status >= 200 && status < 300 && body && body.code === 'OK') {
          resolve(body.data)
          return
        }
        const message =
          (body && body.message) || (status === 401 ? '身份无效，请检查 mock 身份头' : '请求未成功（HTTP ' + status + '）')
        reject(new ApiError(message, {status, code: (body && body.code) || '', path}))
      },
      fail(err) {
        const detail = (err && err.errMsg) || '网络错误'
        reject(new ApiError('连不上后端（' + detail + '），请确认 8080 已启动', {status: 0, path}))
      }
    })
  })
}

export const get = (path, query, header) => request(path, {method: 'GET', query, header})
export const post = (path, {query, data, header} = {}) => request(path, {method: 'POST', query, data, header})
export const patch = (path, {query, data, header} = {}) => request(path, {method: 'PATCH', query, data, header})
export const del = (path, {query, header} = {}) => request(path, {method: 'DELETE', query, header})
