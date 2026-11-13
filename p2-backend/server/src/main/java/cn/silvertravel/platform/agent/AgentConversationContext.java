package cn.silvertravel.platform.agent;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.sql.Timestamp;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
@Service @Profile("!bootstrap")
public class AgentConversationContext {
    private final JdbcTemplate jdbc;private final ObjectMapper json;private final AgentMemoryService memory;private final AgentAttachmentService attachments;
    public AgentConversationContext(JdbcTemplate jdbc,ObjectMapper json,AgentMemoryService memory,AgentAttachmentService attachments){this.jdbc=jdbc;this.json=json;this.memory=memory;this.attachments=attachments;}
    public List<JsonNode> history(String user,String conversation,String currentMessage){
        List<JsonNode> out=new ArrayList<>();int chars=0;
        for(var row:jdbc.queryForList("SELECT id,task_id,role,text,created_at FROM agent_message WHERE user_id=? AND conversation_id=? AND id<>? ORDER BY created_at DESC,id DESC LIMIT 20",user,conversation,currentMessage)){
            if("assistant".equals(row.get("role"))&&(memory.stale(row.get("task_id").toString(),user)||attachments.stale(row.get("task_id").toString())))continue;
            String text=row.get("text").toString();if(chars+text.length()>8000)continue;chars+=text.length();
            ObjectNode n=json.createObjectNode().put("messageId",row.get("id").toString()).put("role",row.get("role").toString()).put("text",text).put("createdAt",((Timestamp)row.get("created_at")).toInstant().toString());n.putArray("attachmentIds");out.add(n);
        }
        Collections.reverse(out);return out;
    }
    public List<JsonNode> candidates(String user,String conversation,String currentTask){return jdbc.query("SELECT t.id,t.state,t.snapshot,t.request_json,t.updated_at FROM agent_task t WHERE t.user_id=? AND t.conversation_id=? AND t.id<>? AND t.state IN ('QUEUED','RUNNING','WAITING_INPUT','WAITING_CONFIRMATION','WAITING_DEPENDENCIES') AND NOT EXISTS (SELECT 1 FROM agent_delegation d WHERE d.child_task_id=t.id) ORDER BY t.updated_at DESC,t.id LIMIT 5",(rs,n)->{
        try{JsonNode request=json.readTree(rs.getString("request_json")),snapshot=json.readTree(rs.getString("snapshot"));String summary=request.path("input").path("text").asText("图片任务");if(memory.stale(rs.getString("id"),user)||attachments.stale(rs.getString("id")))summary="已有任务的资料已失效，请重新确认";ObjectNode out=json.createObjectNode().put("taskId",rs.getString("id")).put("summary",summary.substring(0,Math.min(summary.length(),200))).put("status",rs.getString("state")).put("updatedAt",rs.getTimestamp("updated_at").toInstant().toString());out.set("inputRequestId",snapshot.path("inputRequest").path("inputRequestId").isMissingNode()?json.nullNode():snapshot.path("inputRequest").path("inputRequestId"));out.putArray("businessRefs");return (JsonNode)out;}catch(java.io.IOException e){throw new IllegalStateException(e);}
    },user,conversation,currentTask);}
    public void inherit(String task,String invocation,String user,JsonNode history){
        Set<String> inherited=new HashSet<>();inherited.add(task);
        for(JsonNode item:history){if(!"assistant".equals(item.path("role").asText()))continue;for(String source:jdbc.queryForList("SELECT task_id FROM agent_message WHERE id=? AND user_id=? AND role='assistant'",String.class,item.path("messageId").asText(),user)){
            if(!inherited.add(source))continue;memory.inherit(source,invocation,user);
            jdbc.update("INSERT IGNORE INTO agent_task_attachment(task_id,attachment_id) SELECT ?,attachment_id FROM agent_task_attachment WHERE task_id=?",task,source);
        }}
    }
}
