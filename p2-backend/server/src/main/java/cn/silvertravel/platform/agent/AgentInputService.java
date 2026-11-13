package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.common.api.BusinessException;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Used inside the caller's task transaction, so question and task state commit together. */
@Service
@Profile("!bootstrap")
public class AgentInputService {
    private final JdbcTemplate jdbc;private final ObjectMapper json;
    public AgentInputService(JdbcTemplate jdbc,ObjectMapper json){this.jdbc=jdbc;this.json=json;}
    public String root(String task){return jdbc.queryForList("SELECT parent_task_id FROM agent_delegation WHERE child_task_id=?",String.class,task).stream().findFirst().orElse(task);}
    public ObjectNode register(String owner,JsonNode draft){
        if(!draft.isObject()||draft.has("ownerTaskId")||draft.has("version"))throw BusinessException.invalid("Agent首提问题不得填写ownerTaskId或version");
        String id=draft.path("inputRequestId").asText();
        try{UUID u=UUID.fromString(id);if(u.version()!=4||!u.toString().equals(id))throw new IllegalArgumentException();}catch(Exception e){throw BusinessException.invalid("inputRequestId必须为规范UUID v4");}
        if(!AgentTextSafety.valid(draft.path("question").asText())||draft.path("question").asText().length()>2000||!draft.path("requiredFields").isArray()||draft.path("requiredFields").size()>20||!draft.path("options").isArray()||draft.path("options").size()>20||!draft.path("allowFreeText").isBoolean())throw BusinessException.invalid("问题字段无效");
        Set<String> fields=Set.of("inputRequestId","question","requiredFields","options","allowFreeText");draft.fieldNames().forEachRemaining(k->{if(!fields.contains(k))throw BusinessException.invalid("未知问题字段");});
        for(JsonNode field:draft.path("requiredFields"))if(!field.isTextual()||!AgentTextSafety.valid(field.asText())||field.asText().length()>128)throw BusinessException.invalid("待补充字段无效");
        Set<String> optionIds=new HashSet<>();for(JsonNode option:draft.path("options")){if(!option.isObject()||!AgentTextSafety.valid(option.path("id").asText())||!AgentTextSafety.valid(option.path("label").asText())||!option.path("value").isTextual()||!optionIds.add(option.path("id").asText()))throw BusinessException.invalid("问题选项无效");}
        String root=root(owner);var existing=jdbc.queryForList("SELECT * FROM agent_input_request WHERE id=?",id);
        if(existing.isEmpty()){
            try{jdbc.update("INSERT INTO agent_input_request(id,owner_task_id,root_task_id,version,state,question_json,created_at) VALUES (?,?,?,1,'PENDING',?,?)",id,owner,root,encode(draft),Timestamp.from(Instant.now()));}
            catch(DuplicateKeyException collision){throw BusinessException.conflict("INPUT_REQUEST_ID_CONFLICT");}
            return registered(draft,owner,1);
        }
        var saved=existing.getFirst();
        boolean own=owner.equals(saved.get("owner_task_id"));boolean reference=owner.equals(root)&&root.equals(saved.get("root_task_id"));
        if((!own&&!reference)||!"PENDING".equals(saved.get("state"))||!read(saved.get("question_json")).equals(draft))throw BusinessException.conflict("INPUT_REQUEST_ID_CONFLICT");
        return registered(draft,saved.get("owner_task_id").toString(),((Number)saved.get("version")).intValue());
    }
    public List<JsonNode> pending(String root){return jdbc.query("SELECT q.owner_task_id,q.version,q.question_json FROM agent_input_request q JOIN agent_task r ON r.id=q.root_task_id WHERE q.root_task_id=? AND q.state='PENDING' AND r.state IN ('QUEUED','RUNNING','WAITING_INPUT','WAITING_DEPENDENCIES','WAITING_CONFIRMATION') ORDER BY q.created_at,q.id",(rs,n)->(JsonNode)registered(read(rs.getString("question_json")),rs.getString("owner_task_id"),rs.getInt("version")),root);}
    public JsonNode draft(JsonNode question){ObjectNode d=((ObjectNode)question).deepCopy();d.remove(List.of("ownerTaskId","version"));return d;}
    private ObjectNode registered(JsonNode draft,String owner,int version){ObjectNode q=(ObjectNode)draft.deepCopy();q.put("ownerTaskId",owner).put("version",version);return q;}
    private ObjectNode read(Object o){try{return (ObjectNode)json.readTree(o.toString());}catch(Exception e){throw new IllegalStateException(e);}}
    private String encode(Object o){try{return json.writeValueAsString(o);}catch(Exception e){throw new IllegalStateException(e);}}
}
