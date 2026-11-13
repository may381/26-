package cn.silvertravel.platform.scenic;

import static org.assertj.core.api.Assertions.*;

import cn.silvertravel.platform.common.api.ContractJsonConfiguration;
import cn.silvertravel.platform.scenic.ScenicData.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.validation.Validation;
import jakarta.validation.ValidatorFactory;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.stream.Stream;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;

class ScenicDatasetImporterTest {
    private static ObjectMapper json;
    private static ValidatorFactory validation;
    private static ScenicDatasetImporter importer;

    @BeforeAll
    static void initialize() {
        var builder = new Jackson2ObjectMapperBuilder().modules(new JavaTimeModule());
        new ContractJsonConfiguration().strictContractJson().customize(builder);
        json = builder.build();
        validation = Validation.buildDefaultValidatorFactory();
        importer = new ScenicDatasetImporter(json, validation.getValidator());
    }

    @AfterAll
    static void close() {
        validation.close();
    }

    @Test
    void fixtureSupportsDistinctTourDemonstrations() {
        Dataset fixture = importer.read(new ClassPathResource("fixtures/qingfeng.json"));
        assertThat(fixture.scenic().source()).isEqualTo(Source.MOCK);
        assertThat(fixture.scenic().name()).contains("演示数据");
        assertThat(fixture.spots()).hasSize(6);
        assertThat(fixture.facilities()).hasSize(10);
        assertThat(fixture.routes()).hasSize(3);
        assertThat(fixture.routes()).extracting(Route::totalSteps).containsExactly(20, 60, 120);
        assertThat(fixture.routes()).extracting(Route::totalWalkMin).containsExactly(40, 55, 70);
        assertThat(fixture.routes()).extracting(Route::restCount).containsExactly(4L, 2L, 1L);
        assertThat(fixture.routes())
                .allSatisfy(
                        route -> {
                            assertThat(route.source()).isEqualTo(Source.MOCK);
                            assertThat(route.verifiedBy()).isEqualTo("team");
                        });
    }

    @Test
    void mockProviderCannotBeMutatedAndUnknownScenicStaysEmpty() {
        var provider =
                new MockScenicProvider(importer, new ClassPathResource("fixtures/qingfeng.json"));
        Dataset fixture = provider.findById("qingfeng").orElseThrow();
        assertThat(provider.findById("unknown")).isEmpty();
        assertThatThrownBy(() -> fixture.routes().clear())
                .isInstanceOf(UnsupportedOperationException.class);
        assertThatThrownBy(
                        () ->
                                fixture.routes()
                                        .getFirst()
                                        .segments()
                                        .getFirst()
                                        .restFacilities()
                                        .clear())
                .isInstanceOf(UnsupportedOperationException.class);
        assertThat(provider.findById("qingfeng").orElseThrow().routes()).hasSize(3);
    }

    static Stream<String[]> corruptions() {
        return Stream.of(
                new String[] {"/spots/1/id", "\"spot-001\""},
                new String[] {"/facilities/1/id", "\"facility-001\""},
                new String[] {"/routes/1/id", "\"r1\""},
                new String[] {"/facilities/0/spotId", "\"unknown\""},
                new String[] {"/routes/0/spots/1", "\"unknown\""},
                new String[] {"/routes/0/segments/0/toSpotId", "\"spot-004\""},
                new String[] {"/routes/0/segments/0/restFacilities/0", "\"facility-001\""},
                new String[] {"/routes/0/segments/0/restFacilities/0", "\"facility-006\""},
                new String[] {"/routes/0/segments/0/restFacilities/0", "\"missing\""},
                new String[] {"/routes/0/segments/0/steps", "-1"},
                new String[] {"/routes/0/segments/0/walkMin", "0"},
                new String[] {"/routes/0/segments/0/walkMin", "\"10\""},
                new String[] {"/routes/0/segments/0/slope", "101"},
                new String[] {"/spots/0/location/lat", "91"},
                new String[] {"/spots/0/source", "\"FIELD\""},
                new String[] {"/routes/0/verifiedBy", "\"\""},
                new String[] {"/routes/0/updatedAt", "null"},
                new String[] {"/routes/0/segments", "[]"},
                new String[] {"/routes/0/segments/0/steps", "1.5"});
    }

    @ParameterizedTest
    @MethodSource("corruptions")
    void invalidReferencesAndMetadataAreRejected(String pointer, String replacement)
            throws Exception {
        JsonNode tree =
                json.valueToTree(importer.read(new ClassPathResource("fixtures/qingfeng.json")));
        int lastSlash = pointer.lastIndexOf('/');
        JsonNode parent = tree.at(pointer.substring(0, lastSlash));
        String key = pointer.substring(lastSlash + 1);
        if (parent instanceof ArrayNode array) {
            array.set(Integer.parseInt(key), json.readTree(replacement));
        } else {
            ((ObjectNode) parent).set(key, json.readTree(replacement));
        }
        assertThatThrownBy(
                        () -> importer.read(new ByteArrayInputStream(json.writeValueAsBytes(tree))))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsOversizedTrailingAndDuplicateJson() {
        assertThatThrownBy(
                        () ->
                                importer.read(
                                        new ByteArrayInputStream(new byte[5 * 1024 * 1024 + 1])))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(
                        () ->
                                importer.read(
                                        new ByteArrayInputStream(
                                                "{} {}".getBytes(StandardCharsets.UTF_8))))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(
                        () ->
                                importer.read(
                                        new ByteArrayInputStream(
                                                "{\"scenic\":{},\"scenic\":{}}"
                                                        .getBytes(StandardCharsets.UTF_8))))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
