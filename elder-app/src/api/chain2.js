// 链路二：求助 → 景区接单 → 家属关系 → 家属视图。全部在 /api/v3 下。
// 注意：家属相关接口对“老人 userId”操作，但身份头必须是 ELDER（老人自己）或 FAMILY（家属）。
import {get, post, patch} from './http.js'

/* ---------- 求助：老人发起，工作人员受理 ---------- */
// payload: {userId, tripId, type, location:{lat,lng}|{spotId}, locationNote}
export function createHelpEvent(payload) {
  return post('/api/v3/help-events', {query: {userId: payload.userId}, data: payload})
}

// 不传 userId 时，后端按当前身份返回可见范围（老人看自己的，工作人员看全部）。
export function listHelpEvents(userId) {
  return get('/api/v3/help-events', userId ? {userId} : {})
}

export function getHelpEvent(id, userId) {
  return get('/api/v3/help-events/' + id, {userId})
}

export function acknowledgeHelpEvent(id, userId) {
  return post('/api/v3/help-events/' + id + '/acknowledge', {query: {userId}})
}

export function resolveHelpEvent(id, userId) {
  return post('/api/v3/help-events/' + id + '/resolve', {query: {userId}})
}

/* ---------- 家属关系：老人侧 ---------- */
export function listFamilyRelations(userId) {
  return get('/api/v3/family-relations', {userId})
}

export function createFamilyRelation(userId, body) {
  return post('/api/v3/family-relations', {query: {userId}, data: body})
}

export function approveFamilyRelation(userId, id) {
  return post('/api/v3/family-relations/' + id + '/approve', {query: {userId}})
}

export function revokeFamilyRelation(userId, id) {
  return post('/api/v3/family-relations/' + id + '/revoke', {query: {userId}})
}

// 支持只传要改的项，例如 {shareProgress:true}
export function patchFamilyPermissions(userId, id, body) {
  return patch('/api/v3/family-relations/' + id + '/permissions', {query: {userId}, data: body})
}

// 本地 mock：把已生效的家属关系绑定到固定家属身份，例如 family-operator-001
export function bindFamilyMockAccount(userId, id, familyActorId) {
  return post('/api/v3/family-relations/' + id + '/mock-account', {query: {userId}, data: {familyActorId}})
}

/* ---------- 家属视图：家属侧（身份头需为 FAMILY） ---------- */
export function familyElderView(userId) {
  return get('/api/v3/family/elder', {userId})
}

export function familyNotifications(userId, limit = 20) {
  return get('/api/v3/notifications', {userId, limit})
}

export function familyMessages(userId, limit = 20) {
  return get('/api/v3/family/messages', {userId, limit})
}

export function sendFamilyMessage(userId, text) {
  return post('/api/v3/family/messages', {query: {userId}, data: {text}})
}

export function listRouteSuggestions(userId) {
  return get('/api/v3/family/route-suggestions', {userId})
}

export function suggestRoute(userId, body) {
  return post('/api/v3/family/route-suggestions', {query: {userId}, data: body})
}

// decision: ACCEPT / REJECT；老人采纳需要 remotePlanning 授权
export function decideRouteSuggestion(userId, id, body) {
  return post('/api/v3/family/route-suggestions/' + id + '/decision', {query: {userId}, data: body})
}

/* ---------- 适配：后端 DTO -> 页面现有形状 ---------- */

export const HELP_TYPE_LABEL = {SOS: '紧急求助', LOST: '迷路', UNWELL: '身体不适', GENERAL: '需要协助'}
export const HELP_STATUS_LABEL = {OPEN: '求助已发出', ACKNOWLEDGED: '工作人员已接单', RESOLVED: '已解决'}
export const NOTIFY_RECIPIENT = {FAMILY: '家属', SCENIC: '景区服务中心', OFFICIAL: '景区官方', ADMIN: '管理员'}
export const NOTIFY_STATUS = {PENDING: '待送达', SENT: '已发出', DELIVERED: '已送达', FAILED: '送达失败'}

function clock(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'})
}

