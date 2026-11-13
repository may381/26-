package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.common.idempotency.IdempotencyService;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Durable acceptance boundary. Execution is intentionally separate from HTTP acceptance. */
@Service
@Profile("!bootstrap")
@org.springframework.scheduling.annotation.EnableScheduling
public class AgentTaskService {
    public record Input(@Size(max=2000) String text, @Size(max=4) List<String> attachmentIds, JsonNode responseTo) {}
    public record Context(List<JsonNode> businessRefs) {}
    public record Request(@NotBlank String protocolVersion, @NotBlank @Size(max=128) String userId,
            String conversationId, String continueTaskId, @NotNull @Valid Input input,
            @Valid Context context, String relatedTaskId) {}
    public record Accepted(String conversationId, String messageId, String taskId,
            long taskVersion, String taskStatus, JsonNode reply, List<JsonNode> results,
            List<String> confirmationIds) {}
    public record Cancel(@Min(1) long expectedVersion, @Size(max=500) String reason) {}
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    private final BusinessAccessPolicy access;
    private final IdempotencyService keys;
    private final AgentProperties properties;
    private final AgentDelegationService delegations;
    private final AgentInputService inputs;
    private final AgentMemoryService memory;private final AgentAttachmentService attachments;
    public AgentTaskService(JdbcTemplate jdbc,ObjectMapper json,BusinessAccessPolicy access,IdempotencyService keys,AgentProperties properties,AgentDelegationService delegations,AgentInputService inputs,AgentMemoryService memory,AgentAttachmentService attachments) {
        this.jdbc=jdbc;this.json=json;this.access=access;this.keys=keys;
        this.properties=properties;
        this.delegations=delegations;this.inputs=inputs;this.memory=memory;this.attachments=attachments;
    }
    @Transactional
    public Accepted accept(Request request,String key) {
        var actor=access.requireElderOwner(request.userId());
        if(!"3.0".equals(request.protocolVersion())) throw BusinessException.invalid("protocolVersion 必须为3.0");
        if(key==null) throw BusinessException.invalid("必须提供 Idempotency-Key");
        if((request.input().text()==null||request.input().text().isBlank())&&(request.input().attachmentIds()==null||request.input().attachmentIds().isEmpty()))throw BusinessException.invalid("文本和图片至少提供一项");
        if(request.input().text()!=null&&!request.input().text().isBlank()&&!AgentTextSafety.valid(request.input().text()))throw BusinessException.invalid("文本无效");
        if(request.continueTaskId()==null && request.input().responseTo()!=null)
            throw BusinessException.invalid("回答问题必须指定 continueTaskId");
        if(request.context()!=null && request.context().businessRefs()!=null && !request.context().businessRefs().isEmpty())
            throw BusinessException.invalid("业务引用授权解析尚未开放");
        return keys.execute(actor,"agent.message.accept",key,request,Accepted.class,Accepted::taskId,()->request.continueTaskId()==null?create(request):resume(request));
    }
    private Accepted resume(Request r) {
        var roots=jdbc.queryForList("SELECT snapshot,version FROM agent_task WHERE id=? AND user_id=? FOR UPDATE",r.continueTaskId(),r.userId());
        if(roots.isEmpty())throw BusinessException.notFound("任务不存在");
        if(memory.stale(r.continueTaskId(),r.userId()))throw BusinessException.conflict("依赖的记忆已失效，请新建任务");
        ObjectNode root;try{root=(ObjectNode)json.readTree(roots.getFirst().get("snapshot").toString());}catch(Exception e){throw new IllegalStateException(e);}
        JsonNode answer=r.input().responseTo();
        if(answer!=null){if(!answer.isObject()||!answer.path("ownerTaskId").isTextual()||!answer.path("inputRequestId").isTextual()||!answer.path("version").isIntegralNumber())throw BusinessException.invalid("问题引用字段类型无效");answer.fieldNames().forEachRemaining(k->{if(!Set.of("ownerTaskId","inputRequestId","version","selectedOptionId").contains(k))throw BusinessException.invalid("未知问题引用字段");});}
        if(!root.path("parentTaskId").isNull()||!root.path("conversationId").asText().equals(r.conversationId())||!List.of("WAITING_INPUT","WAITING_DEPENDENCIES").contains(root.path("status").asText())||answer==null)throw BusinessException.conflict("请通过当前根任务回答有效问题");
        var questions=jdbc.queryForList("SELECT * FROM agent_input_request WHERE id=? AND root_task_id=? FOR UPDATE",answer.path("inputRequestId").asText(),r.continueTaskId());
        if(questions.isEmpty())throw BusinessException.conflict("问题不存在或不属于当前任务");var q=questions.getFirst();
        String owner=q.get("owner_task_id").toString();
        if(!owner.equals(r.continueTaskId())&&r.input().attachmentIds()!=null&&!r.input().attachmentIds().isEmpty())throw BusinessException.invalid("子问题回答本批只支持文本");
        if(!"PENDING".equals(q.get("state"))||!owner.equals(answer.path("ownerTaskId").asText())||((Number)q.get("version")).longValue()!=answer.path("version").asLong(-1))throw BusinessException.conflict("问题已回答、失效或版本不符");
        if(!Instant.parse(root.path("expiresAt").asText()).isAfter(Instant.now()))throw BusinessException.conflict("任务已过期");
        ObjectNode question;try{question=(ObjectNode)json.readTree(q.get("question_json").toString());}catch(Exception e){throw new IllegalStateException(e);}
        if(answer.hasNonNull("selectedOptionId")){boolean found=false;for(JsonNode option:question.path("options"))if(option.path("id").asText().equals(answer.path("selectedOptionId").asText()))found=true;if(!found)throw BusinessException.invalid("选项不存在");}
        else if(!question.path("allowFreeText").asBoolean())throw BusinessException.invalid("请选择问题选项");
        var owners=jdbc.queryForList("SELECT snapshot FROM agent_task WHERE id=? AND user_id=? AND state='WAITING_INPUT' FOR UPDATE",owner,r.userId());if(owners.isEmpty())throw BusinessException.conflict("原问题所属任务已变化");
        ObjectNode s;try{s=(ObjectNode)json.readTree(owners.getFirst().get("snapshot").toString());}catch(Exception e){throw new IllegalStateException(e);}
        String message=UUID.randomUUID().toString();long ownerVersion=s.path("version").asLong()+1;
        s.put("sourceMessageId",message).put("status","QUEUED").put("phase","INPUT_PROVIDED").put("resumeReason","INPUT_PROVIDED").put("version",ownerVersion).put("updatedAt",Instant.now().toString()).putNull("inputRequest").putNull("reply");s.putArray("pendingInputRequests");
        question.put("ownerTaskId",owner).put("version",((Number)q.get("version")).intValue());ObjectNode response=s.putObject("inputResponse");response.set("question",question);response.put("text",r.input().text());response.set("responseTo",answer);
        jdbc.update("UPDATE agent_task SET state='QUEUED',version=version+1,snapshot=?,request_json=?,updated_at=? WHERE id=?",encode(s),encode(r),Timestamp.from(Instant.now()),owner);
        jdbc.update("UPDATE agent_input_request SET state='ANSWERED',answer_json=? WHERE id=?",encode(response),q.get("id"));
        long rootVersion=ownerVersion;
        if(!owner.equals(r.continueTaskId())){rootVersion=root.path("version").asLong()+1;root.put("status","WAITING_DEPENDENCIES").put("phase","CHILD_INPUT_PROVIDED").put("version",rootVersion).putNull("inputRequest").put("updatedAt",Instant.now().toString());jdbc.update("UPDATE agent_task SET state='WAITING_DEPENDENCIES',version=version+1,snapshot=?,updated_at=? WHERE id=?",encode(root),Timestamp.from(Instant.now()),r.continueTaskId());}
        attachments.bind(owner,r.userId(),r.input().attachmentIds());saveMessage(message,r.conversationId(),owner,r.userId(),"user",r.input().text());attachments.message(message,r.input().attachmentIds());
        return new Accepted(r.conversationId(),message,r.continueTaskId(),rootVersion,owner.equals(r.continueTaskId())?"QUEUED":"WAITING_DEPENDENCIES",null,List.of(),List.of());
    }
    private Accepted create(Request r) {
        Instant now=Instant.now();
        memory.revision(r.userId());
        int open=jdbc.queryForObject("SELECT COUNT(*) FROM agent_task t WHERE user_id=? AND state IN ('QUEUED','RUNNING','WAITING_INPUT','WAITING_DEPENDENCIES','WAITING_CONFIRMATION') AND NOT EXISTS (SELECT 1 FROM agent_delegation d WHERE d.child_task_id=t.id)",Integer.class,r.userId());
        if(open>=10)throw BusinessException.conflict("当前未结束任务已达10项，请先完成或取消旧任务");
        String conversation=r.conversationId();
        if(conversation==null){conversation=UUID.randomUUID().toString();jdbc.update("INSERT INTO agent_conversation VALUES (?,?,?)",conversation,r.userId(),Timestamp.from(now));}
        else if(jdbc.queryForObject("SELECT COUNT(*) FROM agent_conversation WHERE id=? AND user_id=?",Integer.class,conversation,r.userId())!=1)
            throw BusinessException.notFound("会话不存在");
        if(r.relatedTaskId()!=null) {
            var previous=owned(r.relatedTaskId(),r.userId());
            if(!List.of("SUCCEEDED","PARTIALLY_SUCCEEDED","FAILED","CANCELLED","EXPIRED").contains(previous.path("status").asText()))
                throw BusinessException.conflict("relatedTaskId 必须关联已结束任务");
        }
        String id=UUID.randomUUID().toString(), message=UUID.randomUUID().toString();
        ObjectNode s=json.createObjectNode();
        s.put("taskId",id).put("conversationId",conversation).put("sourceMessageId",message)
            .putNull("parentTaskId").put("relatedTaskId",r.relatedTaskId()).put("version",1)
            .put("status","QUEUED").put("phase","ACCEPTED").putNull("reply").putNull("inputRequest")
            .putNull("error").put("createdAt",now.toString()).put("updatedAt",now.toString())
            .put("expiresAt",now.plusSeconds(86400).toString());
        for(String name:List.of("results","confirmationIds","childTasks","pendingInputRequests","effects")) s.putArray(name);
        jdbc.update("INSERT INTO agent_task VALUES (?,?,?,?,?,?,?,?,?)",id,r.userId(),conversation,1,"QUEUED",encode(s),encode(r),Timestamp.from(now),Timestamp.from(now));
        attachments.bind(id,r.userId(),r.input().attachmentIds());saveMessage(message,conversation,id,r.userId(),"user",r.input().text());attachments.message(message,r.input().attachmentIds());
        return new Accepted(conversation,message,id,1,"QUEUED",null,List.of(),List.of());
    }
    @Transactional(readOnly=true)
    public JsonNode get(String id) {ObjectNode s=owned(id,access.currentActor().elderUserId());s.set("childTasks",json.valueToTree(delegations.summaries(id)));s.set("pendingInputRequests",json.valueToTree(inputs.pending(inputs.root(id))));if(memory.stale(id,access.currentActor().elderUserId())||attachments.stale(id)){s.putNull("reply").putNull("inputRequest");s.putArray("results");s.putArray("pendingInputRequests");s.putObject("error").put("code","CONTEXT_INVALIDATED").put("message","任务依赖的资料已失效，旧回复已隐藏").put("retryable",false);}return s;}
    @Transactional(readOnly=true)
    public List<JsonNode> list(String user,int limit){access.requireElderOwner(user);if(limit<1||limit>100)throw BusinessException.invalid("limit必须为1～100");return jdbc.query("SELECT t.id,t.conversation_id,t.state,t.version,t.created_at,t.updated_at FROM agent_task t WHERE t.user_id=? AND NOT EXISTS (SELECT 1 FROM agent_delegation d WHERE d.child_task_id=t.id) ORDER BY t.updated_at DESC,t.id DESC LIMIT ?",(rs,n)->(JsonNode)json.createObjectNode().put("taskId",rs.getString("id")).put("conversationId",rs.getString("conversation_id")).put("status",rs.getString("state")).put("version",rs.getLong("version")).put("createdAt",rs.getTimestamp("created_at").toInstant().toString()).put("updatedAt",rs.getTimestamp("updated_at").toInstant().toString()),user,limit);}
    private ObjectNode owned(String id,String user) {
        access.requireElderOwner(user);
        var rows=jdbc.queryForList("SELECT snapshot FROM agent_task WHERE id=? AND user_id=?",String.class,id,user);
        if(rows.isEmpty()) throw BusinessException.notFound("任务不存在");
        try{return (ObjectNode)json.readTree(rows.getFirst());}catch(Exception e){throw new IllegalStateException("Invalid task snapshot",e);}
    }
    @Transactional
    public JsonNode cancel(String id,Cancel r,String key) {
        if(key==null) throw BusinessException.invalid("必须提供 Idempotency-Key");
        var actor=access.currentActor();
        return keys.execute(actor,"agent.task.cancel",key,Map.of("taskId",id,"request",r),JsonNode.class,n->id,()->{
            ObjectNode s=owned(id,actor.elderUserId());
            if(s.path("version").asLong()!=r.expectedVersion()) throw BusinessException.conflict("任务版本已变化");
            if(!List.of("QUEUED","WAITING_INPUT","WAITING_CONFIRMATION","WAITING_DEPENDENCIES","RUNNING").contains(s.path("status").asText())) throw BusinessException.conflict("当前状态不能取消");
            Instant now=Instant.now();s.put("status","CANCELLED").put("phase","CANCELLED").put("version",r.expectedVersion()+1).put("updatedAt",now.toString());
            s.putNull("inputRequest");s.putArray("pendingInputRequests");
            s.putArray("confirmationIds");
            int changed=jdbc.update("UPDATE agent_task SET state='CANCELLED',version=version+1,snapshot=?,updated_at=? WHERE id=? AND user_id=? AND state IN ('QUEUED','WAITING_INPUT','WAITING_CONFIRMATION','WAITING_DEPENDENCIES','RUNNING') AND version=?",encode(s),Timestamp.from(now),id,actor.elderUserId(),r.expectedVersion());
            if(changed!=1)throw BusinessException.conflict("任务已变化，请刷新");
            jdbc.update("UPDATE agent_invocation SET state='CANCEL_REQUESTED',cancel_request_id=COALESCE(cancel_request_id,UUID()),updated_at=? WHERE task_id=? AND state='RUNNING'",Timestamp.from(now),id);
            jdbc.update("UPDATE agent_confirmation SET state='CANCELLED',version=version+1,decided_at=? WHERE task_id=? AND state='PENDING'",Timestamp.from(now),id);
            jdbc.update("UPDATE agent_input_request SET state='CANCELLED' WHERE root_task_id=? AND state='PENDING'",id);
            for(String child:jdbc.queryForList("SELECT child_task_id FROM agent_delegation WHERE parent_task_id=? ORDER BY child_task_id",String.class,id)){
                var rows=jdbc.queryForList("SELECT snapshot,version FROM agent_task WHERE id=? AND state IN ('QUEUED','RUNNING','WAITING_INPUT') FOR UPDATE",child);if(rows.isEmpty())continue;
                var row=rows.getFirst();ObjectNode cs;
                try{cs=(ObjectNode)json.readTree(row.get("snapshot").toString());}catch(Exception e){throw new IllegalStateException(e);}
                cs.put("status","CANCELLED").put("phase","PARENT_CANCELLED").put("version",((Number)row.get("version")).longValue()+1).put("updatedAt",now.toString());
                jdbc.update("UPDATE agent_task SET state='CANCELLED',version=version+1,snapshot=?,updated_at=? WHERE id=?",encode(cs),Timestamp.from(now),child);
                jdbc.update("UPDATE agent_invocation SET state='CANCEL_REQUESTED',cancel_request_id=COALESCE(cancel_request_id,UUID()),updated_at=? WHERE task_id=? AND state='RUNNING'",Timestamp.from(now),child);
            }
            return s;
        });
    }
    private String encode(Object value){try{return json.writeValueAsString(value);}catch(Exception e){throw new IllegalStateException(e);}}

