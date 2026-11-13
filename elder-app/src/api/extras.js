// 景点详情、景区景点/设施列表、长期偏好（记忆）的接口。都走 src/api/http.js 的统一封装。
import {get,del} from './http.js'
import {SCENIC_ID} from './config.js'
import {userId as currentUserId} from './session.js'

export function getSpotDetail(id,scenicId=SCENIC_ID){return get('/api/v3/spots/'+encodeURIComponent(id),{scenicId})}
export function listScenicSpots(scenicId=SCENIC_ID){return get('/api/v3/spots',{scenicId})}
export function listScenicFacilities(scenicId=SCENIC_ID){return get('/api/v3/facilities',{scenicId,limit:50})}
export function listMemories(userId=currentUserId()){return get('/api/v3/memories',{userId})}
export function deleteMemory(id,expectedVersion,userId=currentUserId()){return del('/api/v3/memories/'+encodeURIComponent(id),{query:{userId,expectedVersion}})}
