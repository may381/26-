package cn.silvertravel.platform.agent;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.route.RouteService;
import cn.silvertravel.platform.scenic.SpotQueryService;
import cn.silvertravel.platform.scenic.ScenicData.FacilityType;
import cn.silvertravel.platform.trip.TripService;
import cn.silvertravel.platform.trip.TripProgressService;
import cn.silvertravel.platform.help.HelpEventService;
import cn.silvertravel.platform.security.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.validation.Validator;
import jakarta.validation.constraints.*;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Read-only reuse of existing P2 business services; no Agent may supply a target userId. */
@Service @Profile("!bootstrap")
public class AgentBusinessToolService {
    public record RouteArgs(@Min(1) @Max(1440) Integer walkDurationMin,Boolean avoidSteps) {}
    public record SiteArgs(@Size(max=128) String scenicId) {}
    public record SpotArgs(@NotBlank @Size(max=128) String id,@Size(max=128) String scenicId) {}
    public record IdArgs(@NotBlank @Size(max=36) String id) {}
    public record FacilityArgs(@Size(max=128) String scenicId,FacilityType type,Double lat,Double lng,@Min(1) @Max(100) Integer limit) {}
    public record KnowledgeArgs(@NotBlank @Size(max=1000) String query,AgentProtocol.Intent intent) {}
    private final JdbcTemplate jdbc;private final ObjectMapper json;private final Validator validator;private final AgentInvocationAccess access;private final RouteService routes;private final SpotQueryService spots;private final TripService trips;private final TripProgressService progress;private final HelpEventService help;private final KnowledgeService knowledge;
    public AgentBusinessToolService(JdbcTemplate jdbc,ObjectMapper json,Validator validator,AgentInvocationAccess access,RouteService routes,SpotQueryService spots,TripService trips,TripProgressService progress,HelpEventService help,KnowledgeService knowledge){this.jdbc=jdbc;this.json=json;this.validator=validator;this.access=access;this.routes=routes;this.spots=spots;this.trips=trips;this.progress=progress;this.help=help;this.knowledge=knowledge;}
    public boolean supports(String tool){return Set.of("route.recommend","spot.list","spot.get","facility.search","trip.get","trip.progress.get","help.get","knowledge.search").contains(tool);}
    public void allow(String caller,String tool){if(!supports(tool))throw new AccessDeniedException("业务工具未开放");if(!"a1".equals(caller)&&!"knowledge.search".equals(tool)&&!("a2".equals(caller)&&"help.get".equals(tool)))throw new AccessDeniedException("领域工具不属于当前Agent");}
    private <T>T parse(JsonNode args,Class<T> type){try{T value=json.treeToValue(args,type);if(!validator.validate(value).isEmpty())throw new IllegalArgumentException();return value;}catch(Exception e){throw BusinessException.invalid("业务工具参数错误");}}
    public JsonNode normalize(String tool,JsonNode args){return json.valueToTree(switch(tool){case "route.recommend"->parse(args,RouteArgs.class);case "spot.list"->parse(args,SiteArgs.class);case "spot.get"->parse(args,SpotArgs.class);case "facility.search"->parse(args,FacilityArgs.class);case "trip.get","trip.progress.get","help.get"->parse(args,IdArgs.class);case "knowledge.search"->parse(args,KnowledgeArgs.class);default->throw new AccessDeniedException("业务工具未开放");});}
    @Transactional
    public JsonNode execute(String caller,String token,AgentMemoryService.ToolRequest r){
        var t=access.require(caller,token,r.taskId());String tool=r.input().tool();allow(caller,tool);JsonNode args=normalize(tool,r.input().args());
        if("a2".equals(caller)&&"help.get".equals(tool)&&jdbc.queryForObject("SELECT COUNT(*) FROM agent_delegation WHERE child_task_id=? AND domain IN ('help','care')",Integer.class,r.taskId())!=1)throw new AccessDeniedException("本子任务未授权求助查询");
        var rows=jdbc.queryForList("SELECT * FROM agent_action WHERE id=? AND task_id=? AND step_id=? AND tool=? FOR UPDATE",r.actionId(),r.taskId(),r.stepId(),tool);
        if(rows.isEmpty()||!read(rows.getFirst().get("args")).equals(read(encode(args)))||r.input().confirmationId()!=null)throw BusinessException.conflict("必须引用已准备的相同业务动作");
        JsonNode result;boolean replay="SUCCEEDED".equals(rows.getFirst().get("execution_status"));
        if(replay)result=read(rows.getFirst().get("result"));else{
            String user=t.get("user_id").toString();var previous=SecurityContextHolder.getContext();var delegated=SecurityContextHolder.createEmptyContext();delegated.setAuthentication(UsernamePasswordAuthenticationToken.authenticated(new CurrentActor(user,ActorRole.ELDER,user),null,List.of(new SimpleGrantedAuthority("ROLE_ELDER"))));SecurityContextHolder.setContext(delegated);
            try{Object business=switch(tool){case "route.recommend"->{var a=parse(args,RouteArgs.class);yield routes.recommend(user,a.walkDurationMin(),a.avoidSteps());}case "spot.list"->spots.list(parse(args,SiteArgs.class).scenicId());case "spot.get"->{var a=parse(args,SpotArgs.class);yield spots.get(a.id(),a.scenicId());}case "facility.search"->{var a=parse(args,FacilityArgs.class);yield spots.facilities(a.scenicId(),a.type(),a.lat(),a.lng(),a.limit()==null?20:a.limit());}case "trip.get"->trips.get(user,parse(args,IdArgs.class).id());case "trip.progress.get"->progress.getProgress(parse(args,IdArgs.class).id(),user);case "help.get"->help.get(parse(args,IdArgs.class).id(),user);case "knowledge.search"->{var a=parse(args,KnowledgeArgs.class);yield knowledge.search(a.query(),a.intent());}default->throw new AccessDeniedException("业务工具未开放");};result=json.valueToTree(business);}finally{SecurityContextHolder.setContext(previous);}
            jdbc.update("UPDATE agent_action SET execution_status='SUCCEEDED',result=? WHERE id=?",encode(result),r.actionId());
        }
        ObjectNode out=json.createObjectNode();out.put("actionId",r.actionId()).putNull("effectId").put("tool",tool).put("executionStatus","SUCCEEDED").putNull("businessRef").put("replayed",replay);out.set("result",result);return out;
    }
    private JsonNode read(Object o){try{return json.readTree(o.toString());}catch(Exception e){throw new IllegalStateException(e);}}
    private String encode(Object o){try{return json.writeValueAsString(o);}catch(Exception e){throw new IllegalStateException(e);}}
}
