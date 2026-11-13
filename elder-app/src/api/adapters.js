// 把后端 DTO 转成页面正在使用的形状，页面模板尽量不改。
// 约定：后端只给 steps/slope/walkMin 等原始量，展示用的时长、台阶、休息点在这里聚合。

const STEPS_LIGHT = 20 // 合计台阶不超过这个数视为“少量台阶”，与后端“台阶最少”的推荐口径一致

function num(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function clockOf(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0')
}

function dateLabel(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('zh-CN')
}

// 由分段汇总：总时长、总台阶、最大坡度、休息点数。
function summarize(candidate) {
  const segments = Array.isArray(candidate.segments) ? candidate.segments : []
  const walkMin = segments.reduce((sum, s) => sum + num(s.walkMin), 0)
  const steps = segments.reduce((sum, s) => sum + num(s.steps), 0)
  const maxSlope = segments.reduce((max, s) => Math.max(max, num(s.slope)), 0)
  const rests = new Set()
  segments.forEach(s => (s.restFacilities || []).forEach(id => rests.add(id)))
  // 后端没有距离字段，用步行分钟数按 3km/h 估算，只作展示。
  const km = (walkMin * 0.05).toFixed(1)
  return {segments, walkMin, steps, maxSlope, rests: rests.size, km}
}

function stairsLabel(steps) {
  if (!steps) return '无台阶'
  return steps <= STEPS_LIGHT ? '少量台阶' : '有台阶'
}

function terrainLabel(maxSlope) {
  if (maxSlope <= 2) return '平缓为主'
  if (maxSlope <= 4) return '有缓坡'
  return '部分坡道'
}

// 后端候选路线 -> 页面 routes[i]（travel-data 的形状）
export function adaptRoute(candidate, index, spotsById = {}, facilities = []) {
  const info = summarize(candidate)
  const spotIds = candidate.spots || []
  const names = spotIds.map(id => (spotsById[id] && spotsById[id].name) || id)
  const stations = names.map((name, i) => {
    const segment = i === 0 ? null : info.segments[i - 1]
    const rest = segment && (segment.restFacilities || []).length > 0
    const spot = spotsById[spotIds[i]]
    return {
      id: i,
      spotId: spotIds[i],
      name,
      at: i === 0 ? 0 : info.segments.slice(0, i).reduce((sum, s) => sum + num(s.walkMin), 0),
      kind: i === 0 ? '出发' : rest ? '休息段' : '步行段',
      text: (spot && spot.description) || (i === names.length - 1 ? '返回入口，结束本次游览。' : '沿路线继续前行。')
    }
  })
  const toilets = facilities.filter(f => f.type === 'TOILET' && spotIds.includes(f.spotId)).length
  return {
    id: index,
    routeId: candidate.id,
    name: candidate.name,
    minutes: info.walkMin,
    km: info.km,
    terrain: terrainLabel(info.maxSlope),
    stairs: stairsLabel(info.steps),
    seats: info.rests,
    toilets,
    desc: candidate.reason || names.join(' → '),
    stops: names,
    notes: stations.map(s => s.text),
    stations,
    segments: info.segments,
    recommended: !!candidate.recommended,
    reason: candidate.reason || '',
    source: candidate.source,
    backend: true
  }
}

export function adaptRoutes(result, spotsById, facilities) {
  const list = (result && result.routes) || []
  return list.map((candidate, index) => adaptRoute(candidate, index, spotsById, facilities))
}

// 后端 ProfileView -> state.profile
export function adaptProfile(view) {
  if (!view) return null
  const contacts = Array.isArray(view.emergencyContacts) ? view.emergencyContacts : []
  const first = contacts[0] || {name: '', phone: '', relation: ''}
  return {
    id: view.id,
    version: view.version,
    nickname: view.nickname || '',
    age: view.age || 0,
    city: view.residence || '',
    language: view.language || '',
    emergencyContact: {name: first.name || '', phone: first.phone || '', relation: first.relation || ''},
    contacts,
    walkSpeed: view.walkSpeed || 'MEDIUM',
    walkDurationMin: view.walkDurationMin || 40,
    avoidSteps: view.avoidSteps !== false,
    interests: Array.isArray(view.interests) ? view.interests : [],
    interactionPreference: view.interactionPreference || 'VOICE',
    updatedAt: view.updatedAt || null,
    backend: true
  }
}

// 档案 -> state.preferences（页面里的步行习惯）
export function adaptPreferences(profile) {
  if (!profile) return null
  const pace = {SLOW: '慢慢走', MEDIUM: '正常速度', FAST: '走得快一点'}[profile.walkSpeed] || '正常速度'
  return {
    walkDuration: profile.walkDurationMin || 40,
    walkSpeed: profile.walkSpeed || 'MEDIUM',
    pace,
    stairs: profile.avoidSteps ? '少台阶' : '不限台阶',
    interests: profile.interests || [],
    avoid: [],
    updatedAt: profile.updatedAt ? new Date(profile.updatedAt).getTime() : Date.now(),
    backend: true
  }
}

// 页面上的步行习惯 -> PATCH /api/v3/profile 的字段（只带改动项）
export function profilePatch(body) {
  const payload = {}
  if (body.nickname !== undefined) payload.nickname = body.nickname
  if (body.age !== undefined) payload.age = Number(body.age)
  if (body.city !== undefined) payload.residence = body.city
  if (body.language !== undefined) payload.language = body.language
  if (body.walkSpeed !== undefined) payload.walkSpeed = body.walkSpeed
  if (body.walkDurationMin !== undefined) payload.walkDurationMin = Number(body.walkDurationMin)
  if (body.avoidSteps !== undefined) payload.avoidSteps = !!body.avoidSteps
  if (body.interests !== undefined) payload.interests = body.interests
  if (body.interactionPreference !== undefined) payload.interactionPreference = body.interactionPreference
  if (body.emergencyContacts !== undefined) payload.emergencyContacts = body.emergencyContacts
  return payload
}

// 后端 ProgressView -> 页面 tour（索引口径由调用方换算）
export function adaptProgress(progress) {
  if (!progress) return null
  return {
    progressSeq: num(progress.progressSeq),
    currentSpotId: progress.currentSpotId || null,
    visitedSpotIds: Array.isArray(progress.visitedSpotIds) ? progress.visitedSpotIds.slice() : [],
    nextSpotId: progress.nextSpotId || null,
    updatedAt: progress.updatedAt || null
  }
}

export function adaptActiveTrip(view) {
  if (!view) return null
  return {
    tripId: view.id || view.tripId,
    routeId: view.routeId,
    tripVersion: num(view.tripVersion),
    progressSeq: num(view.progressSeq),
    currentSpotId: view.currentSpotId || null,
    visitedSpotIds: Array.isArray(view.visitedSpotIds) ? view.visitedSpotIds.slice() : [],
    skippedSpotIds: Array.isArray(view.skippedSpotIds) ? view.skippedSpotIds.slice() : [],
    remainingSpotIds: Array.isArray(view.remainingSpotIds) ? view.remainingSpotIds.slice() : [],
    estimatedFinishAt: view.estimatedFinishAt === undefined ? undefined : view.estimatedFinishAt,
    activeRest: view.activeRest ?? null,
    startedAt: view.startedAt ?? Date.now()
  }
}

// 设施类型 -> 页面中文分类
export const FACILITY_CATEGORY = {TOILET: '厕所', BENCH: '休息点', EXIT: '出口', MEDICAL: '医务室', SERVICE_DESK: '服务台'}

export function adaptFacilityGroup(results) {
  const groups = {厕所: [], 休息点: [], 出口: [], 医务室: [], 服务台: []}
  ;(results || []).forEach(item => {
    const facility = item.facility || item
    const category = FACILITY_CATEGORY[facility.type] || '服务台'
    const meters = item.distanceMeters
    const distance = typeof meters === 'number' ? '约' + Math.round(meters) + '米 · 步行约' + Math.max(1, Math.round(meters / 60)) + '分钟' : '距离以现场标识为准'
    groups[category].push([facility.name, distance])
  })
  return groups
}

// 后端 RecordSummary -> 记录页条目
export function adaptRecordSummary(summary) {
  if (!summary) return null
  const minutes = Math.max(1, Math.round(num(summary.durationSeconds) / 60))
  return {
    id: summary.id,
    tripId: summary.tripId || summary.id,
    routeName: summary.routeName || '',
    routeLabel: summary.routeName || '',
    dateLabel: dateLabel(summary.startedAt),
    start: clockOf(summary.startedAt),
    end: clockOf(summary.finishedAt),
    minutes,
    km: (minutes * 0.05).toFixed(1),
    feedbackSubmitted: !!summary.feedbackSubmitted,
    startedAt: summary.startedAt,
    finishedAt: summary.finishedAt,
    backend: true
  }
}

// 后端 RecordDetail -> 游后页记录（route 用索引，调用方传入 routeIndex）
export function adaptRecordDetail(detail, spotsById, routeIndex) {
  if (!detail) return null
  const plan = detail.routeSnapshot
  const walkedMin = plan && Array.isArray(plan.segments) ? plan.segments.reduce((sum, s) => sum + num(s.walkMin), 0) : 0
  const visitedSpotIds = Array.isArray(detail.visitedSpotIds) ? detail.visitedSpotIds : []
  const plannedSpotIds = Array.isArray(detail.plannedSpotIds) ? detail.plannedSpotIds : []
  const indexOf = id => plannedSpotIds.indexOf(id)
  return {
    id: detail.id,
    tripId: detail.tripId || detail.id,
    route: typeof routeIndex === 'number' ? routeIndex : 0,
    routeName: detail.routeName || '',
    dateLabel: dateLabel(detail.startedAt),
    start: clockOf(detail.startedAt),
    end: clockOf(detail.finishedAt),
    minutes: Math.max(1, Math.round(num(detail.durationSeconds) / 60)),
    // 距离按路线计划步行分钟数换算，不能用“游览历时”，否则长时间挂起的记录会算出几百公里。
    km: (walkedMin * 0.05).toFixed(1),
    visited: visitedSpotIds.map(indexOf).filter(i => i >= 0),
    visitedNames: visitedSpotIds.map(id => (spotsById[id] && spotsById[id].name) || id),
    skipped: plannedSpotIds.filter(id => !visitedSpotIds.includes(id)).map(indexOf).filter(i => i >= 0),
    restInserted: 0,
    photos: (detail.media || []).map(m => m.id),
    mediaList: Array.isArray(detail.media) ? detail.media.map(m => ({...m, id: m.id, mimeType: m.mimeType, fileName: m.fileName, sizeBytes: m.sizeBytes, url: m.url, expiresAt: m.expiresAt})) : [],
    feedback: detail.feedback
      ? {effort: detail.feedback.effort, note: detail.feedback.note || '', comfortableWalkMin: detail.feedback.comfortableWalkMin}
      : null,
    preferenceUpdate: detail.preferenceUpdate || null,
    notice: detail.notice || '',
    startedAt: detail.startedAt,
    finishedAt: detail.finishedAt,
    backend: true
  }
}

export {dateLabel, clockOf}
