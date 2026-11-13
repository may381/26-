package cn.silvertravel.platform.profile;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.*;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("local")
@org.springframework.test.annotation.DirtiesContext(
        classMode = org.springframework.test.annotation.DirtiesContext.ClassMode.AFTER_CLASS)
@Testcontainers
@org.springframework.test.context.bean.override.mockito.MockitoBean(
        types = org.springframework.scheduling.TaskScheduler.class)
class ProfileFamilyIntegrationTest {
    @Container
    static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.4")
                    .withDatabaseName("profile_family_test")
                    .withUsername("test_app")
                    .withPassword("test_only_password")
                    // Fault-injection trigger needs no SUPER privilege when test-only binlog is
                    // disabled.
                    .withCommand("--skip-log-bin");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
    }

    private static final String PROFILE =
            """
            {"nickname":"王阿姨","age":68,"residence":"深圳","language":"普通话",
             "walkSpeed":"MEDIUM","walkDurationMin":40,"avoidSteps":true,
             "interests":["历史"],"interactionPreference":"VOICE",
             "emergencyContacts":[{"name":"王小明","phone":"138xxxx","relation":"儿子"}]}
            """;
    private static final String FAMILY =
            """
            {"name":"王小明","relation":"儿子","phone":"138xxxx"}
            """;
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void initializeOnlyIsolatedTestDatabase() throws Exception {
        jdbc.execute("DROP TRIGGER IF EXISTS fail_audit");
        jdbc.update("DELETE FROM family_relation");
        jdbc.update("DELETE FROM elder_profile");
        jdbc.update("DELETE FROM audit_log");
        elder(
                        patch("/api/v3/profile")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(PROFILE))
                .andExpect(status().isOk());
    }

    @Test
    void staleProfileVersionCannotOverwriteNewerChange() throws Exception {
        JsonNode before =
                data(
                        elder(get("/api/v3/profile").param("userId", "u100"))
                                .andExpect(status().isOk()));
        long version = before.path("version").asLong();
        assertThat(version).isPositive();
        JsonNode updated =
                data(
                        elder(
                                        patch("/api/v3/profile")
                                                .param("userId", "u100")
                                                .header("X-Expected-Profile-Version", version)
                                                .contentType(MediaType.APPLICATION_JSON)
                                                .content("{\"nickname\":\"版本测试\"}"))
                                .andExpect(status().isOk()));
        assertThat(updated.path("version").asLong()).isEqualTo(version + 1);
        elder(
                        patch("/api/v3/profile")
                                .param("userId", "u100")
                                .header("X-Expected-Profile-Version", version)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"nickname\":\"不应覆盖\"}"))
                .andExpect(status().isConflict());
        JsonNode after =
                data(
                        elder(get("/api/v3/profile").param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(after.path("nickname").asText()).isEqualTo("版本测试");
        assertThat(after.path("version").asLong()).isEqualTo(version + 1);
    }

    @Test
    void profileUsesUuidAndPatchPreservesUnspecifiedFields() throws Exception {
        JsonNode before =
                data(
                        elder(get("/api/v3/profile").param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(UUID.fromString(before.get("id").asText()).toString())
                .isEqualTo(before.get("id").asText());
        JsonNode updated =
                data(
                        elder(
                                        patch("/api/v3/profile")
                                                .param("userId", "u100")
                                                .contentType(MediaType.APPLICATION_JSON)
                                                .content(
                                                        "{\"walkDurationMin\":20,\"avoidSteps\":false}"))
                                .andExpect(status().isOk())
                                .andExpect(jsonPath("$.data.nickname").value("王阿姨"))
                                .andExpect(jsonPath("$.data.age").value(68))
                                .andExpect(jsonPath("$.data.avoidSteps").value(false))
                                .andExpect(jsonPath("$.data.walkDurationMin").value(20))
                                .andExpect(jsonPath("$.data.familyRelations").doesNotExist()));
        assertThat(updated.get("id")).isEqualTo(before.get("id"));
        assertThat(updated.get("emergencyContacts")).isEqualTo(before.get("emergencyContacts"));
        assertThat(count("audit_log")).isEqualTo(2);
    }

    @Test
    void emptyArraysExplicitlyClearLists() throws Exception {
        elder(
                        patch("/api/v3/profile")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"interests\":[],\"emergencyContacts\":[]}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.interests").isEmpty())
                .andExpect(jsonPath("$.data.emergencyContacts").isEmpty());
    }

    @ParameterizedTest
    @ValueSource(
            strings = {
                "{}",
                "[]",
                "null",
                "{\"id\":\"u101\"}",
                "{\"familyRelations\":[]}",
                "{\"age\":null}",
                "{\"age\":68.5}",
                "{\"walkDurationMin\":\"20\"}",
                "{\"walkDurationMin\":0}",
                "{\"avoidSteps\":\"true\"}",
                "{\"walkSpeed\":1}",
                "{\"walkSpeed\":\"slow\"}",
                "{\"interests\":[null]}",
                "{\"emergencyContacts\":[null]}",
                "{\"nickname\":123}",
                "{\"emergencyContacts\":[{\"name\":\"家属\",\"phone\":\"138xxxx\",\"relation\":\"儿子\",\"permissions\":{}}]}"
            })
    void rejectsInvalidPatchWithoutChangingProfileOrAudit(String body) throws Exception {
        elder(
                        patch("/api/v3/profile")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_ARGUMENT"));
        elder(get("/api/v3/profile").param("userId", "u100"))
                .andExpect(jsonPath("$.data.walkDurationMin").value(40));
        assertThat(count("audit_log")).isEqualTo(1);
    }

    @Test
    void initialProfileRequiresCompleteFieldsAndDoesNotInventDefaults() throws Exception {
        mvc.perform(
                        get("/api/v3/profile")
                                .param("userId", "u101")
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isNotFound());
        mvc.perform(
                        patch("/api/v3/profile")
                                .param("userId", "u101")
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"nickname\":\"李叔叔\"}"))
                .andExpect(status().isBadRequest());
        assertThat(count("elder_profile")).isEqualTo(1);
    }

    @Test
    void familyLifecycleKeepsBindingSeparateFromPermissions() throws Exception {
        String id = createFamily();
        elder(get("/api/v3/family-relations").param("userId", "u100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(1));
        elder(
                        patch("/api/v3/family-relations/" + id + "/permissions")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"shareAlert\":true}"))
                .andExpect(status().isConflict());
        elder(post("/api/v3/family-relations/" + id + "/approve").param("userId", "u100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("ACTIVE"))
                .andExpect(jsonPath("$.data.permissions.shareAlert").value(false));
        elder(post("/api/v3/family-relations/" + id + "/approve").param("userId", "u100"))
                .andExpect(status().isConflict());
        elder(
                        patch("/api/v3/family-relations/" + id + "/permissions")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"shareAlert\":true,\"shareLocation\":true}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.permissions.shareAlert").value(true))
                .andExpect(jsonPath("$.data.permissions.shareProgress").value(false));
        elder(
                        patch("/api/v3/family-relations/" + id + "/permissions")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"shareAlert\":false,\"shareLocation\":false}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("ACTIVE"));
        elder(post("/api/v3/family-relations/" + id + "/revoke").param("userId", "u100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("REVOKED"))
                .andExpect(jsonPath("$.data.permissions.shareLocation").value(false));
        elder(post("/api/v3/family-relations/" + id + "/revoke").param("userId", "u100"))
                .andExpect(status().isConflict());
        elder(
                        patch("/api/v3/family-relations/" + id + "/permissions")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"shareAlert\":true}"))
                .andExpect(status().isConflict());
        assertThat(count("audit_log")).isEqualTo(6);
    }

    @Test
    void ownerAndFamilyCannotOperateOtherEldersData() throws Exception {
        String id = createFamily();
        elder(get("/api/v3/profile").param("userId", "u101")).andExpect(status().isForbidden());
        mvc.perform(
                        get("/api/v3/profile")
                                .param("userId", "u100")
                                .header("X-Mock-Actor-Id", "family-operator-001")
                                .header("X-Mock-Actor-Role", "FAMILY"))
                .andExpect(status().isForbidden());
        mvc.perform(
                        post("/api/v3/family-relations/" + id + "/approve")
                                .param("userId", "u100")
                                .header("X-Mock-Actor-Id", "family-operator-001")
                                .header("X-Mock-Actor-Role", "FAMILY"))
                .andExpect(status().isForbidden());
        mvc.perform(
                        post("/api/v3/family-relations/" + id + "/approve")
                                .param("userId", "u101")
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isNotFound());
        assertThat(count("audit_log")).isEqualTo(2);
    }

    @ParameterizedTest
    @ValueSource(
            strings = {
                "{\"name\":\"儿子\",\"phone\":\"138xxxx\",\"relation\":\"儿子\",\"status\":\"ACTIVE\"}",
                "{\"name\":\"儿子\",\"phone\":\"138xxxx\",\"relation\":\"儿子\",\"permissions\":{\"shareAlert\":true}}",
                "{\"name\":\"\",\"phone\":\"138xxxx\",\"relation\":\"儿子\"}"
            })
    void familyCreationCannotAssignStatusOrPermissions(String body) throws Exception {
        elder(
                        post("/api/v3/family-relations")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(body))
                .andExpect(status().isBadRequest());
        assertThat(count("family_relation")).isZero();
    }

    @Test
    void concurrentApprovalsCommitOnlyOneTransitionAndAudit() throws Exception {
        String id = createFamily();
        CountDownLatch start = new CountDownLatch(1);
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            java.util.concurrent.Callable<Integer> approve =
                    () -> {
                        if (!start.await(10, TimeUnit.SECONDS)) {
                            throw new IllegalStateException("Start timed out");
                        }
                        return elder(
                                        post("/api/v3/family-relations/" + id + "/approve")
                                                .param("userId", "u100"))
                                .andReturn()
                                .getResponse()
                                .getStatus();
                    };
            var first = executor.submit(approve);
            var second = executor.submit(approve);
            start.countDown();
            assertThat(List.of(first.get(30, TimeUnit.SECONDS), second.get(30, TimeUnit.SECONDS)))
                    .containsExactlyInAnyOrder(200, 409);
        } finally {
            start.countDown();
        }
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM audit_log WHERE action = 'FAMILY_RELATION_APPROVED'",
                                Integer.class))
                .isEqualTo(1);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT status FROM family_relation WHERE id = ?",
                                String.class,
                                id))
                .isEqualTo("ACTIVE");
    }

    @ParameterizedTest
    @ValueSource(
            strings = {
                "{}",
                "{\"shareAlert\":null}",
                "{\"shareAlert\":\"true\"}",
                "{\"status\":\"REVOKED\"}",
                "{\"shareAlert\":1}"
            })
    void permissionPatchRejectsInvalidTypesAndMassAssignment(String body) throws Exception {
        String id = createFamily();
        elder(post("/api/v3/family-relations/" + id + "/approve").param("userId", "u100"))
                .andExpect(status().isOk());
        elder(
                        patch("/api/v3/family-relations/" + id + "/permissions")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(body))
                .andExpect(status().isBadRequest());
        assertThat(count("audit_log")).isEqualTo(3);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT share_alert FROM family_relation WHERE id = ?",
                                Boolean.class,
                                id))
                .isFalse();
    }

    @Test
    void auditFailureRollsBackProfileAndFamilyWrites() throws Exception {
        jdbc.execute(
                "CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log FOR EACH ROW "
                        + "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'test audit failure'");
        try {
            elder(
                            patch("/api/v3/profile")
                                    .param("userId", "u100")
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content("{\"walkDurationMin\":20}"))
                    .andExpect(status().isInternalServerError());
            elder(get("/api/v3/profile").param("userId", "u100"))
                    .andExpect(jsonPath("$.data.walkDurationMin").value(40));
            elder(
                            post("/api/v3/family-relations")
                                    .param("userId", "u100")
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content(FAMILY))
                    .andExpect(status().isInternalServerError());
            assertThat(count("family_relation")).isZero();
            assertThat(count("audit_log")).isEqualTo(1);
        } finally {
            jdbc.execute("DROP TRIGGER fail_audit");
        }
    }

    private String createFamily() throws Exception {
        return data(elder(
                                post("/api/v3/family-relations")
                                        .param("userId", "u100")
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(FAMILY))
                        .andExpect(status().isOk())
                        .andExpect(jsonPath("$.data.status").value("PENDING"))
                        .andExpect(jsonPath("$.data.permissions.shareLocation").value(false))
                        .andExpect(jsonPath("$.data.permissions.shareProgress").value(false))
                        .andExpect(jsonPath("$.data.permissions.shareAlert").value(false))
                        .andExpect(jsonPath("$.data.permissions.remotePlanning").value(false)))
                .get("id")
                .asText();
    }

    private ResultActions elder(MockHttpServletRequestBuilder request) throws Exception {
        return mvc.perform(
                request.header("X-Mock-Actor-Id", "u100").header("X-Mock-Actor-Role", "ELDER"));
    }

    private JsonNode data(ResultActions response) throws Exception {
        return json.readTree(response.andReturn().getResponse().getContentAsString()).get("data");
    }

    private int count(String table) {
        return jdbc.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
    }
}