// HelpModels.View -> 页面 help（OutingScreen / StaffScreen 共用）
export function adaptHelp(view, spotNames = {}) {
  if (!view) return null
  const location = view.location || {}
  const spotName = location.spotId ? spotNames[location.spotId] || location.spotId : ''
  const coord = location.lat != null && location.lng != null ? '坐标 ' + location.lat + ', ' + location.lng : ''
  // 后端返回的接收人/状态是小写（family、scenic、delivered…），这里统一归一化后再查中文表，
  // 避免页面上出现 "family: family: 已发出" 这种原始值。
  const recipientLabel = (type) => {
    const key = String(type || '').toUpperCase()
    return NOTIFY_RECIPIENT[key] || '通知方'
  }
  const statusLabel = (status) => {
    const key = String(status || '').toUpperCase()
    return NOTIFY_STATUS[key] || '状态更新'
  }
  const notifications = (view.notifications || []).map(n => ({
    to: recipientLabel(n.recipientType),
    status: statusLabel(n.status),
    body: statusLabel(n.status)
  }))
  const stages = [
    {label: '已发出', time: clock(view.createdAt), body: '求助信息已发到景区服务中心。'},
    {label: '已接单', time: view.businessStatus !== 'OPEN' ? clock(view.updatedAt) : '待更新', body: '工作人员受理后提供协助。'},
    {label: '处理中', time: '待更新', body: '工作人员在现场处理时会更新进度。'},
    {label: '已解决', time: view.businessStatus === 'RESOLVED' ? clock(view.updatedAt) : '待更新', body: '问题解决后状态会更新。'}
  ]
  const level = view.businessStatus === 'RESOLVED' ? 3 : view.businessStatus === 'ACKNOWLEDGED' ? 1 : 0
  const timeline = [{label: '已发出', time: view.createdAt, body: '求助信息已发到景区服务中心。'}]
  if (level >= 1) timeline.push({label: '已接单', time: view.updatedAt, body: '工作人员已受理，正在提供协助。'})
  if (level >= 3) timeline.push({label: '已解决', time: view.updatedAt, body: '本次求助已处理完成。'})
  return {
    id: view.id,
    backend: true,
    type: view.type,
    typeLabel: HELP_TYPE_LABEL[view.type] || view.type,
    status: view.businessStatus,
    statusLabel: HELP_STATUS_LABEL[view.businessStatus] || view.businessStatus,
    reason: view.locationNote || HELP_TYPE_LABEL[view.type] || '需要协助',
    location: spotName || view.locationNote || coord || '位置未提供',
    locationNote: view.locationNote || '',
    tripId: view.tripId,
    notifications,
    timeline,
    stages: stages.map((s, i) => ({...s, done: i <= level})),
    createdAt: view.createdAt,
    updatedAt: view.updatedAt,
    timeLabel: clock(view.createdAt)
  }
}

// FamilyModels.View -> 页面关系
export function adaptFamilyRelation(view) {
  if (!view) return null
  const p = view.permissions || {}
  return {
    id: view.id,
    backend: true,
    name: view.name,
    relation: view.relation,
    phone: view.phone,
    status: view.status,
    permissions: {
      position: !!p.shareLocation,
      progress: !!p.shareProgress,
      help: !!p.shareAlert,
      planning: !!p.remotePlanning
    }
  }
}

// FamilyReadService.ElderView -> 家属视图页
export function adaptElderView(view) {
  if (!view) return null
  return {
    backend: true,
    userId: view.userId,
    nickname: view.nickname,
    profileId: view.profileId,
    permissions: adaptFamilyRelation({permissions: view.permissions}).permissions,
    trip: view.trip
      ? {
          id: view.trip.id,
          routeId: view.trip.routeId,
          status: view.trip.status,
          startedAt: view.trip.startedAt,
          visitedCount: (view.trip.visitedSpotIds || []).length,
          nextSpotId: view.trip.nextSpotId,
          progressAvailable: !!view.trip.progressAvailable
        }
      : null,
    location: view.location || null,
    locationAvailable: !!view.locationAvailable,
    helpEvents: (view.helpEvents || []).map(h => ({
      id: h.id,
      type: h.type,
      typeLabel: HELP_TYPE_LABEL[h.type] || h.type,
      status: h.businessStatus,
      statusLabel: HELP_STATUS_LABEL[h.businessStatus] || h.businessStatus,
      timeLabel: clock(h.createdAt)
    })),
    notice: view.notice || ''
  }
}

export function adaptSuggestion(view, routeNames = {}) {
  if (!view) return null
  return {
    id: view.id,
    routeId: view.routeId,
    routeName: (view.route && view.route.name) || routeNames[view.routeId] || view.routeId,
    note: view.note || '',
    status: view.status,
    decisionNote: view.decisionNote || '',
    timeLabel: clock(view.createdAt)
  }
}

export function adaptMessage(view) {
  if (!view) return null
  return {
    id: view.id,
    text: view.text,
    senderRole: view.senderRole,
    fromFamily: view.senderRole === 'FAMILY',
    timeLabel: clock(view.createdAt),
    readAt: view.readAt
  }
}