    @Transactional(readOnly=true)
    public List<Map<String,Object>> invocations(String task) {
        owned(task,access.currentActor().elderUserId());
        return jdbc.query("SELECT id,agent_id,task_version,state,deadline_at,created_at,updated_at FROM agent_invocation WHERE task_id=? ORDER BY created_at,id",(rs,n)->Map.<String,Object>of("invocationId",rs.getString("id"),"agentId",rs.getString("agent_id"),"baseTaskVersion",rs.getLong("task_version"),"state",rs.getString("state"),"deadlineAt",rs.getTimestamp("deadline_at").toInstant(),"createdAt",rs.getTimestamp("created_at").toInstant(),"updatedAt",rs.getTimestamp("updated_at").toInstant()),task);
    }

    private void saveMessage(String id,String conversation,String task,String user,String role,String text) {
        jdbc.update("INSERT INTO agent_message(id,conversation_id,task_id,user_id,role,text,created_at) VALUES (?,?,?,?,?,?,?)",id,conversation,task,user,role,text==null?"":text,Timestamp.from(Instant.now()));
    }

    @Transactional(readOnly=true)
    public List<Map<String,Object>> history(String conversation,int limit) {
        String user=access.currentActor().elderUserId(); access.requireElderOwner(user);
        if(limit<1 || limit>100)throw BusinessException.invalid("limit必须为1～100");
        if(jdbc.queryForObject("SELECT COUNT(*) FROM agent_conversation WHERE id=? AND user_id=?",Integer.class,conversation,user)!=1)throw BusinessException.notFound("会话不存在");
        return jdbc.query("SELECT id,task_id,role,text,created_at FROM agent_message WHERE conversation_id=? AND user_id=? ORDER BY created_at DESC,id DESC LIMIT ?",(rs,n)->Map.<String,Object>of("messageId",rs.getString("id"),"taskId",rs.getString("task_id"),"role",rs.getString("role"),"text","assistant".equals(rs.getString("role"))&&(memory.stale(rs.getString("task_id"),user)||attachments.stale(rs.getString("task_id")))?"[依赖的资料已失效，旧回复已隐藏]":rs.getString("text"),"createdAt",rs.getTimestamp("created_at").toInstant(),"attachmentIds",attachments.messageRefs(rs.getString("id"))),conversation,user,limit);
    }

