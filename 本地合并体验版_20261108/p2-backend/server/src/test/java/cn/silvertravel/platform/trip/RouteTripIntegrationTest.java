package cn.silvertravel.platform.trip;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.maps.AmapClient;
import cn.silvertravel.platform.scenic.ScenicData.Location;
import com.fasterxml.jackson.databind.*;
import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.*;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
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
class RouteTripIntegrationTest {
    @Container
    static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.4")
                    .withDatabaseName("route_trip_test")
                    .withUsername("test_app")
                    .withPassword("test_only_password")
                    .withCommand("--skip-log-bin");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
    }

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @MockitoBean AmapClient amap;

    @BeforeEach
    void initializeOnlyIsolatedTestDatabase() throws Exception {
        jdbc.execute("DROP TRIGGER IF EXISTS fail_audit");
        jdbc.update("DELETE FROM trip");
        jdbc.update("DELETE FROM family_relation");
        jdbc.update("DELETE FROM elder_profile");
        jdbc.update("DELETE FROM audit_log");
        elder(
                        patch("/api/v3/profile")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(
                                        """
                {"nickname":"王阿姨","age":68,"residence":"深圳","language":"普通话",
                 "walkSpeed":"MEDIUM","walkDurationMin":40,"avoidSteps":true,
                 "interests":[],"interactionPreference":"VOICE","emergencyContacts":[]}
                """))
                .andExpect(status().isOk());
    }

    @Test
    void recommendationUsesProfileAndExplicitFalseOverridesIt() throws Exception {
        JsonNode personal =
                data(elder(get("/api/v3/routes").param("userId", "u100"))
                                .andExpect(status().isOk()))
                        .get("routes");
        assertThat(personal.size()).isEqualTo(3);
        assertThat(selectedId(personal)).isEqualTo("r1");
        JsonNode overridden =
                data(elder(
                                        get("/api/v3/routes")
                                                .param("userId", "u100")
                                                .param("walkDurationMin", "70")
                                                .param("avoidSteps", "false"))
                                .andExpect(status().isOk()))
                        .get("routes");
        assertThat(selectedId(overridden)).isEqualTo("r3");
        elder(get("/api/v3/profile").param("userId", "u100"))
                .andExpect(jsonPath("$.data.walkDurationMin").value(40))
                .andExpect(jsonPath("$.data.avoidSteps").value(true));
        verifyNoInteractions(amap);
    }

    @Test
    void genericRecommendationAndNoExactMatchStayExplicit() throws Exception {
        assertThat(
                        selectedId(
                                data(elder(get("/api/v3/routes")).andExpect(status().isOk()))
                                        .get("routes")))
                .isEqualTo("r2");
        JsonNode routes =
                data(elder(get("/api/v3/routes").param("walkDurationMin", "10"))
                                .andExpect(status().isOk()))
                        .get("routes");
        assertThat(selectedId(routes)).isEqualTo("r1");
        assertThat(routes.get(0).get("reason").asText()).contains("无完全匹配，此为最接近方案");
        assertThat(routes.get(0).get("source").asText()).isEqualTo("MOCK");
        assertThat(routes.get(1).get("reason").isNull()).isTrue();
        elder(get("/api/v3/routes").param("walkDurationMin", "0"))
                .andExpect(status().isBadRequest());
        elder(get("/api/v3/routes").param("walkDurationMin", "1.5"))
                .andExpect(status().isBadRequest());
        elder(get("/api/v3/routes").param("avoidSteps", "unknown"))
                .andExpect(status().isBadRequest());
        elder(get("/api/v3/routes").param("userId", "u101")).andExpect(status().isForbidden());
    }

    @Test
    void activeTripCanBeRecoveredOnlyByItsOwner() throws Exception {
        String path = "/api/v3/trips/active";
        elder(get(path).param("userId", "u100"))
                .andExpect(status().isOk())
                .andExpect(content().json("{\"code\":\"OK\",\"data\":null}"));
        String id = createTrip();
        String startedAt =
                data(elder(get("/api/v3/trips/" + id).param("userId", "u100"))
                                .andExpect(status().isOk()))
                        .path("startedAt")
                        .asText();
        assertThat(startedAt).isNotBlank();
        elder(get(path).param("userId", "u100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(id))
                .andExpect(jsonPath("$.data.startedAt").value(startedAt))
                .andExpect(jsonPath("$.data.status").value("ACTIVE"));
        mvc.perform(
                        get(path)
                                .param("userId", "u100")
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isForbidden());
        elder(post("/api/v3/trips/" + id + "/finish").param("userId", "u100"))
                .andExpect(status().isOk());
        elder(get(path).param("userId", "u100"))
                .andExpect(status().isOk())
                .andExpect(content().json("{\"code\":\"OK\",\"data\":null}"));
    }

    @Test
    void legacyProgressEtaIsAcceptedAndJourneyEtaIsReturned() throws Exception {
        String id = createTrip();
        String path = "/api/v3/trips/" + id + "/progress";
        var reported =
                data(
                        elder(
                                        post(path)
                                                .param("userId", "u100")
                                                .contentType(MediaType.APPLICATION_JSON)
                                                .content(
                                                        """
                        {"progressSeq":1,"location":{"lat":22.58,"lng":114.06},
                         "visitedSpotIds":[],"estimatedFinishAt":"2000-01-01T00:00:00Z"}
                        """))
                                .andExpect(status().isOk()));
        var active =
                data(
                        elder(get("/api/v3/trips/active").param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(reported.path("estimatedFinishAt").asText())
                .isNotBlank()
                .isEqualTo(active.path("estimatedFinishAt").asText());
        assertThat(
                        jdbc.queryForObject(
                                "SELECT estimated_finish_at FROM trip_progress WHERE trip_id=?",
                                java.sql.Timestamp.class,
                                id))
                .isNull();
    }

    @Test
    void skipAndRestRecoverAcrossRequestsWithVersionAndReplayProtection() throws Exception {
        String path = "/api/v3/trips/" + createTrip();
        var skip = post(path + "/stops/spot-001/skip");
        JsonNode skipped =
                data(
                        journeyWrite(skip, "test-skip", "{\"expectedTripVersion\":1}")
                                .andExpect(status().isOk()));
        assertThat(skipped.path("tripVersion").asLong()).isEqualTo(2);
        assertThat(skipped.path("currentSpotId").asText()).isEqualTo("spot-002");
        assertThat(skipped.path("visitedSpotIds").size()).isZero();
        assertThat(skipped.path("skippedSpotIds").get(0).asText()).isEqualTo("spot-001");
        assertThat(
                        data(
                                journeyWrite(
                                                post(path + "/stops/spot-001/skip"),
                                                "test-skip",
                                                "{\"expectedTripVersion\":1}")
                                        .andExpect(status().isOk())))
                .isEqualTo(skipped);
        journeyWrite(
                        post(path + "/stops/spot-002/skip"),
                        "stale-skip",
                        "{\"expectedTripVersion\":1}")
                .andExpect(status().isConflict());

        String startBody =
                """
                {"expectedTripVersion":2,"plannedMinutes":10,
                 "location":{"lat":22.581,"lng":114.0608,"coordinateSystem":"GCJ-02"}}
                """;
        JsonNode started =
                data(
                        journeyWrite(post(path + "/rests"), "test-rest", startBody)
                                .andExpect(status().isOk()));
        String restId = started.at("/activeRest/id").asText();
        String restPath = path + "/rests/" + restId;
        JsonNode extended =
                data(
                        journeyWrite(
                                        patch(restPath),
                                        "test-extend",
                                        "{\"expectedTripVersion\":3,\"additionalMinutes\":5}")
                                .andExpect(status().isOk()));
        assertThat(extended.at("/activeRest/plannedMinutes").asInt()).isEqualTo(15);
        assertThat(java.time.Instant.parse(extended.path("estimatedFinishAt").asText()))
                .isEqualTo(
                        java.time.Instant.parse(started.path("estimatedFinishAt").asText())
                                .plusSeconds(300));
        assertThat(
                        data(
                                elder(get("/api/v3/trips/active").param("userId", "u100"))
                                        .andExpect(status().isOk())))
                .isEqualTo(extended);

        JsonNode finished =
                data(
                        journeyWrite(
                                        post(restPath + "/finish"),
                                        "test-end-rest",
                                        "{\"expectedTripVersion\":4}")
                                .andExpect(status().isOk()));
        assertThat(finished.path("activeRest").isNull()).isTrue();
        assertThat(finished.path("tripVersion").asLong()).isEqualTo(5);
        assertThat(java.time.Instant.parse(finished.path("estimatedFinishAt").asText()))
                .isBefore(java.time.Instant.parse(extended.path("estimatedFinishAt").asText()));
        elder(get(path + "/rests").param("userId", "u100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].status").value("FINISHED"));
    }

    private ResultActions journeyWrite(
            MockHttpServletRequestBuilder request, String key, String body) throws Exception {
        return elder(
                request.param("userId", "u100")
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body));
    }

    @Test
    void tripLifecycleKeepsSnapshotAndAllowsNextTripOnlyAfterFinish() throws Exception {
        String id = createTrip();
        elder(get("/api/v3/trips/" + id).param("userId", "u100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("ACTIVE"));
        elder(
                        post("/api/v3/trips")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"routeId\":\"r2\"}"))
                .andExpect(status().isConflict());
        assertThat(
                        jdbc.queryForObject(
                                "SELECT route_source FROM trip WHERE id = ?", String.class, id))
                .isEqualTo("MOCK");
        JsonNode snapshot =
                json.readTree(
                        jdbc.queryForObject(
                                "SELECT route_snapshot FROM trip WHERE id = ?", String.class, id));
        assertThat(snapshot.get("segments").size()).isEqualTo(3);
        elder(post("/api/v3/trips/" + id + "/finish").param("userId", "u100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("FINISHED"));
        elder(post("/api/v3/trips/" + id + "/finish").param("userId", "u100"))
                .andExpect(status().isConflict());
        String next = createTrip();
        assertThat(next).isNotEqualTo(id);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM trip WHERE status = 'ACTIVE'", Integer.class))
                .isEqualTo(1);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM trip WHERE status = 'FINISHED'",
                                Integer.class))
                .isEqualTo(1);
        verifyNoInteractions(amap);
    }

    @Test
    void tripCannotBeAssignedForeignIdentityOrArbitraryStatus() throws Exception {
        elder(
                        post("/api/v3/trips")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"routeId\":\"unknown\"}"))
                .andExpect(status().isNotFound());
        elder(
                        post("/api/v3/trips")
                                .param("userId", "u100")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"routeId\":\"r1\",\"status\":\"FINISHED\"}"))
                .andExpect(status().isBadRequest());
        String id = createTrip();
        elder(get("/api/v3/trips/" + id).param("userId", "u101")).andExpect(status().isForbidden());
        mvc.perform(
                        get("/api/v3/trips/" + id)
                                .param("userId", "u101")
                                .header("X-Mock-Actor-Id", "u101")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isNotFound());
        mvc.perform(
                        post("/api/v3/trips/" + id + "/finish")
                                .param("userId", "u100")
                                .header("X-Mock-Actor-Id", "family-operator-001")
                                .header("X-Mock-Actor-Role", "FAMILY"))
                .andExpect(status().isForbidden());
    }

    @Test
    void concurrentStartsCommitOneActiveTripAndOneAudit() throws Exception {
        CountDownLatch start = new CountDownLatch(1);
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Callable<Integer> create =
                    () -> {
                        if (!start.await(10, TimeUnit.SECONDS))
                            throw new IllegalStateException("Start timed out");
                        return elder(
                                        post("/api/v3/trips")
                                                .param("userId", "u100")
                                                .contentType(MediaType.APPLICATION_JSON)
                                                .content("{\"routeId\":\"r1\"}"))
                                .andReturn()
                                .getResponse()
                                .getStatus();
                    };
            var first = executor.submit(create);
            var second = executor.submit(create);
            start.countDown();
            assertThat(List.of(first.get(30, TimeUnit.SECONDS), second.get(30, TimeUnit.SECONDS)))
                    .containsExactlyInAnyOrder(200, 409);
        } finally {
            start.countDown();
        }
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM trip", Integer.class)).isEqualTo(1);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM audit_log WHERE action='TRIP_STARTED'",
                                Integer.class))
                .isEqualTo(1);
    }

    @Test
    void databaseConstraintBlocksDuplicateActiveTripEvenWithoutService() throws Exception {
        String id = createTrip();
        assertThatThrownBy(
                        () ->
                                jdbc.update(
                                        """
                INSERT INTO trip(id,user_id,route_id,scenic_id,route_source,route_snapshot,status,created_at)
                SELECT ?,user_id,route_id,scenic_id,route_source,route_snapshot,status,created_at FROM trip WHERE id=?
                """,
                                        UUID.randomUUID().toString(),
                                        id))
                .isInstanceOf(DuplicateKeyException.class);
    }

    @Test
    void auditFailureRollsBackBothStartAndFinish() throws Exception {
        triggerAuditFailure();
        try {
            elder(
                            post("/api/v3/trips")
                                    .param("userId", "u100")
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content("{\"routeId\":\"r1\"}"))
                    .andExpect(status().isInternalServerError());
            assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM trip", Integer.class)).isZero();
        } finally {
            jdbc.execute("DROP TRIGGER fail_audit");
        }
        String id = createTrip();
        triggerAuditFailure();
        try {
            elder(post("/api/v3/trips/" + id + "/finish").param("userId", "u100"))
                    .andExpect(status().isInternalServerError());
            elder(get("/api/v3/trips/" + id).param("userId", "u100"))
                    .andExpect(jsonPath("$.data.status").value("ACTIVE"));
        } finally {
            jdbc.execute("DROP TRIGGER fail_audit");
        }
    }

    @Test
    void mapUsesConvertedCoordinatesAndPreservesSpotOrderAndMockLabel() throws Exception {
        when(amap.convertWgs84(anyList(), anyLong()))
                .thenAnswer(
                        invocation -> {
                            List<Location> input = invocation.getArgument(0);
                            return input.stream()
                                    .map(
                                            location ->
                                                    new Location(
                                                            location.lat()
                                                                    .subtract(
                                                                            new BigDecimal(
                                                                                    "0.003")),
                                                            location.lng()
                                                                    .add(new BigDecimal("0.005"))))
                                    .toList();
                        });
        when(amap.walking(any(), any(), anyLong()))
                .thenAnswer(
                        invocation ->
                                new AmapClient.WalkingPath(
                                        100,
                                        120,
                                        List.of(
                                                invocation.getArgument(0),
                                                invocation.getArgument(1))));
        elder(get("/api/v3/routes/r1/map"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.coordinateSystem").value("GCJ-02"))
                .andExpect(jsonPath("$.data.provider").value("AMAP"))
                .andExpect(jsonPath("$.data.source").value("MOCK"))
                .andExpect(jsonPath("$.data.accessibilityVerified").value(false))
                .andExpect(jsonPath("$.data.spots[0].location.lng").value(114.065))
                .andExpect(jsonPath("$.data.spots[0].location.lat").value(22.577))
                .andExpect(jsonPath("$.data.spots.length()").value(4))
                .andExpect(jsonPath("$.data.facilities.length()").value(10))
                .andExpect(jsonPath("$.data.legs.length()").value(3))
                .andExpect(jsonPath("$.data.legs[0].fromSpotId").value("spot-001"))
                .andExpect(jsonPath("$.data.legs[0].toSpotId").value("spot-002"));
        verify(amap, times(3)).walking(any(), any(), anyLong());
    }

    @Test
    void mapFailureIsExplicitAndDoesNotAffectRecommendationOrTrip() throws Exception {
        when(amap.convertWgs84(anyList(), anyLong()))
                .thenThrow(BusinessException.upstream("地图服务不可用"));
        elder(get("/api/v3/routes/r1/map"))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.code").value("UPSTREAM_ERROR"));
        elder(get("/api/v3/routes")).andExpect(status().isOk());
        createTrip();
    }

    private String selectedId(JsonNode routes) {
        String id = null;
        int selected = 0;
        for (JsonNode route : routes) {
            if (route.get("recommended").asBoolean()) {
                selected++;
                id = route.get("id").asText();
            }
        }
        assertThat(selected).isEqualTo(1);
        return id;
    }

    private String createTrip() throws Exception {
        return data(elder(
                                post("/api/v3/trips")
                                        .param("userId", "u100")
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content("{\"routeId\":\"r1\"}"))
                        .andExpect(status().isOk())
                        .andExpect(jsonPath("$.data.status").value("ACTIVE")))
                .get("id")
                .asText();
    }

    private void triggerAuditFailure() {
        jdbc.execute(
                "CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log FOR EACH ROW "
                        + "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test audit failure'");
    }

    private ResultActions elder(MockHttpServletRequestBuilder request) throws Exception {
        return mvc.perform(
                request.header("X-Mock-Actor-Id", "u100").header("X-Mock-Actor-Role", "ELDER"));
    }

    private JsonNode data(ResultActions response) throws Exception {
        return json.readTree(response.andReturn().getResponse().getContentAsString()).get("data");
    }
}
