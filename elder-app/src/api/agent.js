import {get,post,idempotencyKey} from './http.js'
import {userId} from './session.js'
export function submitAgentMessage(text,conversationId,pending){
 const q=pending?.inputRequest
 return post('/api/v3/agent/messages',{header:{'Idempotency-Key':idempotencyKey('agent')},data:{protocolVersion:'3.0',userId:userId(),...(conversationId?{conversationId}:{}),...(pending?{continueTaskId:pending.taskId}:{}),input:{text,attachmentIds:[],...(q?{responseTo:{ownerTaskId:q.ownerTaskId,inputRequestId:q.inputRequestId,version:q.version}}:{})},context:{businessRefs:[]}}})
}
export const getAgentTask=id=>get('/api/v3/agent/tasks/'+encodeURIComponent(id))
