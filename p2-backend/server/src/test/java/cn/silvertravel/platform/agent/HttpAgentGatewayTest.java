package cn.silvertravel.platform.agent;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

import cn.silvertravel.platform.agent.AgentProtocol.*;
import cn.silvertravel.platform.common.api.BusinessException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.SocketTimeoutException;
import org.junit.jupiter.api.*;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class HttpAgentGatewayTest {
    private static final String KEY = "fixture-http-agent-key-123456789";
    private MockRestServiceServer server;
    private HttpAgentGateway gateway;

    @BeforeEach
    void setup() {
        var builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        gateway =
                new HttpAgentGateway(
                        builder.build(), properties(KEY, KEY + "2", KEY + "3"), new ObjectMapper());
    }

    private AgentProperties properties(String a, String b, String c) {
        return new AgentProperties(
                AgentProperties.Mode.http,
                "http://127.0.0.1:18001",
                "http://127.0.0.1:18002",
                "http://127.0.0.1:18003",
                a,
                b,
                c);
    }

    @Test
    void classificationUsesPythonEndpointAndServiceIdentity() {
        server.expect(requestTo("http://127.0.0.1:18001/internal/v3/intents"))
                .andExpect(header("X-Agent-Key", KEY))
                .andExpect(header("X-Trace-Id", "trace-1"))
                .andExpect(jsonPath("$.protocolVersion").value("3.0"))
                .andExpect(jsonPath("$.input.text").value("厕所在哪"))
                .andExpect(jsonPath("$.text").doesNotExist())
                .andRespond(
                        withSuccess(
                                "{\"code\":\"OK\",\"message\":\"成功\",\"data\":{\"intent\":\"tourism\"}}",
                                MediaType.APPLICATION_JSON));
        assertThat(gateway.classify(new Message("u100", "厕所在哪", null, null), "trace-1"))
                .isEqualTo(Intent.tourism);
        server.verify();
    }

    @Test
    void messageUsesV2AndAcceptsNewOptionalResponseFields() {
        server.expect(requestTo("http://127.0.0.1:18001/internal/v3/messages"))
                .andExpect(jsonPath("$.input.text").value("你好"))
                .andExpect(jsonPath("$.protocolVersion").value("3.0"))
                .andExpect(jsonPath("$.traceId").doesNotExist())
                .andRespond(
                        withSuccess(
                                """
                    {"code":"OK","message":"成功","data":{"intent":"tourism",
                     "reply":{"text":"你好","speechRate":0.8,"audioUrl":null,"future":true},
                     "tools":[],"handoff":null,"future":{}}}
                    """,
                                MediaType.APPLICATION_JSON));
        var result =
                gateway.respond(
                        "a1",
                        new WireMessage("u100", "你好", Intent.tourism, null, "token", "trace"));
        assertThat(result.text()).isEqualTo("你好");
        server.verify();
    }

    @Test
    void timeoutIsSanitizedAndNeverRetried() {
        server.expect(anything())
                .andRespond(
                        request -> {
                            throw new SocketTimeoutException(KEY);
                        });
        assertThatThrownBy(() -> gateway.classify(new Message("u100", "测试", null, null), "trace-1"))
                .isInstanceOf(BusinessException.class)
                .hasMessageNotContaining(KEY)
                .hasNoCause()
                .satisfies(
                        error ->
                                assertThat(((BusinessException) error).status().value())
                                        .isEqualTo(504));
        server.verify();
    }

    @Test
    void invalidIntentAndEnvelopeFailInsteadOfLocalFallback() {
        server.expect(anything())
                .andRespond(
                        withSuccess(
                                "{\"code\":\"OK\",\"message\":\"成功\",\"data\":{\"intent\":\"unknown\"}}",
                                MediaType.APPLICATION_JSON));
        assertThatThrownBy(() -> gateway.classify(new Message("u100", "测试", null, null), "trace-1"))
                .isInstanceOf(BusinessException.class);
        server.verify();
    }

    @Test
    void serviceKeysAreIndependentAndPropertiesNeverPrintThem() {
        assertThat(properties(KEY, KEY + "2", KEY + "3").toString()).doesNotContain(KEY);
        assertThatThrownBy(() -> properties(KEY, KEY, KEY + "3"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> properties("", "", ""))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
