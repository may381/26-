package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.common.api.ApiResponse;
import cn.silvertravel.platform.common.api.BusinessException;
import jakarta.validation.Valid;
import org.springframework.context.annotation.Profile;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import com.fasterxml.jackson.databind.JsonNode;

@RestController
@Profile("!bootstrap")
public class AgentActionController {
    private final AgentActionService actions;
    public AgentActionController(AgentActionService actions){this.actions=actions;}
    private String caller(Authentication authentication){return ((AgentServiceIdentity)authentication.getPrincipal()).agentId();}
    @PostMapping("/internal/agent/v3/tasks/{id}/steps")
    public ApiResponse<JsonNode> steps(Authentication authentication,@RequestHeader("X-Agent-Context") String token,@PathVariable String id,@Valid @RequestBody AgentActionService.Steps request){
        if(!id.equals(request.taskId()))throw BusinessException.invalid("路径与正文taskId不一致");return ApiResponse.ok(actions.steps(caller(authentication),token,request));
    }
    @PostMapping("/internal/agent/v3/actions")
    public ApiResponse<JsonNode> prepare(Authentication authentication,@RequestHeader("X-Agent-Context") String token,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody AgentActionService.Prepare request){return ApiResponse.ok(actions.prepare(caller(authentication),token,request,key));}
    @GetMapping("/internal/agent/v3/actions/{id}")
    public ApiResponse<JsonNode> action(Authentication authentication,@RequestHeader("X-Agent-Context") String token,@PathVariable String id){return ApiResponse.ok(actions.queryAction(caller(authentication),token,id));}
    @GetMapping("/internal/agent/v3/tasks/{id}/steps")
    public ApiResponse<JsonNode> steps(Authentication authentication,@RequestHeader("X-Agent-Context") String token,@PathVariable String id){return ApiResponse.ok(actions.querySteps(caller(authentication),token,id));}
    @PostMapping("/internal/agent/v3/confirmations")
    public ApiResponse<JsonNode> confirm(Authentication authentication,@RequestHeader("X-Agent-Context") String token,@Valid @RequestBody AgentActionService.Confirm request){return ApiResponse.ok(actions.publicView(actions.confirm(caller(authentication),token,request)));}
    @GetMapping("/api/v3/agent/confirmations/{id}")
    public ApiResponse<JsonNode> get(@PathVariable String id){return ApiResponse.ok(actions.publicView(actions.get(id)));}
    @PostMapping("/api/v3/agent/confirmations/{id}/decision")
    public ApiResponse<JsonNode> decide(@PathVariable String id,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody AgentActionService.Decide request){return ApiResponse.ok(actions.publicView(actions.decide(id,request,key)));}
}
