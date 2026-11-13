package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
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

@Service @Profile("!bootstrap")
public class AgentMemoryService {
    public record Source(@Pattern(regexp="USER_MESSAGE") @NotNull String type,@NotBlank String id) {}
    public record Candidate(@Pattern(regexp="LONG_TERM_PREFERENCE") @NotNull String category,@NotBlank @Size(max=128) String key,@NotBlank @Size(max=1000) String content,JsonNode value,@NotNull @Size(min=1,max=3) List<@NotBlank String> domains,@Pattern(regexp="GENERAL") @NotNull String sensitivity,@NotNull @Size(min=1,max=5) List<@Valid Source> sourceRefs) {}
    public record Review(@NotBlank String candidateId,@Min(1) int candidateVersion,@Pattern(regexp="ADD|KEEP|REJECT") @NotNull String recommendation,@NotBlank @Size(max=2000) String explanation) {}
    public record Change(@Pattern(regexp="ADD") @NotNull String operation,@NotBlank String candidateId,@Min(1) int candidateVersion,@NotBlank String reviewId,@Min(1) int reviewVersion) {}
    public record Search(@NotBlank @Size(max=500) String purpose,@NotBlank @Size(max=1000) String query,@NotNull @Size(min=1,max=3) List<@NotBlank String> domains,@Min(1) @Max(10) Integer limit,@Min(200) @Max(4000) Integer maxContentChars) {}
    public record ToolInput(@NotBlank String tool,@NotNull JsonNode args,String confirmationId) {}
    public record ToolRequest(@Pattern(regexp="3.0") @NotNull String protocolVersion,@NotBlank String taskId,@NotBlank String stepId,@NotBlank String actionId,@NotNull @Valid ToolInput input) {}
    private final JdbcTemplate jdbc;private final ObjectMapper json;private final Validator validator;private final AgentInvocationAccess invocations;private final BusinessAccessPolicy access;private final cn.silvertravel.platform.audit.AuditService audit;
    public AgentMemoryService(JdbcTemplate jdbc,ObjectMapper json,Validator validator,AgentInvocationAccess invocations,BusinessAccessPolicy access,cn.silvertravel.platform.audit.AuditService audit){this.jdbc=jdbc;this.json=json;this.validator=validator;this.invocations=invocations;this.access=access;this.audit=audit;}
    private String root(String task){return jdbc.queryForList("SELECT parent_task_id FROM agent_delegation WHERE child_task_id=?",String.class,task).stream().findFirst().orElse(task);}
    private <T>T parse(JsonNode n,Class<T> type){try{T r=json.treeToValue(n,type);if(!validator.validate(r).isEmpty())throw new IllegalArgumentException();return r;}catch(Exception e){throw BusinessException.invalid("记忆参数不符合当前开放格式");}}
    public JsonNode normalize(String tool,JsonNode args){return json.valueToTree(switch(tool){case "memory.search"->parse(args,Search.class);case "memory.candidate.create"->parse(args,Candidate.class);case "memory.candidate.review"->parse(args,Review.class);case "memory.change"->parse(args,Change.class);default->throw new AccessDeniedException("记忆工具未开放");});}
    public void allow(String caller,String tool){if("memory.candidate.review".equals(tool)&&!"a3".equals(caller)||"memory.change".equals(tool)&&!"a1".equals(caller))throw new AccessDeniedException("该记忆能力不属于当前Agent");}
    private void scope(String caller,String task,List<String> domains){
        Set<String> allowed=Set.of("tourism","fraud","health","care","help","community","volunteer","culture","ability");
        if(!"a1".equals(caller)){var d=jdbc.queryForList("SELECT domain FROM agent_delegation WHERE child_task_id=? AND target_agent=?",String.class,task,caller);if(d.size()!=1)throw new AccessDeniedException("子任务领域未授权");allowed=Set.of(d.getFirst());}
        if(new HashSet<>(domains).size()!=domains.size()||!allowed.containsAll(domains))throw new AccessDeniedException("记忆领域越权");
    }
    public long revision(String user){jdbc.update("INSERT IGNORE INTO elder_memory_revision(user_id,revision) VALUES (?,0)",user);return jdbc.queryForObject("SELECT revision FROM elder_memory_revision WHERE user_id=? FOR UPDATE",Long.class,user);}
    @Transactional
    public JsonNode execute(String caller,String token,ToolRequest r){
        var t=invocations.require(caller,token,r.taskId());allow(caller,r.input().tool());
        var actions=jdbc.queryForList("SELECT * FROM agent_action WHERE id=? AND step_id=? AND task_id=? AND tool=? FOR UPDATE",r.actionId(),r.stepId(),r.taskId(),r.input().tool());
        if(actions.isEmpty()||!read(actions.getFirst().get("args")).equals(read(encode(normalize(r.input().tool(),r.input().args()))))||r.input().confirmationId()!=null)throw BusinessException.conflict("工具必须引用同参数的已准备动作");
        if("memory.change".equals(r.input().tool()))throw new AccessDeniedException("记忆写入仅允许老人确认执行器");
        if("SUCCEEDED".equals(actions.getFirst().get("execution_status"))){if("memory.search".equals(r.input().tool()))throw BusinessException.conflict("检索动作已执行，请登记新的读取步骤以核对当前版本");return toolResult(r,read(actions.getFirst().get("result")),true);}
        String user=t.get("user_id").toString();JsonNode result=switch(r.input().tool()){
            case "memory.candidate.create"->candidate(caller,r.taskId(),user,parse(r.input().args(),Candidate.class));
            case "memory.candidate.review"->review(r.taskId(),user,parse(r.input().args(),Review.class));
            case "memory.search"->search(caller,r.taskId(),user,t.get("invocation_id").toString(),parse(r.input().args(),Search.class));
            default->throw new AccessDeniedException("工具未开放");};
        jdbc.update("UPDATE agent_action SET execution_status='SUCCEEDED',result=? WHERE id=?",encode(result),r.actionId());return toolResult(r,result,false);
    }
    private JsonNode toolResult(ToolRequest r,JsonNode result,boolean replay){ObjectNode n=json.createObjectNode();n.put("actionId",r.actionId()).putNull("effectId").put("tool",r.input().tool()).put("executionStatus","SUCCEEDED").putNull("businessRef").put("replayed",replay);n.set("result",result);return n;}
    private JsonNode candidate(String caller,String task,String user,Candidate c){
        scope(caller,task,c.domains());if(!AgentTextSafety.valid(c.content()))throw BusinessException.invalid("记忆正文无效");
        if(!Collections.disjoint(c.domains(),List.of("health","care","help"))||c.value()!=null&&c.value().toString().length()>1000)throw BusinessException.invalid("本批不保存健康照护求助记忆，value最多1000字符");
        for(Source s:c.sourceRefs())if(jdbc.queryForObject("SELECT COUNT(*) FROM agent_message WHERE id=? AND user_id=? AND role='user' AND task_id IN (SELECT id FROM agent_task WHERE id=? OR id IN (SELECT child_task_id FROM agent_delegation WHERE parent_task_id=?))",Integer.class,s.id(),user,root(task),root(task))!=1)throw new AccessDeniedException("来源不属于当前老人任务树中的用户消息");
        String id=UUID.randomUUID().toString();jdbc.update("INSERT INTO memory_candidate(id,user_id,root_task_id,state,payload,created_at) VALUES (?,?,?,'CANDIDATE',?,?)",id,user,root(task),encode(c),Timestamp.from(Instant.now()));return json.createObjectNode().put("candidateId",id).put("candidateVersion",1).put("state","CANDIDATE");
    }
    private JsonNode review(String task,String user,Review r){
        var c=candidateRow(user,r.candidateId(),r.candidateVersion());if(!root(task).equals(c.get("root_task_id")))throw new AccessDeniedException("候选不属于当前任务树");
        var old=jdbc.queryForList("SELECT payload FROM memory_review WHERE candidate_id=?",String.class,r.candidateId());if(!old.isEmpty())throw BusinessException.conflict("候选已有审核，请复用已保存审核");
        JsonNode payload=read(c.get("payload"));scope("a3",task,strings(payload.path("domains")));String id=UUID.randomUUID().toString();
        ObjectNode out=json.createObjectNode();out.put("candidateId",r.candidateId()).put("candidateVersion",r.candidateVersion()).put("reviewId",id).put("reviewVersion",1).put("recommendation",r.recommendation()).put("needsUserConfirmation","ADD".equals(r.recommendation())).put("explanation",r.explanation());out.putArray("conflictMemoryRefs");out.set("proposedDomains",payload.path("domains"));
        jdbc.update("INSERT INTO memory_review(id,candidate_id,candidate_version,payload,created_at) VALUES (?,?,?,?,?)",id,r.candidateId(),r.candidateVersion(),encode(out),Timestamp.from(Instant.now()));return out;
    }
    private Map<String,Object> candidateRow(String user,String id,int version){var rows=jdbc.queryForList("SELECT * FROM memory_candidate WHERE id=? AND user_id=? AND version=? AND state='CANDIDATE' FOR UPDATE",id,user,version);if(rows.isEmpty())throw BusinessException.conflict("候选已失效或版本不匹配");return rows.getFirst();}
    public JsonNode changeContent(String user,String task,Change r){var c=candidateRow(user,r.candidateId(),r.candidateVersion());if(!root(task).equals(c.get("root_task_id")))throw new AccessDeniedException("候选不属于当前任务树");var reviews=jdbc.queryForList("SELECT payload FROM memory_review WHERE id=? AND candidate_id=? AND candidate_version=? AND version=?",String.class,r.reviewId(),r.candidateId(),r.candidateVersion(),r.reviewVersion());if(reviews.isEmpty()||!"ADD".equals(read(reviews.getFirst()).path("recommendation").asText()))throw BusinessException.conflict("没有有效的A3新增审核建议");return read(c.get("payload"));}
    public JsonNode apply(String user,String task,Change r){revision(user);JsonNode content=changeContent(user,task,r);
        if(jdbc.queryForObject("SELECT COUNT(*) FROM elder_memory WHERE user_id=? AND state='ACTIVE' AND JSON_UNQUOTE(JSON_EXTRACT(payload,'$.key'))=?",Integer.class,user,content.path("key").asText())>0)throw BusinessException.conflict("存在同键有效记忆，需先对齐替换规则");
        String id=UUID.randomUUID().toString();Instant now=Instant.now();jdbc.update("INSERT INTO elder_memory(id,user_id,candidate_id,state,payload,confirmed_at,updated_at) VALUES (?,?,?,'ACTIVE',?,?,?)",id,user,r.candidateId(),encode(content),Timestamp.from(now),Timestamp.from(now));jdbc.update("UPDATE memory_candidate SET state='APPLIED' WHERE id=?",r.candidateId());jdbc.update("UPDATE elder_memory_revision SET revision=revision+1 WHERE user_id=?",user);audit.record(access.requireElderOwner(user),user,"MEMORY_CONFIRMED","memory",id);return json.createObjectNode().put("memoryId",id).put("version",1).put("state","ACTIVE");}
    private JsonNode search(String caller,String task,String user,String invocation,Search r){scope(caller,task,r.domains());long rev=revision(user);int budget=r.maxContentChars()==null?2000:r.maxContentChars(),limit=r.limit()==null?5:r.limit(),chars=0;boolean truncated=false;ObjectNode out=json.createObjectNode();var items=out.putArray("items");var refs=json.createArrayNode();
        for(var row:jdbc.queryForList("SELECT * FROM elder_memory WHERE user_id=? AND state='ACTIVE' ORDER BY confirmed_at DESC,id LIMIT 100",user)){ObjectNode p=read(row.get("payload"));if(Collections.disjoint(strings(p.path("domains")),r.domains()))continue;int size=p.path("content").asText().codePointCount(0,p.path("content").asText().length());if(items.size()>=limit||chars+size>budget){truncated=true;continue;}chars+=size;p.put("memoryId",row.get("id").toString()).put("version",((Number)row.get("version")).intValue()).put("state","ACTIVE").put("confirmedAt",((Timestamp)row.get("confirmed_at")).toInstant().toString()).put("updatedAt",((Timestamp)row.get("updated_at")).toInstant().toString()).putNull("expiresAt");items.add(p);refs.addObject().put("memoryId",row.get("id").toString()).put("version",((Number)row.get("version")).intValue());}
        out.put("readStatus",items.isEmpty()?"EMPTY":"AVAILABLE").put("memoryRevision",rev).put("authorizationRevision",0).put("retrievedAt",Instant.now().toString()).put("returnedContentChars",chars).put("truncated",truncated);
        jdbc.update("INSERT INTO agent_memory_read VALUES (?,?,?,?) ON DUPLICATE KEY UPDATE memory_refs=JSON_MERGE_PRESERVE(memory_refs,VALUES(memory_refs))",invocation,user,rev,encode(refs));return out;
    }
    public long currentRevision(String user){return jdbc.queryForObject("SELECT COALESCE((SELECT revision FROM elder_memory_revision WHERE user_id=?),0)",Long.class,user);}
    public boolean stale(String task,String user){long rev=currentRevision(user);return jdbc.queryForObject("SELECT COUNT(*) FROM agent_memory_read m JOIN agent_invocation i ON i.id=m.invocation_id WHERE i.task_id=? AND m.revision<>?",Integer.class,task,rev)>0;}
    public void assertTaskCurrent(String task,String user){long rev=revision(user);if(jdbc.queryForObject("SELECT COUNT(*) FROM agent_memory_read m JOIN agent_invocation i ON i.id=m.invocation_id WHERE i.task_id=? AND m.revision<>?",Integer.class,task,rev)>0)throw BusinessException.conflict("确认依赖的记忆已变化，请重新准备");}
    public void inherit(String task,String invocation,String user){
        long rev=revision(user);var rows=jdbc.queryForList("SELECT m.memory_refs,m.revision FROM agent_memory_read m JOIN agent_invocation i ON i.id=m.invocation_id WHERE (i.task_id=? OR i.task_id IN (SELECT child_task_id FROM agent_delegation WHERE parent_task_id=?)) AND m.invocation_id<>?",task,task,invocation);
        if(rows.isEmpty())return;for(var row:rows)if(((Number)row.get("revision")).longValue()!=rev)throw BusinessException.conflict("恢复上下文依赖的记忆已失效，请新建任务");
        var refs=json.createArrayNode();Set<String> seen=new HashSet<>();List<String> values=new ArrayList<>(jdbc.queryForList("SELECT memory_refs FROM agent_memory_read WHERE invocation_id=?",String.class,invocation));for(var row:rows)values.add(row.get("memory_refs").toString());for(String value:values){try{for(JsonNode ref:json.readTree(value))if(seen.add(ref.path("memoryId").asText()+":"+ref.path("version").asLong()))refs.add(ref);}catch(Exception e){throw new IllegalStateException(e);}}
        jdbc.update("INSERT INTO agent_memory_read VALUES (?,?,?,?) ON DUPLICATE KEY UPDATE memory_refs=VALUES(memory_refs)",invocation,user,rev,encode(refs));
    }
    public void verifyUsed(String invocation,JsonNode used){
        if(!used.isArray()||used.size()>20)throw BusinessException.invalid("usedMemoryRefs格式无效");
        Set<String> actual=new HashSet<>();for(String value:jdbc.queryForList("SELECT memory_refs FROM agent_memory_read WHERE invocation_id=?",String.class,invocation)){try{for(JsonNode ref:json.readTree(value))actual.add(ref.path("memoryId").asText()+":"+ref.path("version").asLong());}catch(Exception e){throw new IllegalStateException(e);}}
        for(JsonNode ref:used)if(!ref.path("version").isIntegralNumber()||!actual.contains(ref.path("memoryId").asText()+":"+ref.path("version").asLong()))throw BusinessException.conflict("记忆引用未实际授权读取");
    }
    public JsonNode reviewCard(String task,JsonNode payload){var rows=jdbc.queryForList("SELECT r.payload FROM memory_review r JOIN memory_candidate c ON c.id=r.candidate_id WHERE r.id=? AND c.root_task_id=?",String.class,payload.path("reviewId").asText(),root(task));if(rows.size()!=1||!read(rows.getFirst()).equals(payload))throw BusinessException.conflict("审核卡片与保存记录不符");return payload;}
    public void checkInvocation(String invocation,String user){long rev=revision(user);if(jdbc.queryForObject("SELECT COUNT(*) FROM agent_memory_read WHERE invocation_id=? AND revision<>?",Integer.class,invocation,rev)>0)throw BusinessException.conflict("记忆已更新，旧调用结果不再落地");}
    @Transactional(readOnly=true)
    public List<JsonNode> list(String user){access.requireElderOwner(user);return jdbc.query("SELECT id,version,payload,confirmed_at FROM elder_memory WHERE user_id=? AND state='ACTIVE' ORDER BY confirmed_at DESC,id LIMIT 100",(rs,n)->{ObjectNode p=read(rs.getString("payload"));p.put("memoryId",rs.getString("id")).put("version",rs.getInt("version")).put("confirmedAt",rs.getTimestamp("confirmed_at").toInstant().toString());return (JsonNode)p;},user);}
    @Transactional
    public void delete(String user,String id,int expectedVersion){access.requireElderOwner(user);revision(user);int changed=jdbc.update("UPDATE elder_memory SET state='DELETED',payload=NULL,version=version+1,updated_at=? WHERE id=? AND user_id=? AND version=? AND state='ACTIVE'",Timestamp.from(Instant.now()),id,user,expectedVersion);if(changed!=1)throw BusinessException.conflict("记忆不存在、已删除或版本已变化");jdbc.update("UPDATE memory_candidate SET payload=JSON_OBJECT('deleted',true) WHERE id=(SELECT candidate_id FROM elder_memory WHERE id=? AND user_id=?)",id,user);jdbc.update("UPDATE elder_memory_revision SET revision=revision+1 WHERE user_id=?",user);audit.record(access.currentActor(),user,"MEMORY_DELETED","memory",id);}
    public boolean deletedCandidate(String id){return jdbc.queryForObject("SELECT COUNT(*) FROM elder_memory WHERE candidate_id=? AND state='DELETED'",Integer.class,id)>0;}
    public List<JsonNode> reviews(String root){return jdbc.queryForList("SELECT r.payload FROM memory_review r JOIN memory_candidate c ON c.id=r.candidate_id WHERE c.root_task_id=? AND c.state='CANDIDATE' ORDER BY r.created_at",String.class,root).stream().map(this::read).map(n->(JsonNode)n).toList();}
    private List<String> strings(JsonNode n){List<String> values=new ArrayList<>();n.forEach(v->values.add(v.asText()));return values;}
    private ObjectNode read(Object o){try{return (ObjectNode)json.readTree(o.toString());}catch(Exception e){throw new IllegalStateException(e);}}
    private String encode(Object o){try{return json.writeValueAsString(o);}catch(Exception e){throw new IllegalStateException(e);}}
}
