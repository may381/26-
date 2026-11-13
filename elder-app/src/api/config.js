// 后端联调配置。H5 开发走 vite 代理（/api -> 127.0.0.1:8080），小程序/App 需要填完整地址。
const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}

export const API_BASE = env.VITE_API_BASE || ''

// 关闭后全部回到本地演示数据，不会发出任何请求。
export const USE_SERVER = String(env.VITE_USE_SERVER === undefined ? 'true' : env.VITE_USE_SERVER) !== 'false'

export const SCENIC_ID = env.VITE_SCENIC_ID || 'qingfeng'
export const REQUEST_TIMEOUT = 10000

// 身份头：本地演示用 mock 身份，不是真实登录。
export const ACTORS = {
  elder: {id: 'u100', role: 'ELDER', label: '老人 · 李阿姨'},
  elder2: {id: 'u101', role: 'ELDER', label: '老人 · 王阿姨'},
  family: {id: 'family-operator-001', role: 'FAMILY', label: '家属'},
  scenic: {id: 'scenic-operator-001', role: 'SCENIC', label: '景区工作人员'},
  official: {id: 'official-operator-001', role: 'OFFICIAL', label: '景区官方'},
  admin: {id: 'admin-operator-001', role: 'ADMIN', label: '管理员'}
}
