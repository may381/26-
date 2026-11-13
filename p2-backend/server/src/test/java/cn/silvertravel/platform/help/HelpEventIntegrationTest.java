package cn.silvertravel.platform.help;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import cn.silvertravel.platform.notification.MockNotificationService;
import com.fasterxml.jackson.databind.*;
import java.util.List;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.*;
import org.springframework.test.web.servlet.*;
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
class HelpEventIntegrationTest {
    @Container
    static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.4")
                    .withDatabaseName("help_event_test")
                    .withUsername("test_app")
                    .withPassword("test_only_password")
                    .withCommand("--skip-log-bin");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
    }

    private static final String REQUEST =
            """
            {"userId":"u100","tripId":null,"type":"UNWELL","location":null,"locationNote":"入口附近不舒服"}
            """;
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @Autowired MockNotificationService mockNotifications;

    @BeforeEach
    void resetOnlyIsolatedTestDatabase() {
        jdbc.execute("DROP TRIGGER IF EXISTS fail_audit");
        jdbc.update("DELETE FROM help_notification");
        jdbc.update("DELETE FROM help_event");
        jdbc.update("DELETE FROM idempotency_request");
        jdbc.update("DELETE FROM trip");
        jdbc.update("DELETE FROM family_relation");
        jdbc.update("DELETE FROM elder_profile");
        jdbc.update("DELETE FROM audit_log");
    }

    @Test
    void noProfileOrTripRequiredAndNotificationsNeverMeanAcknowledgement() throws Exception {
        String id = create(null).get("id").asText();
        assertThat(count("elder_profile")).isZero();
        elder(get("/api/v3/help-events/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.businessStatus").value("OPEN"))
                .andExpect(jsonPath("$.data.tripId").isEmpty())
                .andExpect(jsonPath("$.data.notifications[0].recipientType").value("official"))
                .andExpect(jsonPath("$.data.notifications[0].status").value("PENDING"));
        mockNotifications.advance();
        elder(get("/api/v3/help-events/" + id))
                .andExpect(jsonPath("$.data.notifications[0].status").value("SENT"));
        mockNotifications.advance();
        elder(get("/api/v3/help-events/" + id))
                .andExpect(jsonPath("$.data.notifications[0].status").value("DELIVERED"))
                .andExpect(jsonPath("$.data.businessStatus").value("OPEN"));
    }

    @Test
    void spotLocationDispatchesToScenicAndCoordinateInputStaysSeparate() throws Exception {
        JsonNode spot =
                data(
                        elder(
                                        post("/api/v3/help-events")
                                                .contentType(MediaType.APPLICATION_JSON)
                                                .content(
                                                        """
                {"userId":"u100","type":"LOST","location":{"spotId":"spot-003"}}
                """))
                                .andExpect(status().isOk()));
        assertThat(spot.get("location").size()).isEqualTo(1);
        assertThat(spot.get("notifications").get(0).get("recipientType").asText())
                .isEqualTo("scenic");
        elder(
                        post("/api/v3/help-events")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(
                                        """
                {"userId":"u100","type":"SOS","location":{"lat":22.58,"lng":114.06}}
                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.location.lat").value(22.58));
    }

    @ParameterizedTest
    @ValueSource(
            strings = {
                "{}",
                "{\"userId\":\"u100\",\"type\":\"SOS\"}",
                "{\"userId\":\"u100\",\"type\":\"SOS\",\"locationNote\":\"  \"}",
                "{\"userId\":\"u100\",\"type\":\"SOS\",\"location\":{}}",
                "{\"userId\":\"u100\",\"type\":\"SOS\",\"location\":{\"lat\":22}}",
                "{\"userId\":\"u100\",\"type\":\"SOS\",\"location\":{\"lat\":91,\"lng\":114}}",
                "{\"userId\":\"u100\",\"type\":\"SOS\",\"location\":{\"lat\":22,\"lng\":114,\"spotId\":\"spot-003\"}}",
                "{\"userId\":\"u100\",\"type\":\"SOS\",\"location\":{\"spotId\":\"unknown\"}}",
                "{\"userId\":\"u100\",\"type\":\"UNKNOWN\",\"locationNote\":\"入口\"}",
                "{\"userId\":\"u100\",\"type\":0,\"locationNote\":\"入口\"}",
                "{\"userId\":\"u100\",\"type\":\"SOS\",\"locationNote\":\"入口\",\"businessStatus\":\"RESOLVED\"}",
                "{\"userId\":\"u100\",\"type\":\"SOS\",\"locationNote\":\"入口\",\"notifications\":[]}",
                "{\"userId\":\"u100\",\"type\":\"SOS\",\"locationNote\":\"入口\",\"tripId\":\" \"}"
            })
    void invalidRequestsDoNotWriteAnything(String request) throws Exception {
        elder(post("/api/v3/help-events").contentType(MediaType.APPLICATION_JSON).content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_ARGUMENT"));
        assertThat(count("help_event")).isZero();
        assertThat(count("help_notification")).isZero();
        assertThat(count("audit_log")).isZero();
    }

    @Test
    void callerCannotForgeUserOrForeignTripAndListIsScoped() throws Exception {
        String own = create(null).get("id").asText();
        mvc.perform(
                        post("/api/v3/help-events")
                                .contentType(MediaType.APPLICATION_JSON)
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER")
                                .content(REQUEST))
                .andExpect(status().isForbidden());
        elder(
                        post("/api/v3/help-events")
                                .param("userId", "u101")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(REQUEST))
                .andExpect(status().isBadRequest());
        mvc.perform(
                        get("/api/v3/help-events/" + own)
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isNotFound());
        mvc.perform(
                        get("/api/v3/help-events")
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").isEmpty());
        role(get("/api/v3/help-events"), "family-operator-001", "FAMILY")
                .andExpect(status().isForbidden());
        role(get("/api/v3/help-events"), "scenic-operator-001", "SCENIC")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(1));
        String tripId = trip();
        String foreign =
                "{\"userId\":\"u101\",\"tripId\":\""
                        + tripId
                        + "\",\"type\":\"GENERAL\",\"locationNote\":\"入口\"}";
        mvc.perform(
                        post("/api/v3/help-events")
                                .contentType(MediaType.APPLICATION_JSON)
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER")
                                .content(foreign))
                .andExpect(status().isNotFound());
    }

    @Test
    void statusMachineRequiresActualHandlerOrAdminAndQueuesEachPhase() throws Exception {
        String id = create(null).get("id").asText();
        elder(post("/api/v3/help-events/" + id + "/acknowledge")).andExpect(status().isForbidden());
        role(post("/api/v3/help-events/" + id + "/resolve"), "admin-operator-001", "ADMIN")
                .andExpect(status().isConflict());
        role(post("/api/v3/help-events/" + id + "/acknowledge"), "scenic-operator-001", "SCENIC")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.businessStatus").value("ACKNOWLEDGED"));
        role(post("/api/v3/help-events/" + id + "/acknowledge"), "scenic-operator-002", "SCENIC")
                .andExpect(status().isConflict());
        role(post("/api/v3/help-events/" + id + "/resolve"), "scenic-operator-002", "SCENIC")
                .andExpect(status().isForbidden());
        role(post("/api/v3/help-events/" + id + "/resolve"), "admin-operator-001", "ADMIN")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.businessStatus").value("RESOLVED"));
        role(post("/api/v3/help-events/" + id + "/resolve"), "scenic-operator-001", "SCENIC")
                .andExpect(status().isConflict());
        assertThat(count("help_notification")).isEqualTo(3);
        assertThat(count("audit_log")).isEqualTo(3);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT handler_actor_id FROM help_event WHERE id=?",
                                String.class,
                                id))
                .isEqualTo("scenic-operator-001");
    }

    @Test
    void concurrentAcknowledgementHasOneWinner() throws Exception {
        String id = create(null).get("id").asText();
        var start = new CountDownLatch(1);
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            var first =
                    executor.submit(
                            () -> {
                                start.await(10, TimeUnit.SECONDS);
                                return role(
                                                post("/api/v3/help-events/" + id + "/acknowledge"),
                                                "scenic-operator-001",
                                                "SCENIC")
                                        .andReturn()
                                        .getResponse()
                                        .getStatus();
                            });
            var second =
                    executor.submit(
                            () -> {
                                start.await(10, TimeUnit.SECONDS);
                                return role(
                                                post("/api/v3/help-events/" + id + "/acknowledge"),
                                                "scenic-operator-002",
                                                "SCENIC")
                                        .andReturn()
                                        .getResponse()
                                        .getStatus();
                            });
            start.countDown();
            assertThat(List.of(first.get(30, TimeUnit.SECONDS), second.get(30, TimeUnit.SECONDS)))
                    .containsExactlyInAnyOrder(200, 409);
        } finally {
            start.countDown();
        }
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM audit_log WHERE action='HELP_ACKNOWLEDGED'",
                                Integer.class))
                .isEqualTo(1);
        assertThat(count("help_notification")).isEqualTo(2);
    }

    @Test
    void idempotentReplayReturnsOriginalSnapshotAndChangedPayloadConflicts() throws Exception {
        JsonNode first = create("request-001");
        String id = first.get("id").asText();
        mockNotifications.advance();
        mockNotifications.advance();
        role(post("/api/v3/help-events/" + id + "/acknowledge"), "scenic-operator-001", "SCENIC")
                .andExpect(status().isOk());
        assertThat(create("request-001")).isEqualTo(first);
        elder(
                        post("/api/v3/help-events")
                                .header("Idempotency-Key", "request-001")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(REQUEST.replace("UNWELL", "SOS")))
                .andExpect(status().isConflict());
        assertThat(count("help_event")).isEqualTo(1);
        assertThat(count("idempotency_request")).isEqualTo(1);
    }

    @Test
    void concurrentIdempotencyCreatesOneEventAndActorScopesAreIndependent() throws Exception {
        var start = new CountDownLatch(1);
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Callable<String> action =
                    () -> {
                        start.await(10, TimeUnit.SECONDS);
                        return create("parallel-key").get("id").asText();
                    };
            var a = executor.submit(action);
            var b = executor.submit(action);
            start.countDown();
            assertThat(a.get(30, TimeUnit.SECONDS)).isEqualTo(b.get(30, TimeUnit.SECONDS));
        } finally {
            start.countDown();
        }
        assertThat(count("help_event")).isEqualTo(1);
        assertThat(count("help_notification")).isEqualTo(1);
        mvc.perform(
                        post("/api/v3/help-events")
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER")
                                .header("Idempotency-Key", "parallel-key")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(REQUEST.replace("u100", "u101")))
                .andExpect(status().isOk());
        assertThat(count("help_event")).isEqualTo(2);
    }

    @Test
    void legacyNoKeyAndExpiredKeyAllowNewHelpWithoutContentDeduplication() throws Exception {
        String a = create(null).get("id").asText();
        assertThat(create(null).get("id").asText()).isNotEqualTo(a);
        String original = create("expired-key").get("id").asText();
        jdbc.update(
                "UPDATE idempotency_request SET expires_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 SECOND)");
        assertThat(create("expired-key").get("id").asText()).isNotEqualTo(original);
        elder(
                        post("/api/v3/help-events")
                                .header("Idempotency-Key", "not valid")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(REQUEST))
                .andExpect(status().isBadRequest());
        assertThat(count("help_event")).isEqualTo(4);
    }

    @Test
    void onlyActiveAlertAuthorizedFamilyGetsNotificationAndRevocationBlocksDelivery()
            throws Exception {
        String family = family();
        String pendingHelp = create(null).get("id").asText();
        assertThat(count("help_notification")).isEqualTo(1);
        elder(post("/api/v3/family-relations/" + family + "/approve").param("userId", "u100"))
                .andExpect(status().isOk());
        create(null);
        assertThat(count("help_notification")).isEqualTo(2);
        elder(
                        patch("/api/v3/family-relations/" + family + "/permissions")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"shareAlert\":true}"))
                .andExpect(status().isOk());
        String authorizedHelp = create(null).get("id").asText();
        assertThat(count("help_notification")).isEqualTo(4);
        mockNotifications.advance();
        elder(post("/api/v3/family-relations/" + family + "/revoke").param("userId", "u100"))
                .andExpect(status().isOk());
        mockNotifications.advance();
        assertThat(
                        jdbc.queryForObject(
                                "SELECT status FROM help_notification WHERE help_event_id=? AND recipient_type='family'",
                                String.class,
                                authorizedHelp))
                .isEqualTo("FAILED");
        elder(get("/api/v3/help-events/" + authorizedHelp))
                .andExpect(jsonPath("$.data.businessStatus").value("OPEN"));
        role(
                        post("/api/v3/help-events/" + authorizedHelp + "/acknowledge"),
                        "scenic-operator-001",
                        "SCENIC")
                .andExpect(status().isOk());
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM help_notification WHERE recipient_type='family'",
                                Integer.class))
                .isEqualTo(1);
        assertThat(pendingHelp).isNotEqualTo(authorizedHelp);
    }

    @Test
    void auditFailureAlsoRollsBackAcknowledgementAndResolutionOutbox() throws Exception {
        String id = create(null).get("id").asText();
        jdbc.execute(
                "CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log FOR EACH ROW "
                        + "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test audit failure'");
        try {
            role(
                            post("/api/v3/help-events/" + id + "/acknowledge"),
                            "scenic-operator-001",
                            "SCENIC")
                    .andExpect(status().isInternalServerError());
            elder(get("/api/v3/help-events/" + id))
                    .andExpect(jsonPath("$.data.businessStatus").value("OPEN"));
            assertThat(
                            jdbc.queryForObject(
                                    "SELECT handler_actor_id FROM help_event WHERE id=?",
                                    String.class,
                                    id))
                    .isNull();
            assertThat(count("help_notification")).isEqualTo(1);
        } finally {
            jdbc.execute("DROP TRIGGER fail_audit");
        }
        role(post("/api/v3/help-events/" + id + "/acknowledge"), "scenic-operator-001", "SCENIC")
                .andExpect(status().isOk());
        jdbc.execute(
                "CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log FOR EACH ROW "
                        + "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test audit failure'");
        try {
            role(post("/api/v3/help-events/" + id + "/resolve"), "scenic-operator-001", "SCENIC")
                    .andExpect(status().isInternalServerError());
            elder(get("/api/v3/help-events/" + id))
                    .andExpect(jsonPath("$.data.businessStatus").value("ACKNOWLEDGED"));
            assertThat(count("help_notification")).isEqualTo(2);
            assertThat(count("audit_log")).isEqualTo(2);
        } finally {
            jdbc.execute("DROP TRIGGER fail_audit");
        }
    }

    @Test
    void auditFailureRollsBackHelpOutboxAndIdempotencyAndAllowsRetry() throws Exception {
        jdbc.execute(
                "CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log FOR EACH ROW "
                        + "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test audit failure'");
        try {
            elder(
                            post("/api/v3/help-events")
                                    .header("Idempotency-Key", "rollback-key")
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content(REQUEST))
                    .andExpect(status().isInternalServerError());
            assertThat(count("help_event")).isZero();
            assertThat(count("help_notification")).isZero();
            assertThat(count("idempotency_request")).isZero();
        } finally {
            jdbc.execute("DROP TRIGGER fail_audit");
        }
        create("rollback-key");
        assertThat(count("help_event")).isEqualTo(1);
    }

    private String trip() throws Exception {
        profile();
        return data(elder(
                                post("/api/v3/trips")
                                        .param("userId", "u100")
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content("{\"routeId\":\"r1\"}"))
                        .andExpect(status().isOk()))
                .get("id")
                .asText();
    }

    private void profile() throws Exception {
        elder(
                        patch("/api/v3/profile")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(
                                        """
                {"nickname":"王阿姨","age":68,"residence":"深圳","language":"普通话","walkSpeed":"MEDIUM",
                "walkDurationMin":40,"avoidSteps":true,"interests":[],"interactionPreference":"VOICE","emergencyContacts":[]}
                """))
                .andExpect(status().isOk());
    }

    private String family() throws Exception {
        profile();
        return data(elder(
                                post("/api/v3/family-relations")
                                        .param("userId", "u100")
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(
                                                "{\"name\":\"家属\",\"relation\":\"儿子\",\"phone\":\"138xxxx\"}"))
                        .andExpect(status().isOk()))
                .get("id")
                .asText();
    }

    private JsonNode create(String key) throws Exception {
        var request =
                post("/api/v3/help-events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(REQUEST);
        if (key != null) request.header("Idempotency-Key", key);
        return data(
                elder(request)
                        .andExpect(status().isOk())
                        .andExpect(
                                jsonPath("$.message")
                                        .value(org.hamcrest.Matchers.containsString("模拟"))));
    }

    private ResultActions elder(MockHttpServletRequestBuilder request) throws Exception {
        return role(request, "u100", "ELDER");
    }

    private ResultActions role(MockHttpServletRequestBuilder request, String id, String role)
            throws Exception {
        return mvc.perform(request.header("X-Mock-Actor-Id", id).header("X-Mock-Actor-Role", role));
    }

    private JsonNode data(ResultActions response) throws Exception {
        return json.readTree(response.andReturn().getResponse().getContentAsString()).get("data");
    }

    private int count(String table) {
        return jdbc.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
    }
}
