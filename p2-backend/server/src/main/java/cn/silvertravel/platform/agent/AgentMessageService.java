package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.agent.AgentProtocol.*;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import cn.silvertravel.platform.trip.TripService;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Validator;
import java.util.List;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;

@Service
@Profile("!bootstrap")
public class AgentMessageService {
    private final BusinessAccessPolicy access;
    private final TripService trips;
    private final AgentGateway gateway;
    private final AgentInvocationRegistry registry;
    private final KnowledgeService knowledge;
    private final ObjectMapper json;
    private final Validator validator;

    public AgentMessageService(
            BusinessAccessPolicy access,
            TripService trips,
            AgentGateway gateway,
            AgentInvocationRegistry registry,
            KnowledgeService knowledge,
            ObjectMapper json,
            Validator validator) {
        this.access = access;
        this.trips = trips;
        this.gateway = gateway;
        this.registry = registry;
        this.knowledge = knowledge;
        this.json = json;
        this.validator = validator;
    }

    public Reply send(Message request, String writeKey) {
        if (request == null || !validator.validate(request).isEmpty())
            throw BusinessException.invalid("对话请求字段或长度无效");
        var actor = access.requireElderOwner(request.userId());
        if (!AgentTextSafety.valid(request.text()))
            throw BusinessException.invalid("消息不能为空白或包含异常控制字符");
        if (writeKey != null && !writeKey.matches("[A-Za-z0-9._:-]{1,128}"))
            throw BusinessException.invalid("Idempotency-Key 格式无效");
        if (request.context() != null && request.context().tripId() != null)
            trips.get(request.userId(), request.context().tripId());
        String trace = MDC.get("traceId");
        if (trace == null) trace = UUID.randomUUID().toString();
        Intent intent =
                request.intent() != null ? request.intent() : gateway.classify(request, trace);
        if (intent == null) throw BusinessException.upstream("Agent 未返回有效意图");
        if (intent != Intent.tourism && intent != Intent.help) {
            var result = knowledge.search(intent.name(), intent);
            return new Reply(
                    intent,
                    "该服务暂未开放，仅提供演示占位。",
                    0.8,
                    null,
                    List.of(
                            new ToolCall(
                                    "knowledge.search",
                                    json.createObjectNode()
                                            .put("query", intent.name())
                                            .put("intent", intent.name()),
                                    json.valueToTree(result))),
                    null);
        }
        String agentId = intent == Intent.help ? "a2" : "a1";
        try (var grant = registry.open(actor, agentId, request, writeKey, trace)) {
            Reply reply =
                    gateway.respond(
                            agentId,
                            new WireMessage(
                                    request.userId(),
                                    request.text(),
                                    intent,
                                    request.context(),
                                    grant.token(),
                                    trace));
            if (reply == null
                    || !validator.validate(reply).isEmpty()
                    || reply.intent() != intent
                    || reply.audioUrl() != null)
                throw BusinessException.upstream("Agent 回答不符合平台协议");
            if (!AgentTextSafety.valid(reply.text())
                    || !Double.isFinite(reply.speechRate())
                    || (reply.handoff() != null
                            && !AgentTextSafety.valid(reply.handoff().reason())))
                throw BusinessException.upstream("Agent 回复包含无效文本或语速");
            List<ToolCall> executed = grant.finish();
            if (!reply.tools().isEmpty() && !reply.tools().equals(executed))
                throw BusinessException.upstream("Agent 工具记录与平台执行结果不一致");
            String text = reply.text();
            if (executed.stream().anyMatch(call -> "help.create".equals(call.tool()))) {
                String notice = "平台提示：求助通知仅为模拟演示，未实际触达接收人。";
                text = notice + text.substring(0, Math.min(text.length(), 4000 - notice.length()));
            }
            return new Reply(intent, text, reply.speechRate(), null, executed, reply.handoff());
        }
    }
}
