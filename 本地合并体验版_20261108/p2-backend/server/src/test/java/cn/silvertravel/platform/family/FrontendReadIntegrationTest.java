package cn.silvertravel.platform.family;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import cn.silvertravel.platform.scenic.*;
import com.fasterxml.jackson.databind.*;
import java.util.List;
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
class FrontendReadIntegrationTest {
    @Container
    static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.4")
                    .withDatabaseName("frontend_read_test")
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
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    private String relation;

    @BeforeEach
    void initializeIsolatedData() throws Exception {
        jdbc.execute("DROP TRIGGER IF EXISTS fail_link_audit");
        for (String table :
                List.of(
                        "help_notification",
                        "help_event",
                        "idempotency_request",
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
            {"nickname":"演示老人","age":68,"residence":"不应向家属暴露的住址","language":"普通话","walkSpeed":"MEDIUM","walkDurationMin":60,"avoidSteps":true,"interests":[],"interactionPreference":"VOICE","emergencyContacts":[{"name":"private","phone":"PRIVATE-PHONE","relation":"private"}]}
            """),
                            user,
                            "ELDER")
                    .andExpect(status().isOk());
        relation = createRelation("u100");
    }

    @Test
    void spotsResolveIdsWithoutInventingDescriptionsOrCallingAmap() throws Exception {
        call(get("/api/v3/spots"), "u100", "ELDER")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(6))
                .andExpect(jsonPath("$.data[0].id").value("spot-001"))
                .andExpect(jsonPath("$.data[0].coordinateSystem").value("WGS84"))
                .andExpect(jsonPath("$.data[0].descriptionAvailable").value(false))
                .andExpect(jsonPath("$.data[0].description").isEmpty())
                .andExpect(jsonPath("$.data[0].source").value("MOCK"));
        var detail =
                data(
                        call(get("/api/v3/spots/spot-003"), "u100", "ELDER")
                                .andExpect(status().isOk()));
        assertThat(detail.path("name").asText()).isNotBlank();
        assertThat(detail.path("facilities").isArray()).isTrue();
        for (var facility : detail.path("facilities"))
            assertThat(facility.path("spotId").asText()).isEqualTo("spot-003");
        call(get("/api/v3/spots/missing"), "u100", "ELDER").andExpect(status().isNotFound());
        call(get("/api/v3/spots").param("scenicId", "missing"), "u100", "ELDER")
                .andExpect(status().isNotFound());
        call(get("/api/v3/spots").param("scenicId", " "), "u100", "ELDER")
                .andExpect(status().isBadRequest());
        mvc.perform(get("/api/v3/spots")).andExpect(status().isUnauthorized());
    }

    @Test
    void descriptionIsOptionalAndPreservedByImporter() throws Exception {
        var importer =
                new ScenicDatasetImporter(
                        json,
                        jakarta.validation.Validation.buildDefaultValidatorFactory()
                                .getValidator());
        var resource = new org.springframework.core.io.ClassPathResource("fixtures/qingfeng.json");
        var node = json.readTree(resource.getInputStream());
        ((com.fasterxml.jackson.databind.node.ObjectNode) node.path("spots").get(0))
                .put("description", "人工提供的演示介绍，非真实讲解");
        var dataset = importer.read(new java.io.ByteArrayInputStream(json.writeValueAsBytes(node)));
        var provider = new MockScenicProviderForTest(dataset);
        var query = new SpotQueryService(provider);
        assertThat(query.get("spot-001", null).description()).contains("演示介绍");
        assertThat(query.get("spot-001", null).descriptionAvailable()).isTrue();
    }

    private record MockScenicProviderForTest(ScenicData.Dataset dataset)
            implements ScenicDataProvider {
        public List<ScenicData.Scenic> listScenics() {
            return List.of(dataset.scenic());
        }

        public java.util.Optional<ScenicData.Dataset> findById(String id) {
            return id.equals(dataset.scenic().id())
                    ? java.util.Optional.of(dataset)
                    : java.util.Optional.empty();
        }
    }

    @Test
    void familyCannotSelfAssociateAndUnlinkedRolesCannotRead() throws Exception {
        family(get("/api/v3/family/elder").param("userId", "u100"))
                .andExpect(status().isNotFound());
        family(
                        post(linkPath())
                                .param("userId", "u100")
                                .contentType("application/json")
                                .content("{\"familyActorId\":\"family-operator-001\"}"))
                .andExpect(status().isForbidden());
        call(
                        post(linkPath())
                                .param("userId", "u100")
                                .contentType("application/json")
                                .content("{\"familyActorId\":\"family-operator-001\"}"),
                        "u101",
                        "ELDER")
                .andExpect(status().isForbidden());
        elder(
                        post(linkPath())
                                .param("userId", "u100")
                                .contentType("application/json")
                                .content("{\"familyActorId\":\"family-operator-001\"}"))
                .andExpect(status().isConflict());
        approve();
        link("family-operator-001").andExpect(status().isOk());
        call(get("/api/v3/family/elder").param("userId", "u100"), "scenic-operator-001", "SCENIC")
                .andExpect(status().isForbidden());
        call(get("/api/v3/family/elder").param("userId", "u100"), "family-operator-002", "FAMILY")
                .andExpect(status().isNotFound());
        family(get("/api/v3/family/elder").param("userId", "u101"))
                .andExpect(status().isNotFound());
    }

    @Test
    void independentPermissionsRedactPrivateDataAndNeverFakeProgress() throws Exception {
        approve();
        link("family-operator-001").andExpect(status().isOk());
        var trip =
                data(
                        elder(
                                        post("/api/v3/trips")
                                                .param("userId", "u100")
                                                .contentType("application/json")
                                                .content("{\"routeId\":\"r1\"}"))
                                .andExpect(status().isOk()));
        createHelp();
        var denied =
                data(
                        family(get("/api/v3/family/elder").param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(denied.path("trip").isNull()).isTrue();
        assertThat(denied.path("helpEvents").isNull()).isTrue();
        family(get("/api/v3/notifications").param("userId", "u100"))
                .andExpect(status().isForbidden());
        permissions("{\"shareProgress\":true,\"shareLocation\":true}");
        var view =
                data(
                        family(get("/api/v3/family/elder").param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(view.path("trip").path("id").asText()).isEqualTo(trip.path("id").asText());
        assertThat(view.path("trip").path("progressAvailable").asBoolean()).isFalse();
        assertThat(view.path("trip").path("visitedSpotIds").isArray()).isTrue();
        assertThat(view.path("trip").path("visitedSpotIds").size()).isZero();
        assertThat(view.path("location").isNull()).isTrue();
        assertThat(view.toString())
                .doesNotContain("PRIVATE-PHONE", "emergencyContacts", "residence", "locationNote");
        permissions("{\"shareAlert\":true,\"shareProgress\":false,\"shareLocation\":false}");
        view =
                data(
                        family(get("/api/v3/family/elder").param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(view.path("helpEvents").size()).isEqualTo(1);
        assertThat(view.path("trip").isNull()).isTrue();
        assertThat(view.path("helpEvents").toString()).doesNotContain("locationNote", "lat", "lng");
    }

    @Test
    void inboxIsRecipientScopedAndRevocationImmediatelyBlocksHistoricalReads() throws Exception {
        approve();
        link("family-operator-001").andExpect(status().isOk());
        permissions("{\"shareAlert\":true}");
        String help = createHelp();
        var inbox =
                data(
                        family(get("/api/v3/notifications").param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(inbox.size()).isEqualTo(1);
        assertThat(inbox.get(0).path("type").asText()).isEqualTo("HELP_OPEN");
        assertThat(inbox.get(0).path("deliveryMode").asText()).isEqualTo("MOCK");
        assertThat(inbox.get(0).path("helpEventId").asText()).isEqualTo(help);
        call(post("/api/v3/help-events/" + help + "/acknowledge"), "scenic-operator-001", "SCENIC")
                .andExpect(status().isOk());
        inbox =
                data(
                        family(get("/api/v3/notifications").param("userId", "u100"))
                                .andExpect(status().isOk()));
        assertThat(inbox.size()).isEqualTo(2);
        assertThat(inbox.get(0).path("businessStatus").asText()).isEqualTo("ACKNOWLEDGED");
        family(get("/api/v3/notifications").param("userId", "u100").param("limit", "0"))
                .andExpect(status().isBadRequest());
        family(get("/api/v3/notifications").param("userId", "u100").param("limit", "101"))
                .andExpect(status().isBadRequest());
        permissions("{\"shareAlert\":false}");
        family(get("/api/v3/notifications").param("userId", "u100"))
                .andExpect(status().isForbidden());
        permissions("{\"shareAlert\":true}");
        elder(post("/api/v3/family-relations/" + relation + "/revoke").param("userId", "u100"))
                .andExpect(status().isOk());
        family(get("/api/v3/notifications").param("userId", "u100"))
                .andExpect(status().isNotFound());
        family(get("/api/v3/family/elder").param("userId", "u100"))
                .andExpect(status().isNotFound());
        relation = createRelation("u100");
        approve();
        link("family-operator-001").andExpect(status().isOk());
        permissions("{\"shareAlert\":true}");
        assertThat(
                        data(family(get("/api/v3/notifications").param("userId", "u100"))
                                        .andExpect(status().isOk()))
                                .size())
                .isZero();
    }

    @Test
    void linkingIsStableAndCannotReplaceAnotherIdentity() throws Exception {
        approve();
        link("family-operator-001").andExpect(status().isOk());
        link("family-operator-001").andExpect(status().isOk());
        link("family-operator-002").andExpect(status().isConflict());
        link("u100").andExpect(status().isBadRequest());
        link("unknown").andExpect(status().isBadRequest());
        String first = relation;
        relation = createRelation("u100");
        approve();
        link("family-operator-001").andExpect(status().isConflict());
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM family_identity_link", Integer.class))
                .isEqualTo(1);
        relation = first;
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM audit_log WHERE action='FAMILY_MOCK_ACCOUNT_LINKED'",
                                Integer.class))
                .isEqualTo(1);
    }

    @Test
    void associationAndAuditRollbackTogether() throws Exception {
        approve();
        jdbc.execute(
                "CREATE TRIGGER fail_link_audit BEFORE INSERT ON audit_log FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test-only audit failure'");
        link("family-operator-001").andExpect(status().isInternalServerError());
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM family_identity_link", Integer.class))
                .isZero();
        family(get("/api/v3/family/elder").param("userId", "u100"))
                .andExpect(status().isNotFound());
    }

    private String createRelation(String user) throws Exception {
        return data(call(
                                post("/api/v3/family-relations")
                                        .param("userId", user)
                                        .contentType("application/json")
                                        .content(
                                                "{\"name\":\"演示家属\",\"relation\":\"家属\",\"phone\":\"DEMO\"}"),
                                user,
                                "ELDER")
                        .andExpect(status().isOk()))
                .path("id")
                .asText();
    }

    private void approve() throws Exception {
        elder(post("/api/v3/family-relations/" + relation + "/approve").param("userId", "u100"))
                .andExpect(status().isOk());
    }

    private String linkPath() {
        return "/api/v3/family-relations/" + relation + "/mock-account";
    }

    private ResultActions link(String actor) throws Exception {
        return elder(
                post(linkPath())
                        .param("userId", "u100")
                        .contentType("application/json")
                        .content(
                                json.writeValueAsString(java.util.Map.of("familyActorId", actor))));
    }

    private void permissions(String body) throws Exception {
        elder(
                        patch("/api/v3/family-relations/" + relation + "/permissions")
                                .param("userId", "u100")
                                .contentType("application/json")
                                .content(body))
                .andExpect(status().isOk());
    }

    private String createHelp() throws Exception {
        return data(elder(
                                post("/api/v3/help-events")
                                        .contentType("application/json")
                                        .content(
                                                "{\"userId\":\"u100\",\"type\":\"GENERAL\",\"location\":{\"lat\":22.58,\"lng\":114.06},\"locationNote\":\"private location note\"}"))
                        .andExpect(status().isOk()))
                .path("id")
                .asText();
    }

    private ResultActions elder(MockHttpServletRequestBuilder b) throws Exception {
        return call(b, "u100", "ELDER");
    }

    private ResultActions family(MockHttpServletRequestBuilder b) throws Exception {
        return call(b, "family-operator-001", "FAMILY");
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
