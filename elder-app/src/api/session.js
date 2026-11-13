// 当前 mock 身份。后端只用身份头区分角色，userId 仍是业务归属参数，两者不能互换。
import {ACTORS} from './config.js'

const KEY = 'elder-actor'

export function actorKey() {
  const key = uni.getStorageSync(KEY)
  return ACTORS[key] ? key : 'elder'
}

export function actor() {
  return ACTORS[actorKey()]
}

export function setActor(key) {
  if (!ACTORS[key]) return false
  uni.setStorageSync(KEY, key)
  return true
}

export function actorList() {
  return Object.keys(ACTORS).map(key => ({key, ...ACTORS[key]}))
}

export function userId() {
  return actor().id
}

export function actorHeaders() {
  const current = actor()
  return {'X-Mock-Actor-Id': current.id, 'X-Mock-Actor-Role': current.role}
}
