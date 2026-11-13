package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.common.idempotency.IdempotencyService;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import cn.silvertravel.platform.trip.TripProgressService;
import cn.silvertravel.platform.route.RouteCatalog;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.validation.Valid;
import jakarta.validation.Validator;
import jakarta.validation.constraints.*;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class AgentActionService {
    public static final String TOOL="trip.route.adjust";
    public record Args(@NotBlank String tripId,@NotBlank String routeId,@NotNull @Min(0) Long expectedProgressSeq,@NotNull @Min(0) Integer expectedRouteRevision,@Size(max=500) String reason) {}
    public record Step(@NotBlank String clientStepKey,@NotBlank String tool,@NotNull JsonNode args) {}
    public record Steps(@NotBlank String protocolVersion,@NotBlank String taskId,@NotBlank @Size(max=128) String requestKey,@Min(1) int planVersion,@NotNull @Size(min=1,max=1) List<@Valid Step> steps) {}
    public record ActionInput(@NotBlank String tool,@NotNull JsonNode args) {}
    public record Prepare(@NotBlank String protocolVersion,@NotBlank String taskId,@NotBlank String stepId,@NotNull @Valid ActionInput input) {}
    public record Confirm(@NotBlank String protocolVersion,@NotBlank String taskId,@NotBlank String actionId) {}
    public enum Decision { APPROVE,REJECT,CANCEL }
    public record Decide(@NotBlank String protocolVersion,@NotNull Decision decision,@Min(1) long expectedVersion) {}
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    private final BusinessAccessPolicy access;
    private final IdempotencyService keys;
    private final TripProgressService progress;
    private final RouteCatalog routes;
    private final Validator validator;
    private final AgentMemoryService memory;private final AgentInvocationAccess invocationAccess;private final AgentBusinessToolService business;private final AgentAttachmentService attachments;
    public AgentActionService(JdbcTemplate jdbc,ObjectMapper json,BusinessAccessPolicy access,IdempotencyService keys,TripProgressService progress,RouteCatalog routes,Validator validator,AgentMemoryService memory,AgentInvocationAccess invocationAccess,AgentBusinessToolService business,AgentAttachmentService attachments){this.jdbc=jdbc;this.json=json;this.access=access;this.keys=keys;this.progress=progress;this.routes=routes;this.validator=validator;this.memory=memory;this.invocationAccess=invocationAccess;this.business=business;this.attachments=attachments;}
    private void version(String version){if(!"3.0".equals(version))throw BusinessException.invalid("protocolVersion必须为3.0");}
    private Map<String,Object> task(String id){var rows=jdbc.queryForList("SELECT * FROM agent_task WHERE id=? FOR UPDATE",id);if(rows.isEmpty())throw BusinessException.notFound("任务不存在");return rows.getFirst();}
    Map<String,Object> authorize(String caller,String token,String taskId){return invocationAccess.require(caller,token,taskId);}
    private void allowed(String caller,String tool){if(business.supports(tool)){business.allow(caller,tool);return;}if(tool.startsWith("memory.")){memory.allow(caller,tool);return;}if(!"a1".equals(caller))throw new AccessDeniedException("该业务工具仅允许A1");}
    private Args args(JsonNode input){try{Args a=json.treeToValue(input,Args.class);if(!validator.validate(a).isEmpty())throw new IllegalArgumentException();return a;}catch(Exception e){throw BusinessException.invalid("改线参数无效");}}
    private JsonNode normalize(String tool,JsonNode input){
        if(business.supports(tool))return read(encode(business.normalize(tool,input)));
        if(tool.startsWith("memory."))return read(encode(memory.normalize(tool,input)));
        if(TOOL.equals(tool))return read(encode(args(input)));
        if("agent.delegate".equals(tool)){try{var i=json.treeToValue(input,AgentDelegationService.Input.class);if(!validator.validate(i).isEmpty())throw new IllegalArgumentException();AgentDelegationService.validateDomain(i);return read(encode(i));}catch(Exception e){throw BusinessException.invalid("委派参数无效");}}
        throw new AccessDeniedException("工具未开放");
    }
    private void checkBusiness(String user,Args a){
        var trip=jdbc.queryForList("SELECT scenic_id FROM trip WHERE id=? AND user_id=? AND status='ACTIVE' FOR UPDATE",a.tripId(),user);
        if(trip.isEmpty())throw BusinessException.conflict("游览不存在或已结束");
        if(!routes.require(a.routeId()).dataset().scenic().id().equals(trip.getFirst().get("scenic_id")))throw BusinessException.invalid("路线必须属于当前景区");
        Long seq=jdbc.queryForObject("SELECT COALESCE(MAX(progress_seq),0) FROM trip_progress WHERE trip_id=? AND user_id=?",Long.class,a.tripId(),user);
        Integer revision=jdbc.queryForObject("SELECT COALESCE(MAX(revision),0) FROM trip_route_adjustment WHERE trip_id=? AND user_id=?",Integer.class,a.tripId(),user);
        if(!Objects.equals(seq,a.expectedProgressSeq())||!Objects.equals(revision,a.expectedRouteRevision()))throw BusinessException.conflict("游览进度或路线版本已变化，请重新准备确认");
    }
    @Transactional
    public JsonNode steps(String caller,String token,Steps r){
        version(r.protocolVersion());var t=authorize(caller,token,r.taskId());
        if(r.planVersion()!=1)throw BusinessException.invalid("本批只开放planVersion=1，每次调用登记一个步骤");
        Step step=r.steps().getFirst();allowed(caller,step.tool());JsonNode normalized=normalize(step.tool(),step.args());
        var existing=jdbc.queryForList("SELECT * FROM agent_plan_step WHERE task_id=? AND request_key=?",r.taskId(),r.requestKey());
        if(!existing.isEmpty()){var saved=existing.getFirst();if(!read(saved.get("request_json")).equals(read(encode(r))))throw BusinessException.conflict("登记Key与原步骤内容不符");return stepView(saved);}
        if(jdbc.queryForObject("SELECT COUNT(*) FROM agent_plan_step WHERE task_id=?",Integer.class,r.taskId())>=40)throw BusinessException.conflict("单任务最多登记40个步骤");
        if(TOOL.equals(step.tool()))checkBusiness(t.get("user_id").toString(),args(normalized));
        if("memory.change".equals(step.tool()))memory.changeContent(t.get("user_id").toString(),r.taskId(),json.convertValue(normalized,AgentMemoryService.Change.class));String id=UUID.randomUUID().toString(),key=UUID.randomUUID().toString();
        jdbc.update("INSERT INTO agent_plan_step VALUES (?,?,?,?,?,?,?)",id,r.taskId(),r.requestKey(),encode(r),key,step.tool(),encode(normalized));
        return stepView(jdbc.queryForMap("SELECT * FROM agent_plan_step WHERE id=?",id));
    }
    private JsonNode stepView(Map<String,Object> row){ObjectNode out=json.createObjectNode();out.put("taskId",row.get("task_id").toString()).put("planVersion",1);out.putArray("steps").addObject().put("stepId",row.get("id").toString()).put("prepareKey",row.get("prepare_key").toString()).put("clientStepKey",read(row.get("request_json")).path("steps").get(0).path("clientStepKey").asText()).put("state","PLANNED");return out;}
    @Transactional
    public JsonNode prepare(String caller,String token,Prepare r,String key){
        version(r.protocolVersion());authorize(caller,token,r.taskId());
        var rows=jdbc.queryForList("SELECT * FROM agent_plan_step WHERE id=? AND task_id=?",r.stepId(),r.taskId());if(rows.isEmpty())throw BusinessException.notFound("步骤不存在");var step=rows.getFirst();allowed(caller,step.get("tool").toString());
        if(!Objects.equals(key,step.get("prepare_key")))throw BusinessException.conflict("必须使用已登记的prepareKey");
        if(!step.get("tool").equals(r.input().tool())||!read(step.get("args")).equals(normalize(r.input().tool(),r.input().args())))throw BusinessException.conflict("操作参数不能改变已登记步骤");
        var saved=jdbc.queryForList("SELECT id FROM agent_action WHERE step_id=?",r.stepId());String id;
        if(!saved.isEmpty())id=saved.getFirst().get("id").toString();else{id=UUID.randomUUID().toString();jdbc.update("INSERT INTO agent_action(id,task_id,step_id,tool,args,execution_status,created_at) VALUES (?,?,?,?,?,'NOT_STARTED',?)",id,r.taskId(),r.stepId(),r.input().tool(),step.get("args").toString(),Timestamp.from(Instant.now()));}
        ObjectNode out=json.createObjectNode();out.put("taskId",r.taskId()).put("stepId",r.stepId()).put("actionId",id).put("requiresConfirmation",TOOL.equals(r.input().tool())||"memory.change".equals(r.input().tool())).put("state","PREPARED");return out;
    }
    @Transactional
    public JsonNode confirm(String caller,String token,Confirm r){
        version(r.protocolVersion());authorize(caller,token,r.taskId());if(!"a1".equals(caller))throw new AccessDeniedException("仅A1准备记忆或改线确认");
        var action=jdbc.queryForList("SELECT * FROM agent_action WHERE id=? AND task_id=?",r.actionId(),r.taskId());if(action.isEmpty())throw BusinessException.notFound("动作不存在");if(!TOOL.equals(action.getFirst().get("tool"))&&!"memory.change".equals(action.getFirst().get("tool")))throw BusinessException.invalid("该工具不使用用户确认入口");
        var saved=jdbc.queryForList("SELECT id FROM agent_confirmation WHERE action_id=?",r.actionId());String id;
        if(saved.isEmpty()){if(jdbc.queryForObject("SELECT COUNT(*) FROM agent_confirmation WHERE task_id=? AND state='PENDING'",Integer.class,r.taskId())>=20)throw BusinessException.conflict("单任务最多20项待确认操作");id=UUID.randomUUID().toString();Instant now=Instant.now();jdbc.update("INSERT INTO agent_confirmation(id,action_id,task_id,state,version,expires_at,created_at) VALUES (?,?,?,'PENDING',1,?,?)",id,r.actionId(),r.taskId(),Timestamp.from(now.plusSeconds(600)),Timestamp.from(now));if("memory.change".equals(action.getFirst().get("tool"))){String user=task(r.taskId()).get("user_id").toString();JsonNode content=memory.changeContent(user,r.taskId(),json.convertValue(read(action.getFirst().get("args")),AgentMemoryService.Change.class));jdbc.update("UPDATE agent_confirmation SET summary=? WHERE id=?","长期保存偏好："+content.path("content").asText()+"；适用领域："+content.path("domains").toString(),id);}}else id=saved.getFirst().get("id").toString();
        return view(id);
    }
    @Transactional(readOnly=true)
    public JsonNode get(String id){JsonNode out=view(id);var rows=jdbc.queryForList("SELECT user_id FROM agent_task WHERE id=?",out.path("ownerTaskId").asText());access.requireElderOwner(rows.getFirst().get("user_id").toString());return out;}
    private ObjectNode view(String id){
        var rows=jdbc.queryForList("SELECT c.*,a.tool,a.args,a.execution_status,a.result FROM agent_confirmation c JOIN agent_action a ON a.id=c.action_id WHERE c.id=?",id);if(rows.isEmpty())throw BusinessException.notFound("确认不存在");var row=rows.getFirst();ObjectNode out=json.createObjectNode();
        out.put("confirmationId",id).put("ownerTaskId",row.get("task_id").toString()).put("rootTaskId",row.get("task_id").toString()).put("actionId",row.get("action_id").toString()).put("state",row.get("state").toString()).put("version",((Number)row.get("version")).longValue()).put("actionStatus",row.get("execution_status").toString()).put("tool",row.get("tool").toString()).put("expiresAt",((Timestamp)row.get("expires_at")).toInstant().toString()).put("canRetry",false).putNull("lastError");if(row.get("summary")!=null)out.put("summary",row.get("summary").toString());out.set("args",read(row.get("args")));out.set("result",row.get("result")==null?json.nullNode():any(row.get("result")));return out;
    }
    @Transactional
    public JsonNode decide(String id,Decide r,String key){
        version(r.protocolVersion());if(key==null)throw BusinessException.invalid("必须提供Idempotency-Key");var actor=access.currentActor();
        return keys.execute(actor,"agent.confirmation.decision",key,Map.of("id",id,"request",r),JsonNode.class,n->id,()->{
            var ids=jdbc.queryForList("SELECT task_id FROM agent_confirmation WHERE id=?",String.class,id);if(ids.isEmpty())throw BusinessException.notFound("确认不存在");var t=task(ids.getFirst());access.requireElderOwner(t.get("user_id").toString());
            var row=jdbc.queryForMap("SELECT * FROM agent_confirmation WHERE id=? FOR UPDATE",id);ObjectNode v=view(id);
            String target=switch(r.decision()){case APPROVE->"EXECUTED";case REJECT->"REJECTED";case CANCEL->"CANCELLED";};
            if(!"PENDING".equals(row.get("state"))) {if(target.equals(row.get("state")))return v;throw BusinessException.conflict("确认已处理");}
            if(((Number)row.get("version")).longValue()!=r.expectedVersion())throw BusinessException.conflict("确认版本已变化");
            if(r.decision()==Decision.APPROVE){memory.assertTaskCurrent(ids.getFirst(),t.get("user_id").toString());attachments.assertFresh(ids.getFirst());}
            ObjectNode snapshot=read(t.get("snapshot"));
            if(!"WAITING_CONFIRMATION".equals(t.get("state"))||!((Timestamp)row.get("expires_at")).toInstant().isAfter(Instant.now())||!Instant.parse(snapshot.path("expiresAt").asText()).isAfter(Instant.now()))throw BusinessException.conflict("任务状态或确认有效期已变化");
            ObjectNode actionResult=json.createObjectNode();
            if(r.decision()==Decision.APPROVE){
                if("memory.change".equals(v.path("tool").asText()))actionResult=(ObjectNode)memory.apply(t.get("user_id").toString(),ids.getFirst(),json.convertValue(v.path("args"),AgentMemoryService.Change.class));
                else {Args a=args(v.path("args"));checkBusiness(t.get("user_id").toString(),a);var result=progress.adjust(t.get("user_id").toString(),a.tripId(),new TripProgressService.AdjustmentRequest(a.routeId(),a.reason(),a.expectedProgressSeq()),"action-"+v.path("actionId").asText());actionResult=json.valueToTree(result);}
                jdbc.update("UPDATE agent_action SET execution_status='SUCCEEDED',result=? WHERE id=?",encode(actionResult),v.path("actionId").asText());
            }
            jdbc.update("UPDATE agent_confirmation SET state=?,version=version+1,decided_at=? WHERE id=?",target,Timestamp.from(Instant.now()),id);
            var remaining=jdbc.queryForList("SELECT id FROM agent_confirmation WHERE task_id=? AND state='PENDING' ORDER BY created_at,id",String.class,ids.getFirst());String nextState=remaining.isEmpty()?"QUEUED":"WAITING_CONFIRMATION";
            snapshot.put("status",nextState).put("phase","CONFIRMATION_DECIDED").put("resumeReason","CONFIRMATION_DECIDED").put("version",((Number)t.get("version")).longValue()+1).put("updatedAt",Instant.now().toString());var pendingIds=snapshot.putArray("confirmationIds");remaining.forEach(pendingIds::add);
            if(r.decision()==Decision.APPROVE){ObjectNode effect=snapshot.withArray("effects").addObject();effect.put("effectId",v.path("actionId").asText()).put("actionId",v.path("actionId").asText()).put("tool",v.path("tool").asText()).put("executionStatus","SUCCEEDED").put("externalStatus","NOT_APPLICABLE").put("createdAt",Instant.now().toString());effect.putObject("businessRef").put("type","memory.change".equals(v.path("tool").asText())?"memory":"tripAdjustment").put("id",actionResult.path("memoryId").asText(actionResult.path("id").asText()));}
            jdbc.update("UPDATE agent_task SET state=?,version=version+1,snapshot=?,updated_at=? WHERE id=?",nextState,encode(snapshot),Timestamp.from(Instant.now()),ids.getFirst());return view(id);
        });
    }
    public List<JsonNode> pending(String task){return jdbc.queryForList("SELECT id FROM agent_confirmation WHERE task_id=? AND state='PENDING'",String.class,task).stream().map(this::view).map(n->(JsonNode)n).toList();}
    public List<JsonNode> decisions(String task){return jdbc.queryForList("SELECT id FROM agent_confirmation WHERE task_id=? AND state<>'PENDING' ORDER BY created_at,id",String.class,task).stream().map(this::view).map(n->(JsonNode)n).toList();}
    public JsonNode publicView(JsonNode detail){
        ObjectNode out=((ObjectNode)detail).deepCopy();JsonNode a=out.path("args");
        out.put("operation",out.path("tool").asText()).put("summary","将游览 "+a.path("tripId").asText()+" 的剩余路线调整为 "+a.path("routeId").asText()+"；基于进度序号 "+a.path("expectedProgressSeq").asLong()+"、路线版本 "+a.path("expectedRouteRevision").asInt()+"；原因："+a.path("reason").asText("未填写"));
        if("memory.change".equals(detail.path("tool").asText()))out.put("summary",memory.deletedCandidate(a.path("candidateId").asText())?"该记忆已删除，原确认内容不再展示":detail.path("summary").asText("长期偏好保存确认"));out.remove(List.of("args","tool","result"));return out;
    }
    @org.springframework.scheduling.annotation.Scheduled(fixedDelay=10000)
    @Transactional
    public void expire(){
        for(var row:jdbc.queryForList("SELECT id,task_id FROM agent_confirmation WHERE state='PENDING' AND expires_at<? LIMIT 100",Timestamp.from(Instant.now()))){
            var t=task(row.get("task_id").toString());
            int changed=jdbc.update("UPDATE agent_confirmation SET state='EXPIRED',version=version+1 WHERE id=? AND state='PENDING' AND expires_at<?",row.get("id"),Timestamp.from(Instant.now()));
            if(changed==1 && "WAITING_CONFIRMATION".equals(t.get("state"))){ObjectNode s=read(t.get("snapshot"));s.put("status","FAILED").put("phase","CONFIRMATION_EXPIRED").put("version",((Number)t.get("version")).longValue()+1).put("updatedAt",Instant.now().toString());s.putArray("confirmationIds");s.putObject("error").put("code","CONFIRMATION_EXPIRED").put("message","确认已过期，请重新提出需求").put("retryable",false);jdbc.update("UPDATE agent_task SET state='FAILED',version=version+1,snapshot=?,updated_at=? WHERE id=?",encode(s),Timestamp.from(Instant.now()),row.get("task_id"));}
        }
    }
    public List<JsonNode> ledger(String task){return jdbc.query("SELECT id,tool,execution_status,result FROM agent_action WHERE task_id=? ORDER BY created_at,id",(rs,n)->{ObjectNode out=json.createObjectNode();out.put("actionId",rs.getString("id")).put("tool",rs.getString("tool")).put("executionStatus",rs.getString("execution_status"));out.set("result",rs.getString("result")==null?json.nullNode():any(rs.getString("result")));return (JsonNode)out;},task);}
    @Transactional
    public JsonNode queryAction(String caller,String token,String id){
        var rows=jdbc.queryForList("SELECT * FROM agent_action WHERE id=?",id);if(rows.isEmpty())throw BusinessException.notFound("动作不存在");var row=rows.getFirst();var t=authorize(caller,token,row.get("task_id").toString());allowed(caller,row.get("tool").toString());
        if(memory.stale(row.get("task_id").toString(),t.get("user_id").toString()))throw BusinessException.conflict("读取依赖已失效，原结果不再提供");
        ObjectNode out=json.createObjectNode();out.put("actionId",id).put("stepId",row.get("step_id").toString()).put("tool",row.get("tool").toString()).put("executionStatus",row.get("execution_status").toString());out.set("result",row.get("result")==null?json.nullNode():any(row.get("result")));return out;
    }
    @Transactional
    public JsonNode querySteps(String caller,String token,String task){authorize(caller,token,task);ObjectNode out=json.createObjectNode();out.put("taskId",task).put("planVersion",1);out.set("planSteps",json.valueToTree(contextSteps(task)));return out;}
    public List<JsonNode> contextSteps(String task){return jdbc.query("SELECT id,prepare_key,tool FROM agent_plan_step WHERE task_id=? ORDER BY id",(rs,n)->(JsonNode)json.createObjectNode().put("stepId",rs.getString("id")).put("prepareKey",rs.getString("prepare_key")).put("tool",rs.getString("tool")),task);}
    public void verifyTools(String task,JsonNode reported){
        if(!reported.isArray()||reported.size()>40)throw BusinessException.invalid("工具记录格式无效");
        for(JsonNode call:reported){boolean found=false;for(var row:jdbc.queryForList("SELECT args,result FROM agent_action WHERE task_id=? AND tool=? AND execution_status='SUCCEEDED'",task,call.path("tool").asText()))if(row.get("result")!=null&&read(row.get("args")).equals(read(encode(call.path("args"))))&&any(row.get("result")).equals(any(encode(call.path("result")))))found=true;if(!found)throw BusinessException.conflict("工具记录与实际执行不符");}
    }
    private JsonNode any(Object o){try{return json.readTree(o.toString());}catch(Exception e){throw new IllegalStateException(e);}}
    private ObjectNode read(Object o){try{return (ObjectNode)json.readTree(o.toString());}catch(Exception e){throw new IllegalStateException(e);}}
    private String encode(Object o){try{return json.writeValueAsString(o);}catch(Exception e){throw new IllegalStateException(e);}}
}
