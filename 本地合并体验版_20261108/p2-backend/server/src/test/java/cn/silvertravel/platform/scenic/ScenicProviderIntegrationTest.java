package cn.silvertravel.platform.scenic;

import static org.assertj.core.api.Assertions.*;

import cn.silvertravel.platform.scenic.ScenicData.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.Iterator;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.io.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.*;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.*;

@SpringBootTest(properties = "data.source=real")
@ActiveProfiles("local")
@org.springframework.test.annotation.DirtiesContext(
        classMode = org.springframework.test.annotation.DirtiesContext.ClassMode.AFTER_CLASS)
@Testcontainers
@org.springframework.test.context.bean.override.mockito.MockitoBean(
        types = org.springframework.scheduling.TaskScheduler.class)
class ScenicProviderIntegrationTest {
    @Container
    static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.4")
                    .withDatabaseName("scenic_provider_test")
                    .withUsername("test_app")
                    .withPassword("test_only_password");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
    }

    @Autowired ScenicDataProvider provider;
    @Autowired ScenicDatasetImporter importer;
    @Autowired ScenicDatasetImportService service;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper json;

    @BeforeEach
    void clearOnlyIsolatedTestDatabase() {
        jdbc.update("DELETE FROM scenic_dataset");
    }

    @Test
    void realModeNeverFallsBackToMockAndRepeatedImportDoesNotDuplicate() {
        assertThat(provider).isInstanceOf(DbScenicProvider.class);
        var resource = new ClassPathResource("fixtures/qingfeng.json");
        service.importResource(resource);
        service.importResource(resource);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM scenic_dataset", Integer.class))
                .isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT source FROM scenic_dataset", String.class))
                .isEqualTo("MOCK");
        assertThat(provider.findById("qingfeng")).isEmpty();
        assertThat(provider.listScenics()).isEmpty();
    }

    @Test
    void realSnapshotRoundTripPreservesAllDataAndDoesNotRewriteFixture() throws Exception {
        Resource syntheticReal = synthetic("FIELD", "2026-10-24T00:00:00Z");
        Dataset expected = importer.read(syntheticReal);
        service.importResource(syntheticReal);
        assertThat(provider.findById("qingfeng")).contains(expected);
        assertThat(provider.listScenics()).containsExactly(expected.scenic());
        assertThat(
                        new MockScenicProvider(
                                        importer, new ClassPathResource("fixtures/qingfeng.json"))
                                .findById("qingfeng")
                                .orElseThrow()
                                .scenic()
                                .source())
                .isEqualTo(Source.MOCK);
    }

    @Test
    void invalidImportDoesNotOverwritePreviousSnapshot() throws Exception {
        Resource valid = synthetic("FIELD", "2026-10-24T00:00:00Z");
        service.importResource(valid);
        Dataset before = provider.findById("qingfeng").orElseThrow();
        JsonNode invalid = json.readTree(valid.getInputStream());
        ((ArrayNode) invalid.at("/routes/0/spots")).set(1, TextNode.valueOf("unknown"));
        assertThatThrownBy(
                        () ->
                                service.importResource(
                                        new ByteArrayResource(json.writeValueAsBytes(invalid))))
                .isInstanceOf(IllegalArgumentException.class);
        assertThat(provider.findById("qingfeng")).contains(before);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM scenic_dataset", Integer.class))
                .isEqualTo(1);
    }

    @Test
    void newestSnapshotWinsAndFieldBreaksTimestampTies() throws Exception {
        service.importResource(synthetic("OPEN_DATA", "2026-10-23T00:00:00Z"));
        service.importResource(synthetic("FIELD", "2026-10-24T00:00:00Z"));
        assertThat(provider.findById("qingfeng").orElseThrow().scenic().source())
                .isEqualTo(Source.FIELD);
        service.importResource(synthetic("OPEN_DATA", "2026-10-25T00:00:00Z"));
        assertThat(provider.findById("qingfeng").orElseThrow().scenic().source())
                .isEqualTo(Source.OPEN_DATA);
        service.importResource(synthetic("FIELD", "2026-10-25T00:00:00Z"));
        assertThat(provider.findById("qingfeng").orElseThrow().scenic().source())
                .isEqualTo(Source.FIELD);
        assertThat(provider.listScenics()).hasSize(1);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM scenic_dataset", Integer.class))
                .isEqualTo(2);
    }

    /**
     * Test-only synthetic metadata. Never exposed as real scenic data or imported into the demo DB.
     */
    private Resource synthetic(String source, String updatedAt) throws Exception {
        JsonNode tree =
                json.valueToTree(importer.read(new ClassPathResource("fixtures/qingfeng.json")));
        replaceMetadata(tree, source, updatedAt);
        return new ByteArrayResource(json.writeValueAsBytes(tree));
    }

    private void replaceMetadata(JsonNode node, String source, String updatedAt) {
        if (node instanceof ObjectNode object && object.has("source")) {
            object.put("source", source);
            object.put("updatedAt", updatedAt);
        }
        Iterator<JsonNode> children = node.elements();
        while (children.hasNext()) {
            replaceMetadata(children.next(), source, updatedAt);
        }
    }
}
