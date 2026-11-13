package cn.silvertravel.platform.agent;
import cn.silvertravel.platform.common.api.ApiResponse;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.Valid;
import org.springframework.context.annotation.Profile;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
@RestController
@Profile("!bootstrap")
public class AgentDelegationController {
    private final AgentDelegationService delegations;
    public AgentDelegationController(AgentDelegationService delegations){this.delegations=delegations;}
    @PostMapping("/internal/agent/v3/delegations")
    public ApiResponse<JsonNode> delegate(Authentication authentication,@RequestHeader("X-Agent-Context") String token,@Valid @RequestBody AgentDelegationService.Request request){return ApiResponse.ok(delegations.delegate(((AgentServiceIdentity)authentication.getPrincipal()).agentId(),token,request));}
}
