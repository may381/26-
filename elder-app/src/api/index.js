// 链路一（游览主线）接口封装。路径与后端 v3 文档一致，全部在 /api/v3 下。
import {get, post, patch, del, idempotencyKey, ApiError} from './http.js'
import {userId as currentUserId, actorHeaders} from './session.js'
import {SCENIC_ID, API_BASE, REQUEST_TIMEOUT} from './config.js'

// 分享落地页：公开接口，不带身份头（给没有 mock 身份的家人看）
export function getSharedRecord(shareId) {
  const path = '/api/v3/travel-record-shares/' + encodeURIComponent(shareId)
  return new Promise((resolve, reject) => {
    uni.request({
      url: API_BASE + path,
      method: 'GET',
      timeout: REQUEST_TIMEOUT,
      header: {'Content-Type': 'application/json'},
      success(res) {
        const body = res.data
        if (res.statusCode >= 200 && res.statusCode < 300 && body && body.code === 'OK') {
          resolve(body.data)
          return
        }
        const message = (body && body.message) || (res.statusCode === 404 ? '分享已失效或链接不完整' : '分享加载失败（HTTP ' + res.statusCode + '）')
        reject(new ApiError(message, {status: res.statusCode, code: (body && body.code) || '', path}))
      },
      fail(err) {
        reject(new ApiError('连不上后端（' + ((err && err.errMsg) || '网络错误') + '）', {path}))
      }
    })
  })
}
export function uploadTripAttachment(tripId, filePath) {
  const path = '/api/v3/trips/' + encodeURIComponent(tripId) + '/attachments'
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: API_BASE + path + '?userId=' + encodeURIComponent(currentUserId()),
      filePath, name: 'file', header: actorHeaders(), timeout: REQUEST_TIMEOUT,
      success(res) {
        let body
        try { body = typeof res.data === 'string' ? JSON.parse(res.data) : res.data } catch (_) {}
        if (res.statusCode >= 200 && res.statusCode < 300 && body?.code === 'OK') return resolve(body.data)
        reject(new ApiError(body?.message || '照片上传未成功（HTTP ' + res.statusCode + '）', {status: res.statusCode, code: body?.code || '', path}))
      },
      fail(err) { reject(new ApiError('连不上后端（' + (err?.errMsg || '网络错误') + '），请稍后重试', {path})) }
    })
  })
}

export function uploadTripAudioBlob(tripId, blob, fileName = 'voice.webm') {
  const path = '/api/v3/trips/' + encodeURIComponent(tripId) + '/attachments'
  return new Promise((resolve, reject) => {
    const fail = message => reject(new ApiError(message, {path}))
    try {
      if (blob.size > 10 * 1024 * 1024) return fail('录音超过 10MiB，请缩短后重试')
      const xhr = new XMLHttpRequest()
      const form = new FormData()
      form.append('file', blob, fileName)
      xhr.open('POST', API_BASE + path + '?userId=' + encodeURIComponent(currentUserId()))
      xhr.timeout = REQUEST_TIMEOUT
      Object.entries(actorHeaders()).forEach(([key, value]) => xhr.setRequestHeader(key, value))
      xhr.onload = () => {
        let body
        try { body = JSON.parse(xhr.responseText) } catch (_) {}
        if (xhr.status >= 200 && xhr.status < 300 && body?.code === 'OK') return resolve(body.data)
        reject(new ApiError(body?.message || '录音上传未成功（HTTP ' + xhr.status + '）', {status: xhr.status, code: body?.code || '', path}))
      }
      xhr.onerror = () => fail('连不上后端，请稍后重试')
      xhr.ontimeout = () => fail('录音上传超时，请稍后重试')
      xhr.onabort = () => fail('录音上传已取消')
      xhr.send(form)
    } catch (e) { fail(e?.message || '当前环境无法上传录音') }
  })
}

