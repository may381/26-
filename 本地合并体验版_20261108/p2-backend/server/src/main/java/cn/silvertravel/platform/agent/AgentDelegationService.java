package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.common.api.BusinessException;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.validation.Valid;
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
public class AgentDelegationService {
    public record Input(@Pattern(regexp="a2|a3") @NotNull String targetAgent,@NotBlank String domain,
            @NotNull Boolean required,@NotBlank @Size(max=2000) String instruction,
            @NotNull @Size(max=0) List<String> attachmentIds,@NotNull @Size(max=0) List<JsonNode> businessRefs) {}
    public record Request(@NotBlank String protocolVersion,@NotBlank String conversationId,
            @NotBlank String taskId,@NotBlank String actionId,@NotNull @Valid Input input) {}
    private static final Set<String> TERMINAL=Set.of("SUCCEEDED","PARTIALLY_SUCCEEDED","FAILED","CANCELLED","EXPIRED");
    private final JdbcTemplate jdbc;private final ObjectMapper json;private final AgentActionService actions;private final AgentInputService inputs;
    public AgentDelegationService(JdbcTemplate jdbc,ObjectMapper json,AgentActionService actions,AgentInputService inputs){this.jdbc=jdbc;this.json=json;this.actions=actions;this.inputs=inputs;}
    @Transactional
    public JsonNode delegate(String caller,String token,Request r){
        if(!"3.0".equals(r.protocolVersion()))throw BusinessException.invalid("protocolVersion必须为3.0");
        var task=actions.authorize(caller,token,r.taskId());ObjectNode parent=read(task.get("snapshot"));
        if(!parent.path("parentTaskId").isNull()||!parent.path("conversationId").asText().equals(r.conversationId()))throw new AccessDeniedException("只允许根A1任务委派");
        validateDomain(r.input());
        var a=jdbc.queryForList("SELECT * FROM agent_action WHERE id=? AND task_id=? AND tool='agent.delegate'",r.actionId(),r.taskId());
        if(a.isEmpty()||!read(a.getFirst().get("args")).equals(read(encode(r.input()))))throw BusinessException.conflict("委派与已准备动作不一致");
        var existing=jdbc.queryForList("SELECT * FROM agent_delegation WHERE action_id=?",r.actionId());
        if(!existing.isEmpty()){var saved=existing.getFirst();if(!read(saved.get("request_json")).equals(read(encode(r))))throw BusinessException.conflict("同动作不能改变委派");return response(saved.get("child_task_id").toString(),r);}
        if(jdbc.queryForObject("SELECT COUNT(*) FROM agent_delegation WHERE parent_task_id=?",Integer.class,r.taskId())>=6)throw BusinessException.conflict("每个根任务最多6项子任务");
        String id=UUID.randomUUID().toString();Instant now=Instant.now();ObjectNode s=json.createObjectNode();
        s.put("taskId",id).put("conversationId",r.conversationId()).put("sourceMessageId",parent.path("sourceMessageId").asText()).put("parentTaskId",r.taskId()).putNull("relatedTaskId").put("version",1).put("status","QUEUED").put("phase","DELEGATED").putNull("reply").putNull("inputRequest").putNull("error").put("createdAt",now.toString()).put("updatedAt",now.toString()).put("expiresAt",parent.path("expiresAt").asText());
        for(String name:List.of("results","confirmationIds","childTasks","pendingInputRequests","effects"))s.putArray(name);
        ObjectNode request=json.createObjectNode();request.put("protocolVersion","3.0").put("userId",task.get("user_id").toString()).put("conversationId",r.conversationId());request.putObject("input").put("text",r.input().instruction()).putArray("attachmentIds");request.putObject("context").putArray("businessRefs");
        jdbc.update("INSERT INTO agent_task VALUES (?,?,?,?,?,?,?,?,?)",id,task.get("user_id"),r.conversationId(),1,"QUEUED",encode(s),encode(request),Timestamp.from(now),Timestamp.from(now));
        jdbc.update("INSERT INTO agent_delegation VALUES (?,?,?,?,?,?,?,?)",id,r.taskId(),r.actionId(),r.input().targetAgent(),r.input().domain(),r.input().required(),encode(r),Timestamp.from(now));
        JsonNode result=response(id,r);jdbc.update("UPDATE agent_action SET execution_status='SUCCEEDED',result=? WHERE id=?",encode(result),r.actionId());return result;
    }
    static void validateDomain(Input i){Set<String> allowed="a2".equals(i.targetAgent())?Set.of("health","care","help","community","volunteer"):Set.of("culture","ability");if(!allowed.contains(i.domain()))throw BusinessException.invalid("子Agent领域不匹配");}
    private ObjectNode response(String id,Request r){return json.createObjectNode().put("childTaskId",id).put("parentTaskId",r.taskId()).put("targetAgent",r.input().targetAgent()).put("status","QUEUED");}
    public String target(String task){return jdbc.queryForList("SELECT target_agent FROM agent_delegation WHERE child_task_id=?",String.class,task).stream().findFirst().orElse("a1");}
    public List<JsonNode> results(String parent){return jdbc.query("SELECT d.child_task_id,d.target_agent,d.required_child,t.snapshot FROM agent_delegation d JOIN agent_task t ON t.id=d.child_task_id WHERE d.parent_task_id=? ORDER BY d.created_at,d.child_task_id",(rs,n)->{ObjectNode snapshot=read(rs.getString("snapshot"));ObjectNode out=json.createObjectNode();out.put("taskId",rs.getString("child_task_id")).put("targetAgent",rs.getString("target_agent")).put("required",rs.getBoolean("required_child")).put("status",snapshot.path("status").asText());out.set("reply",snapshot.path("reply"));out.set("results",snapshot.path("results"));out.set("error",snapshot.path("error"));return (JsonNode)out;},parent);}
    public List<JsonNode> summaries(String parent){return results(parent).stream().map(n->{ObjectNode out=(ObjectNode)n.deepCopy();out.remove(List.of("reply","results","error"));return (JsonNode)out;}).toList();}
    public void validateDependencies(String parent,JsonNode ids){Set<String> registered=new HashSet<>();for(JsonNode n:results(parent))registered.add(n.path("taskId").asText());Set<String> supplied=new HashSet<>();for(JsonNode id:ids)supplied.add(id.asText());if(registered.isEmpty()||!registered.equals(supplied)||ids.size()!=supplied.size())throw BusinessException.conflict("依赖必须完整引用本任务的已登记子任务");}
    @Transactional
    public void reconcile(){
        for(String id:jdbc.queryForList("SELECT DISTINCT parent_task_id FROM agent_delegation",String.class)){
            var rows=jdbc.queryForList("SELECT snapshot,version FROM agent_task WHERE id=? AND state IN ('WAITING_DEPENDENCIES','WAITING_INPUT') FOR UPDATE",id);if(rows.isEmpty())continue;
            List<JsonNode> result=results(id);
            boolean newQuestion=jdbc.queryForObject("SELECT COUNT(*) FROM agent_input_request WHERE root_task_id=? AND owner_task_id<>? AND state='PENDING' AND presented=FALSE",Integer.class,id,id)>0;
            if(!newQuestion && result.stream().anyMatch(n->!TERMINAL.contains(n.path("status").asText())))continue;
            var row=rows.getFirst();ObjectNode s=read(row.get("snapshot"));s.put("status","QUEUED").put("phase",newQuestion?"CHILD_INPUT_REQUIRED":"CHILDREN_FINISHED").put("resumeReason",newQuestion?"CHILD_INPUT_REQUIRED":"CHILDREN_FINISHED").put("version",((Number)row.get("version")).longValue()+1).put("updatedAt",Instant.now().toString());s.set("childTasks",json.valueToTree(summaries(id)));
            jdbc.update("UPDATE agent_task SET state='QUEUED',version=version+1,snapshot=?,updated_at=? WHERE id=? AND state IN ('WAITING_DEPENDENCIES','WAITING_INPUT') AND version=?",encode(s),Timestamp.from(Instant.now()),id,row.get("version"));
            if(newQuestion)jdbc.update("UPDATE agent_input_request SET presented=TRUE WHERE root_task_id=? AND owner_task_id<>? AND state='PENDING'",id,id);
        }
    }
    private ObjectNode read(Object o){try{return (ObjectNode)json.readTree(o.toString());}catch(Exception e){throw new IllegalStateException(e);}}
    private String encode(Object o){try{return json.writeValueAsString(o);}catch(Exception e){throw new IllegalStateException(e);}}
}
