package cn.silvertravel.platform.trip;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.fasterxml.jackson.databind.*;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
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
class TravelRecordIntegrationTest {
    @Container
    static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.4")
                    .withDatabaseName("travel_record_test")
                    .withUsername("test_app")
                    .withPassword("test_only_password")
                    .withCommand("--skip-log-bin");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", MYSQL::getJdbcUrl);
        r.add("spring.datasource.username", MYSQL::getUsername);
        r.add("spring.datasource.password", MYSQL::getPassword);
    }

    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper json;
    private static final String BODY =
            "{\"effort\":\"TIRED\",\"comfortableWalkMin\":40,\"note\":\"接口测试反馈\"}";

    @BeforeEach
    void resetOnlyIsolatedDatabase() throws Exception {
        jdbc.execute("DROP TRIGGER IF EXISTS fail_feedback_audit");
        for (String table :
                List.of(
                        "help_notification",
                        "help_event",
                        "idempotency_request",
                        "trip_feedback",
                        "trip",
                        "family_identity_link",
                        "family_relation",
                        "elder_profile",
                        "audit_log")) jdbc.update("DELETE FROM " + table);
        for (String user : List.of("u100", "u101"))
            call(
                            patch("/api/v3/profile")
                                    .param("userId", user)
                                    .contentType("application/json")
                                    .content(
                                            """
            {"nickname":"演示老人","age":68,"residence":"演示城市","language":"普通话","walkSpeed":"MEDIUM","walkDurationMin":60,"avoidSteps":false,"interests":[],"interactionPreference":"VOICE","emergencyContacts":[]}
            """),
                            user,
                            "ELDER")
                    .andExpect(status().isOk());
    }

    @Test
    void onlyFinishedOwnTripsBecomeRecordsAndNoVisitsAreInvented() throws Exception {
        assertThat(
                        data(elder(get("/api/v3/travel-records").param("userId", "u100"))
                                        .andExpect(status().isOk()))
                                .path("items")
                                .size())
                .isZero();
        String id = create("u100");
        elder(get("/api/v3/travel-records/" + id).param("userId", "u100"))
                .andExpect(status().isNotFound());
        finish("u100", id);
        String foreign = create("u101");
        finish("u101", foreign);
        String snapshot =
                jdbc.queryForObject("SELECT route_snapshot FROM trip WHERE id=?", String.class, id);
        var saved = (com.fasterxml.jackson.databind.node.ObjectNode) json.readTree(snapshot);
        saved.put("name", "开始时保存的路线快照");
        jdbc.update(
                "UPDATE trip SET route_snapshot=?,created_at=?,finished_at=? WHERE id=?",
                json.writeValueAsString(saved),
                Timestamp.from(Instant.parse("2026-10-01T00:00:00Z")),
                Timestamp.from(Instant.parse("2026-10-01T01:00:00Z")),
                id);
        var page =
                data(
                        elder(get("/api/v3/travel-records").param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(page.path("items").size()).isEqualTo(1);
        assertThat(page.path("nextCursor").isNull()).isTrue();
        var detail =
                data(
                        elder(get("/api/v3/travel-records/" + id).param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(detail.path("id").asText()).isEqualTo(id);
        assertThat(detail.path("routeName").asText()).isEqualTo("开始时保存的路线快照");
        assertThat(detail.path("durationSeconds").asLong()).isEqualTo(3600);
        assertThat(detail.path("plannedSpotIds").size()).isGreaterThan(1);
        assertThat(detail.path("visitedSpotIds").size()).isZero();
        assertThat(detail.path("visitedEvidence").asText()).isEqualTo("NONE");
        assertThat(detail.path("progressAvailable").asBoolean()).isFalse();
        assertThat(detail.path("feedback").isNull()).isTrue();
    }

    @Test
    void cursorPaginationIsStableForEqualTimestampsAndScopedToOwner() throws Exception {
        var ids = new ArrayList<String>();
        for (int i = 0; i < 3; i++) {
            String id = create("u100");
            finish("u100", id);
            ids.add(id);
        }
        jdbc.update(
                "UPDATE trip SET created_at=?,finished_at=? WHERE user_id='u100'",
                Timestamp.from(Instant.parse("2026-10-01T00:00:00Z")),
                Timestamp.from(Instant.parse("2026-10-01T01:00:00Z")));
        ids.sort(Comparator.reverseOrder());
        var seen = new ArrayList<String>();
        String cursor = null, firstCursor = null;
        for (int i = 0; i < 3; i++) {
            var request = get("/api/v3/travel-records").param("userId", "u100").param("limit", "1");
            if (cursor != null) request.param("cursor", cursor);
            var page = data(elder(request).andExpect(status().isOk()));
            seen.add(page.path("items").get(0).path("id").asText());
            cursor = page.path("nextCursor").isNull() ? null : page.path("nextCursor").asText();
            if (i == 0) firstCursor = cursor;
        }
        assertThat(seen).containsExactlyElementsOf(ids);
        assertThat(cursor).isNull();
        call(
                        get("/api/v3/travel-records")
                                .param("userId", "u101")
                                .param("cursor", firstCursor),
                        "u101",
                        "ELDER")
                .andExpect(status().isBadRequest());
        for (String value : List.of("0", "101"))
            elder(get("/api/v3/travel-records").param("userId", "u100").param("limit", value))
                    .andExpect(status().isBadRequest());
        for (String value : List.of("bad!", "", "e30"))
            elder(get("/api/v3/travel-records").param("userId", "u100").param("cursor", value))
                    .andExpect(status().isBadRequest());
        String extreme =
                Base64.getUrlEncoder()
                        .withoutPadding()
                        .encodeToString(
                                json.writeValueAsBytes(
                                        Map.of(
                                                "userId",
                                                "u100",
                                                "id",
                                                ids.getFirst(),
                                                "finishedAt",
                                                Instant.MAX.toString())));
        elder(get("/api/v3/travel-records").param("userId", "u100").param("cursor", extreme))
                .andExpect(status().isBadRequest());
    }

    @Test
    void feedbackIsIdempotentAndDoesNotMutateProfileOrMemory() throws Exception {
        String id = create("u100");
        finish("u100", id);
        var profile =
                data(
                        elder(get("/api/v3/profile").param("userId", "u100"))
                                .andExpect(status().isOk()));
        var first = data(feedback(id, "stable", BODY).andExpect(status().isOk()));
        var second = data(feedback(id, "stable", BODY).andExpect(status().isOk()));
        assertThat(second).isEqualTo(first);
        assertThat(first.path("profileUpdated").asBoolean()).isFalse();
        assertThat(first.path("memoryWritten").asBoolean()).isFalse();
        assertThat(
                        data(
                                elder(get("/api/v3/profile").param("userId", "u100"))
                                        .andExpect(status().isOk())))
                .isEqualTo(profile);
        assertThat(
                        data(elder(get("/api/v3/travel-records/" + id).param("userId", "u100"))
                                        .andExpect(status().isOk()))
                                .path("feedback"))
                .isEqualTo(first);
        assertThat(
                        data(elder(get("/api/v3/travel-records").param("userId", "u100"))
                                        .andExpect(status().isOk()))
                                .path("items")
                                .get(0)
                                .path("feedbackSubmitted")
                                .asBoolean())
                .isTrue();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM trip_feedback", Integer.class))
                .isEqualTo(1);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM audit_log WHERE action='TRIP_FEEDBACK_CREATED'",
                                Integer.class))
                .isEqualTo(1);
    }

    @Test
    void duplicateAndCrossTripKeysCannotCreateAnotherFeedback() throws Exception {
        String id = create("u100");
        finish("u100", id);
        feedback(id, "stable", BODY).andExpect(status().isOk());
        feedback(id, "stable", BODY.replace("40", "30")).andExpect(status().isConflict());
        feedback(id, "new-key", BODY).andExpect(status().isConflict());
        String other = create("u100");
        finish("u100", other);
        feedback(other, "stable", BODY).andExpect(status().isConflict());
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM trip_feedback", Integer.class))
                .isEqualTo(1);
    }

    @Test
    void activeOrForeignTripsAndWrongRolesAreRejected() throws Exception {
        String id = create("u100");
        feedback(id, "active", BODY).andExpect(status().isConflict());
        String foreign = create("u101");
        finish("u101", foreign);
        elder(get("/api/v3/travel-records/" + foreign).param("userId", "u100"))
                .andExpect(status().isNotFound());
        feedback(foreign, "foreign", BODY).andExpect(status().isNotFound());
        elder(get("/api/v3/travel-records").param("userId", "u101"))
                .andExpect(status().isForbidden());
        for (var actor :
                Map.of(
                                "family-operator-001",
                                "FAMILY",
                                "scenic-operator-001",
                                "SCENIC",
                                "admin-operator-001",
                                "ADMIN")
                        .entrySet()) {
            call(
                            get("/api/v3/travel-records").param("userId", "u100"),
                            actor.getKey(),
                            actor.getValue())
                    .andExpect(status().isForbidden());
            call(
                            post("/api/v3/trips/" + id + "/feedback")
                                    .param("userId", "u100")
                                    .header("Idempotency-Key", "role")
                                    .contentType("application/json")
                                    .content(BODY),
                            actor.getKey(),
                            actor.getValue())
                    .andExpect(status().isForbidden());
        }
        mvc.perform(get("/api/v3/travel-records").param("userId", "u100"))
                .andExpect(status().isUnauthorized());
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM trip_feedback", Integer.class))
                .isZero();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM idempotency_request", Integer.class))
                .isZero();
    }

    @Test
    void feedbackValidatesTypesBoundsUnknownFieldsAndRequiredKey() throws Exception {
        String id = create("u100");
        finish("u100", id);
        elder(
                        post("/api/v3/trips/" + id + "/feedback")
                                .param("userId", "u100")
                                .contentType("application/json")
                                .content(BODY))
                .andExpect(status().isBadRequest());
        for (String body :
                List.of(
                        "{}",
                        "{\"effort\":\"tired\"}",
                        BODY.replace("40", "0"),
                        BODY.replace("40", "1441"),
                        BODY.replace("40", "40.5"),
                        BODY.replace("40", "\"40\""),
                        BODY.replace("\"effort\"", "\"confirmed\":true,\"effort\""),
                        json.writeValueAsString(
                                Map.of("effort", "TIRED", "note", "x".repeat(501)))))
            feedback(id, "invalid", body).andExpect(status().isBadRequest());
        var accepted =
                data(
                        feedback(id, "valid", "{\"effort\":\"COMFORTABLE\",\"note\":\"  \"}")
                                .andExpect(status().isOk()));
        assertThat(accepted.path("comfortableWalkMin").isNull()).isTrue();
        assertThat(accepted.path("note").isNull()).isTrue();
        elder(get("/api/v3/travel-records/not-uuid").param("userId", "u100"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void sameKeyConcurrentSubmissionsReplayOneFeedback() throws Exception {
        String id = create("u100");
        finish("u100", id);
        var start = new CountDownLatch(1);
        try (var executor = Executors.newFixedThreadPool(2)) {
            Callable<JsonNode> action =
                    () -> {
                        start.await();
                        return data(feedback(id, "concurrent", BODY).andExpect(status().isOk()));
                    };
            var first = executor.submit(action);
            var second = executor.submit(action);
            start.countDown();
            assertThat(first.get(15, TimeUnit.SECONDS)).isEqualTo(second.get(15, TimeUnit.SECONDS));
        }
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM trip_feedback", Integer.class))
                .isEqualTo(1);
    }

    @Test
    void distinctConcurrentKeysStillAllowOnlyOneFeedbackPerTrip() throws Exception {
        String id = create("u100");
        finish("u100", id);
        var start = new CountDownLatch(1);
        try (var executor = Executors.newFixedThreadPool(2)) {
            var first =
                    executor.submit(
                            () -> {
                                start.await();
                                return feedback(id, "first", BODY)
                                        .andReturn()
                                        .getResponse()
                                        .getStatus();
                            });
            var second =
                    executor.submit(
                            () -> {
                                start.await();
                                return feedback(id, "second", BODY)
                                        .andReturn()
                                        .getResponse()
                                        .getStatus();
                            });
            start.countDown();
            assertThat(List.of(first.get(15, TimeUnit.SECONDS), second.get(15, TimeUnit.SECONDS)))
                    .containsExactlyInAnyOrder(200, 409);
        }
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM trip_feedback", Integer.class))
                .isEqualTo(1);
    }

    @Test
    void auditFailureRollsBackFeedbackAndIdempotency() throws Exception {
        String id = create("u100");
        finish("u100", id);
        jdbc.execute(
                "CREATE TRIGGER fail_feedback_audit BEFORE INSERT ON audit_log FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test-only failure'");
        feedback(id, "rollback", BODY).andExpect(status().isInternalServerError());
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM trip_feedback", Integer.class))
                .isZero();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM idempotency_request", Integer.class))
                .isZero();
    }

    private String create(String user) throws Exception {
        return data(call(
                                post("/api/v3/trips")
                                        .param("userId", user)
                                        .contentType("application/json")
                                        .content("{\"routeId\":\"r1\"}"),
                                user,
                                "ELDER")
                        .andExpect(status().isOk()))
                .path("id")
                .asText();
    }

    private void finish(String user, String id) throws Exception {
        call(post("/api/v3/trips/" + id + "/finish").param("userId", user), user, "ELDER")
                .andExpect(status().isOk());
    }

    private ResultActions feedback(String id, String key, String body) throws Exception {
        return elder(
                post("/api/v3/trips/" + id + "/feedback")
                        .param("userId", "u100")
                        .header("Idempotency-Key", key)
                        .contentType("application/json")
                        .content(body));
    }

    private ResultActions elder(MockHttpServletRequestBuilder b) throws Exception {
        return call(b, "u100", "ELDER");
    }

    private ResultActions call(MockHttpServletRequestBuilder b, String actor, String role)
            throws Exception {
        return mvc.perform(b.header("X-Mock-Actor-Id", actor).header("X-Mock-Actor-Role", role));
    }

    private JsonNode data(ResultActions r) throws Exception {
        return json.readTree(
                        r.andReturn()
                                .getResponse()
                                .getContentAsString(java.nio.charset.StandardCharsets.UTF_8))
                .path("data");
    }
}