    @org.springframework.scheduling.annotation.Scheduled(fixedDelay=1000)
    @Transactional
    public void processQueue() {
        var rows=jdbc.queryForList("SELECT id,user_id,snapshot,request_json FROM agent_task WHERE state='QUEUED' OR (state='WAITING_INPUT' AND created_at < ?) ORDER BY updated_at LIMIT 100",Timestamp.from(Instant.now().minusSeconds(86400)));
        for(var row:rows) {
            try {
                ObjectNode s=(ObjectNode)json.readTree(row.get("snapshot").toString());
                long version=s.path("version").asLong();
                String previousState=s.path("status").asText();
                if(!Instant.parse(s.path("expiresAt").asText()).isAfter(Instant.now())) {
                    s.put("status","EXPIRED").put("phase","EXPIRED").put("version",version+1).putNull("inputRequest");s.putArray("pendingInputRequests");
                    int changed=jdbc.update("UPDATE agent_task SET state='EXPIRED',version=version+1,snapshot=?,updated_at=? WHERE id=? AND version=? AND state=?",encode(s),Timestamp.from(Instant.now()),row.get("id"),version,previousState);
                    if(changed==1)jdbc.update("UPDATE agent_input_request SET state='EXPIRED' WHERE state='PENDING' AND "+(s.path("parentTaskId").isNull()?"root_task_id=?":"owner_task_id=?"),row.get("id"));
                    continue;
                }
                if(!"QUEUED".equals(previousState))continue;
            } catch(java.io.IOException e){throw new IllegalStateException("Invalid task snapshot",e);}
        }
    }
}