export function fetchTripMediaUrl(tripId, mediaId, mimeType = 'image/jpeg') {
  const path = '/api/v3/trips/' + encodeURIComponent(tripId) + '/attachments/' + encodeURIComponent(mediaId)
  return new Promise((resolve, reject) => {
    uni.request({
      url: API_BASE + path + '?userId=' + encodeURIComponent(currentUserId()),
      responseType: 'arraybuffer', header: actorHeaders(), timeout: REQUEST_TIMEOUT,
      success(res) {
        if (res.statusCode < 200 || res.statusCode >= 300) return reject(new ApiError(res.statusCode === 401 ? '身份无效，请检查 mock 身份头' : '照片加载未成功（HTTP ' + res.statusCode + '）', {status: res.statusCode, path}))
        try {
          const headers = res.header || {}
          const key = Object.keys(headers).find(k => k.toLowerCase() === 'content-type')
          resolve(URL.createObjectURL(new Blob([res.data], {type: headers[key] || mimeType})))
        } catch (_) { reject(new ApiError('当前环境无法显示照片，请在浏览器中查看', {path})) }
      },
      fail(err) { reject(new ApiError('照片加载失败（' + (err?.errMsg || '网络错误') + '）', {path})) }
    })
  })
}

/* ---------- 档案 ---------- */
export function getProfile(userId = currentUserId()) {
  return get('/api/v3/profile', {userId})
}

// version 传入 GET 返回的 version，后端可做旧页面冲突保护（409）。
export function patchProfile(payload, {userId = currentUserId(), version} = {}) {
  const header = version === undefined || version === null ? {} : {'X-Expected-Profile-Version': String(version)}
  return patch('/api/v3/profile', {query: {userId}, data: payload, header})
}

/* ---------- 景点 / 设施 ---------- */
export function listSpots(scenicId = SCENIC_ID) {
  return get('/api/v3/spots', {scenicId})
}

export function getSpot(id, scenicId = SCENIC_ID) {
  return get('/api/v3/spots/' + id, {scenicId})
}

export function synthesizeSpeech(text, speechRate = 1) {
  return post('/api/v3/speech/syntheses', {query: {userId: currentUserId()}, data: {text, speechRate}})
}

export function transcribeSpeechBlob(blob, fileName = 'voice.webm') {
  const path = '/api/v3/speech/transcriptions'
  return new Promise((resolve, reject) => {
    let xhr
    const fail = (message, code = '') => reject(new ApiError(message || '语音识别未成功', {status: xhr?.status || 0, code, path}))
    try {
      if (blob.size > 10 * 1024 * 1024) return fail('录音超过 10MiB，请缩短后重试', 'INVALID_ARGUMENT')
      xhr = new XMLHttpRequest()
      const form = new FormData()
      form.append('audio', blob, fileName)
      xhr.open('POST', API_BASE + path + '?userId=' + encodeURIComponent(currentUserId()))
      xhr.timeout = REQUEST_TIMEOUT
      Object.entries(actorHeaders()).forEach(([key, value]) => xhr.setRequestHeader(key, value))
      xhr.onload = () => {
        let body
        try { body = JSON.parse(xhr.responseText) } catch (_) {}
        if (xhr.status >= 200 && xhr.status < 300 && body?.code === 'OK') return resolve(body.data)
        fail(body?.message, body?.code || '')
      }
      xhr.onerror = () => fail('连不上后端，请用文字输入')
      xhr.ontimeout = () => fail('语音识别超时，请用文字输入')
      xhr.onabort = () => fail('语音识别已取消，请用文字输入')
      xhr.send(form)
    } catch (e) { fail(e?.message) }
  })
}

export function refreshSynthesis(audioId) {
  return get('/api/v3/speech/syntheses/' + encodeURIComponent(audioId), {userId: currentUserId()})
}

export function searchFacilities({type, lat, lng, limit = 20} = {}) {
  return get('/api/v3/facilities', {scenicId: SCENIC_ID, type, lat, lng, limit})
}

/* ---------- 路线 ---------- */
export function listRoutes({walkDurationMin, avoidSteps} = {}) {
  return get('/api/v3/routes', {userId: currentUserId(), walkDurationMin, avoidSteps})
}

export function getRouteMap(routeId) {
  return get('/api/v3/routes/' + routeId + '/map')
}

/* ---------- 游览 ---------- */
export function createTrip(routeId, userId = currentUserId()) {
  return post('/api/v3/trips', {query: {userId}, data: {routeId}})
}

export function getTrip(tripId, userId = currentUserId()) {
  return get('/api/v3/trips/' + tripId, {userId})
}

export function getActiveTrip(userId = currentUserId()) {
  return get('/api/v3/trips/active', {userId})
}

