package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.agent.AgentProtocol.*;
import cn.silvertravel.platform.common.api.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.context.annotation.Profile;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
public class AgentController {
    private final AgentMessageService messages;
    private final AgentToolService tools;
    private final AgentTaskService tasks;
    private final AgentMemoryService memory;private final AgentBusinessToolService business;

    public AgentController(AgentMessageService messages, AgentToolService tools, AgentTaskService tasks,AgentMemoryService memory,AgentBusinessToolService business) {
        this.messages = messages;
        this.tools = tools;
        this.tasks = tasks;this.memory=memory;this.business=business;
    }

    @PostMapping("/api/v3/agent/messages")
    public ApiResponse<AgentTaskService.Accepted> send(
            @RequestBody @Valid AgentTaskService.Request message,
            @RequestHeader("Idempotency-Key") String key) {
        requireVersion(message.protocolVersion());
        return new ApiResponse<>("OK", "消息已接收", tasks.accept(message, key));
    }

    @GetMapping("/api/v3/agent/tasks/{id}")
    public ApiResponse<com.fasterxml.jackson.databind.JsonNode> task(@PathVariable String id) {
        return ApiResponse.ok(tasks.get(id));
    }
    @GetMapping("/api/v3/agent/tasks")
    public ApiResponse<java.util.List<com.fasterxml.jackson.databind.JsonNode>> list(@RequestParam String userId,@RequestParam(defaultValue="20")int limit){return ApiResponse.ok(tasks.list(userId,limit));}

    @GetMapping("/api/v3/agent/conversations/{id}/messages")
    public ApiResponse<java.util.List<java.util.Map<String,Object>>> history(@PathVariable String id,
            @RequestParam(defaultValue="20") int limit) {
        return ApiResponse.ok(tasks.history(id,limit));
    }

    @GetMapping("/api/v3/agent/tasks/{id}/invocations")
    public ApiResponse<java.util.List<java.util.Map<String,Object>>> invocations(@PathVariable String id) {
        return ApiResponse.ok(tasks.invocations(id));
    }

    @PostMapping("/api/v3/agent/tasks/{id}/cancel")
    public ApiResponse<com.fasterxml.jackson.databind.JsonNode> cancel(@PathVariable String id,
            @Valid @RequestBody AgentTaskService.Cancel request,
            @RequestHeader("Idempotency-Key") String key) {
        return ApiResponse.ok(tasks.cancel(id, request, key));
    }

    @PostMapping("/internal/agent/v3/tools")
    public ApiResponse<com.fasterxml.jackson.databind.JsonNode> tool(
            Authentication authentication,
            @RequestHeader("X-Agent-Context") String token,
            @RequestBody @Valid AgentMemoryService.ToolRequest request) {
        requireVersion(request.protocolVersion());
        var caller = (AgentServiceIdentity) authentication.getPrincipal();
        return ApiResponse.ok(request.input().tool().startsWith("memory.")?memory.execute(caller.agentId(), token, request):business.execute(caller.agentId(),token,request));
    }

    private void requireVersion(String version) {
        if (!"3.0".equals(version)) throw new UnsupportedVersion();
    }

    private static class UnsupportedVersion extends RuntimeException {}

    @ExceptionHandler(UnsupportedVersion.class)
    public ResponseEntity<ApiResponse<Void>> unsupportedVersion() {
        return ResponseEntity.badRequest()
                .body(ApiResponse.error("UNSUPPORTED_PROTOCOL_VERSION", "请使用 protocolVersion=3.0"));
    }
}
