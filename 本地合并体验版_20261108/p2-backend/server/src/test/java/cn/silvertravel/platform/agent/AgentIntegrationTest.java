package cn.silvertravel.platform.agent;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.fasterxml.jackson.databind.*;
import java.util.List;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.*;
import org.springframework.test.web.servlet.*;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.*;

@SpringBootTest(
        properties = {
            "agents.mode=mock",
            "agents.a1-api-key=fixture-a1-key-123456789",
            "agents.a2-api-key=fixture-a2-key-123456789",
            "agents.a3-api-key=fixture-a3-key-123456789"
        })
@AutoConfigureMockMvc
@ActiveProfiles("local")
@org.springframework.test.annotation.DirtiesContext(
        classMode = org.springframework.test.annotation.DirtiesContext.ClassMode.AFTER_CLASS)
@Testcontainers
class AgentIntegrationTest {
    @Test
    void swaggerExposesPublicOperationsAndDocumentsBothMockHeaders() throws Exception {
        String specification =
                mvc.perform(get("/v3/api-docs/p2"))
                        .andExpect(status().isOk())
                        .andReturn()
                        .getResponse()
                        .getContentAsString();
        var document = json.readTree(specification);
        var paths = document.path("paths");
        int operations = 0;
        var fields = paths.fields();
        while (fields.hasNext()) {
            var path = fields.next();
            assertThat(path.getKey()).startsWith("/api/");
            for (String method : List.of("get", "post", "patch", "put", "delete")) {
                if (path.getValue().has(method)) operations++;
            }
        }
        assertThat(operations).isEqualTo(65);
        assertThat(document.at("/components/securitySchemes/actorId/name").asText())
                .isEqualTo("X-Mock-Actor-Id");
        assertThat(document.at("/components/securitySchemes/actorRole/name").asText())
                .isEqualTo("X-Mock-Actor-Role");
        assertThat(specification).doesNotContain("/internal/agent/", "fixture-a1-key-123456789");
        assertResponseFields(
                document,
                "/api/v3/help-events/{id}",
                "get",
                "businessStatus",
                "notifications",
                "locationNote");
        assertResponseFields(document, "/api/v3/trips/{id}", "get", "routeId", "status", "userId");
        assertResponseFields(
                document,
                "/api/v3/family-relations/{id}/approve",
                "post",
                "permissions",
                "phone",
                "relation");
        assertResponseFields(
                document, "/api/v3/routes/{id}/map", "get", "legs", "spots", "coordinateSystem");
        var schemas = document.path("components").path("schemas");
        for (var expected :
                java.util.Map.of(
                                "/api/v3/help-events", "locationNote",
                                "/api/v3/trips", "routeId",
                                "/api/v3/family-relations", "phone")
                        .entrySet()) {
            var schema =
                    document.path("paths")
                            .path(expected.getKey())
                            .path("post")
                            .path("requestBody")
                            .path("content")
                            .path("application/json")
                            .path("schema");
            if (schema.has("$ref"))
                schema =
                        schemas.path(
                                schema.path("$ref")
                                        .asText()
                                        .substring("#/components/schemas/".length()));
            assertThat(schema.path("properties").has(expected.getValue())).isTrue();
        }
        var patch =
                document.path("paths")
                        .path("/api/v3/profile")
                        .path("patch")
                        .path("requestBody")
                        .path("content")
                        .path("application/json")
                        .path("schema");
        assertThat(patch.path("properties").size()).isEqualTo(10);
        assertThat(patch.has("required")).isFalse();
        var permissions =
                document.path("paths")
                        .path("/api/v3/family-relations/{id}/permissions")
                        .path("patch")
                        .path("requestBody")
                        .path("content")
                        .path("application/json")
                        .path("schema");
        assertThat(permissions.path("properties").size()).isEqualTo(4);
    }

