package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.agent.AgentProtocol.*;
import cn.silvertravel.platform.common.api.BusinessException;
import com.fasterxml.jackson.databind.*;
import java.net.URI;
import java.util.Map;
import org.springframework.web.client.RestClient;

public class HttpAgentGateway implements AgentGateway {
    private final RestClient http;
    private final AgentProperties properties;
    private final ObjectMapper json;

    public HttpAgentGateway(RestClient http, AgentProperties properties, ObjectMapper json) {
        this.http = http;
        this.properties = properties;
        this.json = json;
    }

    @Override
    public Intent classify(Message message, String traceId) {
        JsonNode data =
                post(
                        "a1",
                        "/internal/v3/intents",
                        Map.of("protocolVersion", "3.0", "input", Map.of("text", message.text())),
                        traceId);
        try {
            return json.treeToValue(data.path("intent"), Intent.class);
        } catch (Exception exception) {
            throw failed();
        }
    }

    @Override
    public Reply respond(String agentId, WireMessage message) {
        JsonNode data = post(agentId, "/internal/v3/messages", message, message.traceId());
        try {
            return json.treeToValue(data, Reply.class);
        } catch (Exception exception) {
            throw failed();
        }
    }

    private JsonNode post(String agentId, String path, Object body, String traceId) {
        try {
            byte[] payload = json.writeValueAsBytes(body);
            var result =
                    http.post()
                            .uri(URI.create(properties.url(agentId)).resolve(path))
                            .header("X-Agent-Key", properties.key(agentId))
                            .header("X-Trace-Id", traceId)
                            .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                            .contentLength(payload.length)
                            .body(payload)
                            .exchange(
                                    (request, response) -> {
                                        if (!response.getStatusCode().is2xxSuccessful())
                                            throw failed();
                                        byte[] bytes =
                                                response.getBody().readNBytes(1024 * 1024 + 1);
                                        if (bytes.length > 1024 * 1024) throw failed();
                                        return json.readTree(bytes);
                                    });
            if (result == null
                    || !"OK".equals(result.path("code").asText())
                    || !result.path("message").isTextual()
                    || result.path("message").asText().isBlank()
                    || !result.path("data").isObject()) throw failed();
            return result.path("data");
        } catch (Exception exception) {
            for (Throwable cause = exception; cause != null; cause = cause.getCause()) {
                if (cause instanceof java.net.SocketTimeoutException
                        || cause instanceof java.net.http.HttpTimeoutException) {
                    throw new BusinessException(
                            org.springframework.http.HttpStatus.GATEWAY_TIMEOUT,
                            "Agent 服务响应超时，请稍后核查；已执行工具不自动回滚");
                }
            }
            throw failed();
        }
    }

    private BusinessException failed() {
        return BusinessException.upstream("Agent 服务暂不可用，请稍后重试；直接求助入口仍可使用");
    }
}
