package cn.silvertravel.platform.maps;

import static org.assertj.core.api.Assertions.*;
import static org.hamcrest.Matchers.startsWith;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.scenic.ScenicData.Location;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.net.SocketTimeoutException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.*;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class AmapClientTest {
    private MockRestServiceServer server;
    private AmapClient client;
    private static final String TEST_KEY = "test-key-not-a-real-credential";
    private static final Location POINT =
            new Location(new BigDecimal("22.58"), new BigDecimal("114.06"));

    @BeforeEach
    void setup() {
        var builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        client = new AmapClient(builder.build(), properties(TEST_KEY), new ObjectMapper());
    }

    private AmapProperties properties(String key) {
        return new AmapProperties(key, Duration.ofSeconds(2), Duration.ofSeconds(5));
    }

    private long deadline() {
        return System.nanoTime() + Duration.ofSeconds(20).toNanos();
    }

    @Test
    void conversionUsesGpsAndLongitudeFirstAndRespectsBatchLimit() {
        String forty = String.join("|", Collections.nCopies(40, "114.060000,22.580000"));
        server.expect(
                        requestTo(
                                startsWith(
                                        "https://restapi.amap.com/v3/assistant/coordinate/convert")))
                .andExpect(queryParam("key", TEST_KEY))
                .andExpect(queryParam("coordsys", "gps"))
                .andExpect(
                        request -> {
                            String encoded =
                                    org.springframework.web.util.UriComponentsBuilder.fromUri(
                                                    request.getURI())
                                            .build()
                                            .getQueryParams()
                                            .getFirst("locations");
                            assertThat(URLDecoder.decode(encoded, StandardCharsets.UTF_8))
                                    .isEqualTo(forty);
                        })
                .andRespond(
                        withSuccess(
                                "{\"status\":\"1\",\"locations\":\""
                                        + String.join(
                                                ";",
                                                Collections.nCopies(40, "114.065100,22.577300"))
                                        + "\"}",
                                MediaType.APPLICATION_JSON));
        server.expect(
                        requestTo(
                                startsWith(
                                        "https://restapi.amap.com/v3/assistant/coordinate/convert")))
                .andExpect(queryParam("locations", "114.060000,22.580000"))
                .andRespond(
                        withSuccess(
                                "{\"status\":\"1\",\"locations\":\"114.065100,22.577300\"}",
                                MediaType.APPLICATION_JSON));
        var result = client.convertWgs84(Collections.nCopies(41, POINT), deadline());
        assertThat(result).hasSize(41);
        assertThat(result.getFirst().lng()).isEqualByComparingTo("114.0651");
        assertThat(result.getFirst().lat()).isEqualByComparingTo("22.5773");
        server.verify();
    }

    @Test
    void walkingRequestsGeometryAndCostAndParsesUnits() {
        server.expect(requestTo(startsWith("https://restapi.amap.com/v5/direction/walking")))
                .andExpect(queryParam("origin", "114.060000,22.580000"))
                .andExpect(queryParam("show_fields", "cost,polyline"))
                .andRespond(
                        withSuccess(
                                """
                        {"status":"1","route":{"paths":[{"distance":"500","cost":{"duration":"600"},
                        "steps":[{"polyline":"114.060000,22.580000;114.060400,22.580500"}]}]}}
                        """,
                                MediaType.APPLICATION_JSON));
        var path = client.walking(POINT, POINT, deadline());
        assertThat(path.distanceMeters()).isEqualTo(500);
        assertThat(path.durationSeconds()).isEqualTo(600);
        assertThat(path.path()).hasSize(2);
        server.verify();
    }

    @Test
    void upstreamErrorsAndTimeoutNeverExposeKeyOrRequestUrl() {
        server.expect(anything())
                .andRespond(
                        withSuccess(
                                "{\"status\":\"0\",\"info\":\"" + TEST_KEY + "\"}",
                                MediaType.APPLICATION_JSON));
        assertThatThrownBy(() -> client.walking(POINT, POINT, deadline()))
                .isInstanceOf(BusinessException.class)
                .hasMessageNotContaining(TEST_KEY)
                .hasMessageNotContaining("restapi.amap.com")
                .hasNoCause();
        server.verify();
        server.reset();
        server.expect(anything())
                .andRespond(
                        request -> {
                            throw new SocketTimeoutException(TEST_KEY);
                        });
        assertThatThrownBy(() -> client.walking(POINT, POINT, deadline()))
                .isInstanceOf(BusinessException.class)
                .hasMessageNotContaining(TEST_KEY)
                .hasNoCause();
        server.verify();
    }

    @Test
    void missingConfigurationAndExpiredBudgetMakeNoNetworkRequests() {
        var builder = RestClient.builder();
        var isolated = MockRestServiceServer.bindTo(builder).build();
        var missing = new AmapClient(builder.build(), properties(""), new ObjectMapper());
        assertThatThrownBy(() -> missing.convertWgs84(List.of(POINT), deadline()))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("尚未配置");
        assertThatThrownBy(() -> client.walking(POINT, POINT, System.nanoTime() - 1))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("超时");
        assertThat(properties(TEST_KEY).toString()).doesNotContain(TEST_KEY);
        isolated.verify();
        server.verify();
    }

    @Test
    void malformedGeometryAndCountMismatchFailInsteadOfReturningFakePaths() {
        server.expect(anything())
                .andRespond(
                        withSuccess(
                                "{\"status\":\"1\",\"route\":{\"paths\":[]}}",
                                MediaType.APPLICATION_JSON));
        assertThatThrownBy(() -> client.walking(POINT, POINT, deadline()))
                .isInstanceOf(BusinessException.class);
        server.verify();
        server.reset();
        server.expect(anything())
                .andRespond(
                        withSuccess(
                                "{\"status\":\"1\",\"locations\":\"114.06,22.58;114.07,22.59\"}",
                                MediaType.APPLICATION_JSON));
        assertThatThrownBy(() -> client.convertWgs84(List.of(POINT), deadline()))
                .isInstanceOf(BusinessException.class);
        server.verify();
    }
}
