package cn.silvertravel.platform.agent;
import cn.silvertravel.platform.common.api.BusinessException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.security.access.AccessDeniedException;
@Service @Profile("!bootstrap")
public class AgentInvocationAccess {
    private final JdbcTemplate jdbc;private final ObjectMapper json;
    public AgentInvocationAccess(JdbcTemplate jdbc,ObjectMapper json){this.jdbc=jdbc;this.json=json;}
    public Map<String,Object> require(String caller,String token,String task){
        var tasks=jdbc.queryForList("SELECT * FROM agent_task WHERE id=? FOR UPDATE",task);if(tasks.isEmpty())throw BusinessException.notFound("任务不存在");var t=tasks.getFirst();
        var calls=jdbc.queryForList("SELECT id,request_json FROM agent_invocation WHERE task_id=? AND agent_id=? AND state='RUNNING' AND deadline_at>?",task,caller,Timestamp.from(Instant.now()));
        if(!"RUNNING".equals(t.get("state"))||calls.size()!=1||token==null)throw new AccessDeniedException("调用凭证失效");
        try{JsonNode r=json.readTree(calls.getFirst().get("request_json").toString());if(!r.path("capabilityToken").asText().equals(token))throw new AccessDeniedException("调用凭证不匹配");}catch(java.io.IOException e){throw new IllegalStateException(e);}
        t.put("invocation_id",calls.getFirst().get("id"));return t;
    }
}