    private void assertResponseFields(
            JsonNode document, String path, String method, String... fields) {
        var schema =
                document.path("paths")
                        .path(path)
                        .path(method)
                        .path("responses")
                        .path("200")
                        .path("content")
                        .elements()
                        .next()
                        .path("schema");
        for (int depth = 0; depth < 5 && schema.has("$ref"); depth++) {
            schema =
                    document.path("components")
                            .path("schemas")
                            .path(
                                    schema.path("$ref")
                                            .asText()
                                            .substring("#/components/schemas/".length()));
        }
        schema = schema.path("properties").path("data");
        for (int depth = 0; depth < 5 && schema.has("$ref"); depth++) {
            schema =
                    document.path("components")
                            .path("schemas")
                            .path(
                                    schema.path("$ref")
                                            .asText()
                                            .substring("#/components/schemas/".length()));
        }
        for (String field : fields)
            assertThat(schema.path("properties").has(field)).as(path + " data." + field).isTrue();
    }

    @Container
    static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.4")
                    .withDatabaseName("agent_test")
                    .withUsername("test_app")
                    .withPassword("test_only_password");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", MYSQL::getJdbcUrl);
        r.add("spring.datasource.username", MYSQL::getUsername);
        r.add("spring.datasource.password", MYSQL::getPassword);
    }

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @Autowired AgentTaskExecutor executor;

    @org.springframework.test.context.bean.override.mockito.MockitoBean
    org.springframework.scheduling.TaskScheduler scheduler;

    @Test
    void acceptanceIsDurableAndDuplicateKeyDoesNotCreateAnotherTask() throws Exception {
        String key = java.util.UUID.randomUUID().toString();
        JsonNode first = accept("你好", key);
        JsonNode second = accept("你好", key);
        assertThat(first).isEqualTo(second);
        assertThat(first.path("taskStatus").asText()).isEqualTo("QUEUED");
        assertThat(first.path("reply").isNull()).isTrue();
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM agent_task WHERE id=?",
                                Integer.class,
                                first.path("taskId").asText()))
                .isEqualTo(1);
        executor.tick();
        JsonNode done = task(first);
        assertThat(done.path("status").asText()).isEqualTo("SUCCEEDED");
        assertThat(done.at("/reply/text").asText()).contains("模拟");
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM agent_invocation WHERE task_id=?",
                                Integer.class,
                                first.path("taskId").asText()))
                .isEqualTo(1);
        executor.tick();
        assertThat(task(first).path("version")).isEqualTo(done.path("version"));
    }

    @Test
    void changedPayloadCannotReuseSameKey() throws Exception {
        String key = java.util.UUID.randomUUID().toString();
        accept("第一次", key);
        send(body("不同内容"), key).andExpect(status().isConflict());
    }

    @Test
    void answerResumesOriginalTaskAndOldQuestionCannotBeAnsweredTwice() throws Exception {
        JsonNode accepted = accept("追问演示", java.util.UUID.randomUUID().toString());
        executor.tick();
        JsonNode waiting = task(accepted);
        assertThat(waiting.path("status").asText()).isEqualTo("WAITING_INPUT");
        JsonNode q = waiting.path("inputRequest");
        var answer =
                json.createObjectNode()
                        .put("protocolVersion", "3.0")
                        .put("userId", "u100")
                        .put("conversationId", accepted.path("conversationId").asText())
                        .put("continueTaskId", accepted.path("taskId").asText());
        var input = answer.putObject("input").put("text", "杭州");
        input.putObject("responseTo")
                .put("ownerTaskId", q.path("ownerTaskId").asText())
                .put("inputRequestId", q.path("inputRequestId").asText())
                .put("version", q.path("version").asLong());
        send(json.writeValueAsString(answer), java.util.UUID.randomUUID().toString())
                .andExpect(status().isOk());
        executor.tick();
        assertThat(task(accepted).path("status").asText()).isEqualTo("SUCCEEDED");
        send(json.writeValueAsString(answer), java.util.UUID.randomUUID().toString())
                .andExpect(status().isConflict());
    }

    @Test
    void lostResponseUsesReceiptWithoutResubmittingAgent() throws Exception {
        JsonNode accepted = accept("收据恢复演示", java.util.UUID.randomUUID().toString());
        executor.tick();
        assertThat(task(accepted).path("status").asText()).isEqualTo("SUCCEEDED");
        String id = accepted.path("taskId").asText();
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM agent_invocation WHERE task_id=?",
                                Integer.class,
                                id))
                .isEqualTo(1);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT receipt_attempts FROM agent_invocation WHERE task_id=?",
                                Integer.class,
                                id))
                .isEqualTo(1);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT state FROM agent_invocation WHERE task_id=?",
                                String.class,
                                id))
                .isEqualTo("FINISHED");
    }

    @Test
    void queuedCancellationPreventsDispatchAndReplaysSafely() throws Exception {
        JsonNode accepted = accept("取消演示", java.util.UUID.randomUUID().toString());
        String path = "/api/v3/agent/tasks/" + accepted.path("taskId").asText() + "/cancel";
        String key = java.util.UUID.randomUUID().toString();
        String body = "{\"expectedVersion\":1,\"reason\":\"测试取消\"}";
        for (int i = 0; i < 2; i++)
            mvc.perform(
                            post(path)
                                    .header("X-Mock-Actor-Id", "u100")
                                    .header("X-Mock-Actor-Role", "ELDER")
                                    .header("Idempotency-Key", key)
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content(body))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data.status").value("CANCELLED"));
        executor.tick();
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM agent_invocation WHERE task_id=?",
                                Integer.class,
                                accepted.path("taskId").asText()))
                .isZero();
    }

    @Test
    void taskAndInvocationQueriesDoNotExposeOtherOwnersOrCapabilities() throws Exception {
        JsonNode accepted = accept("隐私测试", java.util.UUID.randomUUID().toString());
        executor.tick();
        String path = "/api/v3/agent/tasks/" + accepted.path("taskId").asText();
        mvc.perform(
                        get(path)
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isNotFound());
        String ledger =
                mvc.perform(
                                get(path + "/invocations")
                                        .header("X-Mock-Actor-Id", "u100")
                                        .header("X-Mock-Actor-Role", "ELDER"))
                        .andExpect(status().isOk())
                        .andReturn()
                        .getResponse()
                        .getContentAsString();
        assertThat(ledger).doesNotContain("capabilityToken", "request_json", "fixture-a1-key");
    }

    @Autowired org.springframework.transaction.PlatformTransactionManager transactions;

    @Test
    void duplicateCompletionCannotOverwriteFinishedInvocation() throws Exception {
        JsonNode accepted = accept("重复回复演示", java.util.UUID.randomUUID().toString());
        executor.tick();
        String id = accepted.path("taskId").asText();
        var row =
                jdbc.queryForMap(
                        "SELECT request_json,response_json FROM agent_invocation WHERE task_id=?",
                        id);
        var request =
                (com.fasterxml.jackson.databind.node.ObjectNode)
                        json.readTree(row.get("request_json").toString());
        JsonNode response = json.readTree(row.get("response_json").toString());
        new org.springframework.transaction.support.TransactionTemplate(transactions)
                .executeWithoutResult(
                        status ->
                                org.springframework.test.util.ReflectionTestUtils.invokeMethod(
                                        executor, "finish", request, response));
        assertThat(
                        jdbc.queryForObject(
                                "SELECT state FROM agent_invocation WHERE task_id=?",
                                String.class,
                                id))
                .isEqualTo("FINISHED");
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM agent_message WHERE task_id=? AND role='assistant'",
                                Integer.class,
                                id))
                .isEqualTo(1);
    }

    @Test
    void expiredPersistedInvocationRecoversReceiptAfterWorkerInterruption() throws Exception {
        JsonNode accepted = accept("收据恢复演示", java.util.UUID.randomUUID().toString());
        String id = accepted.path("taskId").asText();
        var transaction =
                new org.springframework.transaction.support.TransactionTemplate(transactions);
        com.fasterxml.jackson.databind.node.ObjectNode request =
                transaction.execute(
                        status ->
                                org.springframework.test.util.ReflectionTestUtils.invokeMethod(
                                        executor, "claim", id));
        assertThatThrownBy(
                        () ->
                                org.springframework.test.util.ReflectionTestUtils.invokeMethod(
                                        executor, "call", request))
                .isInstanceOf(IllegalStateException.class);
        jdbc.update(
                "UPDATE agent_invocation SET deadline_at=? WHERE task_id=?",
                java.sql.Timestamp.from(java.time.Instant.now().minusSeconds(1)),
                id);
        executor.tick();
        assertThat(task(accepted).path("status").asText()).isEqualTo("SUCCEEDED");
        executor.tick();
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM agent_invocation WHERE task_id=?",
                                Integer.class,
                                id))
                .isEqualTo(1);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT receipt_attempts FROM agent_invocation WHERE task_id=?",
                                Integer.class,
                                id))
                .isEqualTo(1);
    }

    @Test
    void expiredInvocationWithoutReceiptFailsWithoutAutomaticResubmission() throws Exception {
        JsonNode accepted = accept("无收据中断演示", java.util.UUID.randomUUID().toString());
        String id = accepted.path("taskId").asText();
        new org.springframework.transaction.support.TransactionTemplate(transactions)
                .executeWithoutResult(
                        status ->
                                org.springframework.test.util.ReflectionTestUtils.invokeMethod(
                                        executor, "claim", id));
        jdbc.update(
                "UPDATE agent_invocation SET deadline_at=? WHERE task_id=?",
                java.sql.Timestamp.from(java.time.Instant.now().minusSeconds(1)),
                id);
        executor.tick();
        assertThat(task(accepted).path("phase").asText()).isEqualTo("RECONCILIATION_REQUIRED");
        assertThat(task(accepted).at("/error/code").asText()).isEqualTo("INVOCATION_UNRESOLVED");
        executor.tick();
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM agent_invocation WHERE task_id=?",
                                Integer.class,
                                id))
                .isEqualTo(1);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT state FROM agent_invocation WHERE task_id=?",
                                String.class,
                                id))
                .isEqualTo("UNKNOWN");
    }

    @Test
    void finishedInvocationCapabilityCannotBeUsedForNewToolCalls() throws Exception {
        JsonNode accepted = accept("凭证生命周期演示", java.util.UUID.randomUUID().toString());
        executor.tick();
        String id = accepted.path("taskId").asText();
        JsonNode request =
                json.readTree(
                        jdbc.queryForObject(
                                "SELECT request_json FROM agent_invocation WHERE task_id=?",
                                String.class,
                                id));
        var body =
                json.createObjectNode()
                        .put("protocolVersion", "3.0")
                        .put("taskId", id)
                        .put("stepId", "unregistered")
                        .put("actionId", "unregistered");
        body.putObject("input")
                .put("tool", "knowledge.search")
                .putObject("args")
                .put("query", "厕所");
        mvc.perform(
                        post("/internal/agent/v3/tools")
                                .header("X-Agent-Key", "fixture-a1-key-123456789")
                                .header("X-Agent-Context", request.path("capabilityToken").asText())
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(json.writeValueAsString(body)))
                .andExpect(status().isForbidden());
    }

    private String body(String text) throws Exception {
        var b = json.createObjectNode().put("protocolVersion", "3.0").put("userId", "u100");
        b.putObject("input").put("text", text);
        return json.writeValueAsString(b);
    }

    private JsonNode accept(String text, String key) throws Exception {
        return json.readTree(
                        send(body(text), key)
                                .andExpect(status().isOk())
                                .andReturn()
                                .getResponse()
                                .getContentAsString())
                .path("data");
    }

    private JsonNode task(JsonNode accepted) throws Exception {
        return json.readTree(
                        mvc.perform(
                                        get("/api/v3/agent/tasks/"
                                                        + accepted.path("taskId").asText())
                                                .header("X-Mock-Actor-Id", "u100")
                                                .header("X-Mock-Actor-Role", "ELDER"))
                                .andExpect(status().isOk())
                                .andReturn()
                                .getResponse()
                                .getContentAsString())
                .path("data");
    }

    private ResultActions send(String body, String key) throws Exception {
        return mvc.perform(
                post("/api/v3/agent/messages")
                        .header("X-Mock-Actor-Id", "u100")
                        .header("X-Mock-Actor-Role", "ELDER")
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body));
    }
}
