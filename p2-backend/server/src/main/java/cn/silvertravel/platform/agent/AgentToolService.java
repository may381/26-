package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.agent.AgentProtocol.*;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.help.*;
import cn.silvertravel.platform.route.RouteService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.validation.Valid;
import jakarta.validation.Validator;
import jakarta.validation.constraints.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.slf4j.MDC;
import org.springframework.context.annotation.Profile;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

@Service
@Profile("!bootstrap")
public class AgentToolService {
    public record RouteArgs(@Min(1) @Max(1440) Integer walkDurationMin, Boolean avoidSteps) {}

    public record KnowledgeArgs(@NotBlank @Size(max = 1000) String query, Intent intent) {}

    public record HelpArgs(
            @NotNull HelpModels.Type type,
            String tripId,
            @Valid HelpModels.Location location,
            @Size(max = 500) String locationNote) {}

    public record HelpGetArgs(@NotBlank @Size(max = 36) String id) {}

    private final AgentInvocationRegistry registry;
    private final RouteService routes;
    private final KnowledgeService knowledge;
    private final HelpEventService help;
    private final ObjectMapper json;
    private final Validator validator;

    public AgentToolService(
            AgentInvocationRegistry registry,
            RouteService routes,
            KnowledgeService knowledge,
            HelpEventService help,
            ObjectMapper json,
            Validator validator) {
        this.registry = registry;
        this.routes = routes;
        this.knowledge = knowledge;
        this.help = help;
        this.json = json;
        this.validator = validator;
    }

    public ToolCall execute(String agentId, String token, ToolRequest request) {
        if (request.args() == null || !request.args().isObject())
            throw BusinessException.invalid("工具 args 必须为对象");
        return registry.use(
                agentId,
                token,
                request.tool(),
                grant -> {
                    ObjectNode args = ((ObjectNode) request.args()).deepCopy();
                    if (args.has("userId")) {
                        if (!args.get("userId").isTextual()
                                || !grant.actor.elderUserId().equals(args.get("userId").asText()))
                            throw new AccessDeniedException("工具不得切换目标老人");
                        args.remove("userId");
                    }
                    var previous = SecurityContextHolder.getContext();
                    String previousTrace = MDC.get("traceId");
                    var delegated = SecurityContextHolder.createEmptyContext();
                    delegated.setAuthentication(
                            UsernamePasswordAuthenticationToken.authenticated(
                                    grant.actor,
                                    null,
                                    List.of(
                                            new SimpleGrantedAuthority(
                                                    "ROLE_" + grant.actor.role().name()))));
                    SecurityContextHolder.setContext(delegated);
                    MDC.put("traceId", grant.traceId);
                    try {
                        Object result =
                                switch (request.tool()) {
                                    case "route.recommend" -> {
                                        var input = read(args, RouteArgs.class);
                                        yield routes.recommend(
                                                grant.actor.elderUserId(),
                                                input.walkDurationMin(),
                                                input.avoidSteps());
                                    }
                                    case "knowledge.search" -> {
                                        var input = read(args, KnowledgeArgs.class);
                                        yield knowledge.search(input.query(), input.intent());
                                    }
                                    case "help.get" -> {
                                        var input = read(args, HelpGetArgs.class);
                                        yield help.get(input.id(), grant.actor.elderUserId());
                                    }
                                    case "help.create" -> {
                                        var input = read(args, HelpArgs.class);
                                        if (grant.writeKey == null)
                                            throw BusinessException.conflict(
                                                    "求助工具需要原始对话请求的 Idempotency-Key");
                                        String tripId =
                                                grant.message.context() == null
                                                        ? null
                                                        : grant.message.context().tripId();
                                        if (input.tripId() != null
                                                && !Objects.equals(input.tripId(), tripId))
                                            throw new AccessDeniedException("工具不得切换游览上下文");
                                        var command =
                                                new HelpModels.CreateRequest(
                                                        grant.actor.elderUserId(),
                                                        tripId,
                                                        input.type(),
                                                        input.location(),
                                                        input.locationNote());
                                        if (!validator.validate(command).isEmpty())
                                            throw BusinessException.invalid("求助参数不完整或定位无效");
                                        yield help.create(command, null, writeKey(grant.writeKey));
                                    }
                                    case "memory.read" ->
                                            Map.of(
                                                    "available",
                                                    false,
                                                    "items",
                                                    List.of(),
                                                    "message",
                                                    "记忆读写协议尚待确认，暂未开放");
                                    case "memory.write" ->
                                            throw BusinessException.conflict(
                                                    "长期记忆确认流程尚未开放，不接受 Agent 自报 confirmed 作为授权");
                                    default -> throw new AccessDeniedException("工具未开放");
                                };
                        var call =
                                new ToolCall(
                                        request.tool(),
                                        request.args().deepCopy(),
                                        json.valueToTree(result));
                        grant.record(call);
                        return call;
                    } finally {
                        SecurityContextHolder.setContext(previous);
                        if (previousTrace == null) MDC.remove("traceId");
                        else MDC.put("traceId", previousTrace);
                    }
                });
    }

    private <T> T read(JsonNode args, Class<T> type) {
        try {
            T value = json.treeToValue(args, type);
            if (!validator.validate(value).isEmpty()) throw BusinessException.invalid("工具参数无效");
            return value;
        } catch (JsonProcessingException exception) {
            throw BusinessException.invalid("工具参数字段或类型不正确");
        }
    }

    private String writeKey(String key) {
        try {
            return "agent-help-"
                    + HexFormat.of()
                            .formatHex(
                                    MessageDigest.getInstance("SHA-256")
                                            .digest(key.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException exception) {
            throw new IllegalStateException(exception);
        }
    }
}