export function skipStop(tripId, spotId, expectedTripVersion) {
  return post('/api/v3/trips/' + encodeURIComponent(tripId) + '/stops/' + encodeURIComponent(spotId) + '/skip', {
    query: {userId: currentUserId()}, data: {expectedTripVersion},
    header: {'Idempotency-Key': idempotencyKey('skip')}
  })
}

export function createRest(tripId, {expectedTripVersion, plannedMinutes, facilityId, location}) {
  return post('/api/v3/trips/' + encodeURIComponent(tripId) + '/rests', {
    query: {userId: currentUserId()}, data: {expectedTripVersion, plannedMinutes, facilityId, location},
    header: {'Idempotency-Key': idempotencyKey('rest-create')}
  })
}

export function extendRest(tripId, restId, {expectedTripVersion, additionalMinutes}) {
  return patch('/api/v3/trips/' + encodeURIComponent(tripId) + '/rests/' + encodeURIComponent(restId), {
    query: {userId: currentUserId()}, data: {expectedTripVersion, additionalMinutes},
    header: {'Idempotency-Key': idempotencyKey('rest-extend')}
  })
}

export function finishRest(tripId, restId, {expectedTripVersion}) {
  return post('/api/v3/trips/' + encodeURIComponent(tripId) + '/rests/' + encodeURIComponent(restId) + '/finish', {
    query: {userId: currentUserId()}, data: {expectedTripVersion},
    header: {'Idempotency-Key': idempotencyKey('rest-finish')}
  })
}

export function listRests(tripId) {
  return get('/api/v3/trips/' + encodeURIComponent(tripId) + '/rests', {userId: currentUserId()})
}

export function finishTrip(tripId, userId = currentUserId()) {
  return post('/api/v3/trips/' + tripId + '/finish', {query: {userId}})
}

// 上报进度：progressSeq 必须递增，visitedSpotIds 是后端景点 ID 列表。
export function reportProgress(tripId, {progressSeq, lat, lng, currentSpotId, visitedSpotIds, nextSpotId, estimatedFinishAt}, userId = currentUserId()) {
  const data = {
    progressSeq,
    location: {lat, lng},
    currentSpotId,
    visitedSpotIds: visitedSpotIds || [],
    nextSpotId,
    estimatedFinishAt
  }
  return post('/api/v3/trips/' + tripId + '/progress', {query: {userId}, data})
}

export function getProgress(tripId, userId = currentUserId()) {
  return get('/api/v3/trips/' + tripId + '/progress', {userId})
}

// 调整剩余路线：需要 Idempotency-Key 和当前 progressSeq。
export function adjustTrip(tripId, {routeId, reason, expectedProgressSeq}, userId = currentUserId()) {
  return post('/api/v3/trips/' + tripId + '/adjustments', {
    query: {userId},
    data: {routeId, reason, expectedProgressSeq},
    header: {'Idempotency-Key': idempotencyKey('adjust')}
  })
}

export function listAdjustments(tripId, userId = currentUserId()) {
  return get('/api/v3/trips/' + tripId + '/adjustments', {userId})
}

/* ---------- 游后记录 ---------- */
export function listRecords({limit = 20, cursor} = {}, userId = currentUserId()) {
  return get('/api/v3/travel-records', {userId, limit, cursor})
}

// 记录 ID 即 Trip UUID。
export function getRecord(recordId, userId = currentUserId()) {
  return get('/api/v3/travel-records/' + recordId, {userId})
}

// effort: EASY / COMFORTABLE / TIRED
export function submitFeedback(tripId, {effort, comfortableWalkMin, note}, userId = currentUserId()) {
  return post('/api/v3/trips/' + tripId + '/feedback', {
    query: {userId},
    data: {effort, comfortableWalkMin, note},
    header: {'Idempotency-Key': idempotencyKey('feedback')}
  })
}

// decision: APPROVE / REJECT
export function decidePreference(recordId, decision, userId = currentUserId()) {
  return post('/api/v3/travel-records/' + recordId + '/preference-confirmation', {query: {userId}, data: {decision}})
}

export function createShare(recordId, payload, userId = currentUserId()) {
  return post('/api/v3/travel-records/' + recordId + '/share', {query: {userId}, data: payload})
}

export function revokeShare(recordId, shareId, userId = currentUserId()) {
  return del('/api/v3/travel-records/' + encodeURIComponent(recordId) + '/share/' + encodeURIComponent(shareId), {query: {userId}})
}
