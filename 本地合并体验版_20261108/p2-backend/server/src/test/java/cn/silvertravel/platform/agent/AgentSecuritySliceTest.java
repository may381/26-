package cn.silvertravel.platform.agent;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import cn.silvertravel.platform.common.api.ContractJsonConfiguration;
import cn.silvertravel.platform.security.*;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(
        controllers = AgentController.class,
        excludeAutoConfiguration =
                org.springframework.boot.autoconfigure.security.servlet
                        .UserDetailsServiceAutoConfiguration.class,
        properties = {
            "app.security.mock-enabled=true",
            "agents.a1-api-key=fixture-a1-key-123456789",
            "agents.a2-api-key=fixture-a2-key-123456789",
            "agents.a3-api-key=fixture-a3-key-123456789"
        })
@ActiveProfiles("mock")
@Import({
    SecurityConfiguration.class,
    SecurityResponseWriter.class,
    ContractJsonConfiguration.class
})
class AgentSecuritySliceTest {
    @Autowired MockMvc mvc;
    @MockitoBean AgentMessageService messages;
    @MockitoBean AgentToolService tools;
    @MockitoBean AgentTaskService tasks;
    @MockitoBean AgentMemoryService memory;
    @MockitoBean AgentBusinessToolService business;

    @Test
    void v3RequiresVersionAndInputAndRejectsOldOrMixedFields() throws Exception {
        for (String body :
                List.of(
                        "{\"userId\":\"u100\",\"text\":\"你好\"}",
                        "{\"protocolVersion\":\"3.0\",\"userId\":\"u100\",\"input\":{\"text\":\"你好\"},\"text\":\"旧字段\"}",
                        "{\"protocolVersion\":\"3.0\",\"userId\":\"u100\",\"input\":null}")) {
            mvc.perform(
                            post("/api/v3/agent/messages")
                                    .header("X-Mock-Actor-Id", "u100")
                                    .header("X-Mock-Actor-Role", "ELDER")
                                    .header("Idempotency-Key", "validation-key")
                                    .contentType("application/json")
                                    .content(body))
                    .andExpect(status().isBadRequest());
        }
        for (String version : List.of("1.0")) {
            mvc.perform(
                            post("/api/v3/agent/messages")
                                    .header("X-Mock-Actor-Id", "u100")
                                    .header("X-Mock-Actor-Role", "ELDER")
                                    .header("Idempotency-Key", "validation-key")
                                    .contentType("application/json")
                                    .content(
                                            "{\"protocolVersion\":\""
                                                    + version
                                                    + "\",\"userId\":\"u100\",\"input\":{\"text\":\"你好\"}}"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.code").value("UNSUPPORTED_PROTOCOL_VERSION"));
        }
        verifyNoInteractions(tasks);
    }

    @Test
    void missingVersionAndToolVersionCannotSilentlyUseOldProtocol() throws Exception {
        mvc.perform(
                        post("/api/v3/agent/messages")
                                .header("X-Mock-Actor-Id", "u100")
                                .header("X-Mock-Actor-Role", "ELDER")
                                .header("Idempotency-Key", "validation-key")
                                .contentType("application/json")
                                .content("{\"userId\":\"u100\",\"input\":{\"text\":\"你好\"}}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_ARGUMENT"));
        mvc.perform(
                        post("/internal/agent/v3/tools")
                                .header("X-Agent-Key", "fixture-a1-key-123456789")
                                .header("X-Agent-Context", "unknown")
                                .contentType("application/json")
                                .content(
                                        "{\"protocolVersion\":\"1.0\",\"input\":{\"tool\":\"route.recommend\",\"args\":{}}}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_ARGUMENT"));
        verifyNoInteractions(tasks, memory, business);
    }

    @Test
    void missingActionFieldsAndMixedIdentityCannotInvokeTool() throws Exception {
        mvc.perform(
                        post("/internal/agent/v3/tools")
                                .header("X-Agent-Key", "fixture-a1-key-123456789")
                                .header("X-Agent-Context", "unknown")
                                .contentType("application/json")
                                .content(
                                        "{\"protocolVersion\":\"3.0\",\"input\":{\"tool\":\"route.recommend\",\"args\":{}}}"))
                .andExpect(status().isBadRequest());
        mvc.perform(
                        post("/internal/agent/v3/tools")
                                .header("X-Agent-Key", "fixture-a1-key-123456789")
                                .header("X-Agent-Context", "unknown")
                                .header("X-Mock-Actor-Id", "admin-operator-001")
                                .contentType("application/json")
                                .content(
                                        "{\"protocolVersion\":\"3.0\",\"input\":{\"tool\":\"route.recommend\",\"args\":{}}}"))
                .andExpect(status().isUnauthorized());
        verifyNoInteractions(memory, business);
    }

    @Test
    void missingKeyCannotReachTaskAcceptance() throws Exception {
        mvc.perform(
                        post("/api/v3/agent/messages")
                                .header("X-Mock-Actor-Id", "u100")
                                .header("X-Mock-Actor-Role", "ELDER")
                                .contentType("application/json")
                                .content(
                                        "{\"protocolVersion\":\"3.0\",\"userId\":\"u100\",\"input\":{\"text\":\"hello\"}}"))
                .andExpect(status().isBadRequest());
        verifyNoInteractions(tasks);
    }
}
