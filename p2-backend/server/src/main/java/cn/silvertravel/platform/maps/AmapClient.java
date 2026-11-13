package cn.silvertravel.platform.maps;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.scenic.ScenicData.Location;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import org.springframework.web.client.RestClient;
import org.springframework.web.util.UriComponentsBuilder;

/**
 * Only calls fixed official endpoints; neither the key nor upstream error bodies escape this
 * adapter.
 */
public class AmapClient {
    public record WalkingPath(long distanceMeters, long durationSeconds, List<Location> path) {
        public WalkingPath {
            path = List.copyOf(path);
        }
    }

    private final RestClient http;
    private final AmapProperties properties;
    private final ObjectMapper json;

    public AmapClient(RestClient http, AmapProperties properties, ObjectMapper json) {
        this.http = http;
        this.properties = properties;
        this.json = json;
    }

    public List<Location> convertWgs84(List<Location> locations, long deadline) {
        var converted = new ArrayList<Location>();
        for (int from = 0; from < locations.size(); from += 40) {
            checkReady(deadline);
            var batch = locations.subList(from, Math.min(from + 40, locations.size()));
            String coordinates = String.join("|", batch.stream().map(this::coordinate).toList());
            JsonNode body =
                    request(
                            uri("/v3/assistant/coordinate/convert")
                                    .queryParam("coordsys", "gps")
                                    .queryParam("locations", coordinates)
                                    .build()
                                    .encode()
                                    .toUri());
            List<Location> output = parsePolyline(body.path("locations").asText());
            if (output.size() != batch.size()) {
                throw failed();
            }
            converted.addAll(output);
        }
        checkReady(deadline);
        return List.copyOf(converted);
    }

    public WalkingPath walking(Location from, Location to, long deadline) {
        checkReady(deadline);
        JsonNode body =
                request(
                        uri("/v5/direction/walking")
                                .queryParam("origin", coordinate(from))
                                .queryParam("destination", coordinate(to))
                                .queryParam("show_fields", "cost,polyline")
                                .queryParam("alternative_route", 1)
                                .build()
                                .encode()
                                .toUri());
        JsonNode paths = body.path("route").path("paths");
        if (!paths.isArray() || paths.isEmpty()) {
            throw failed();
        }
        JsonNode first = paths.get(0);
        JsonNode steps = first.path("steps");
        if (!steps.isArray() || steps.isEmpty()) {
            throw failed();
        }
        var points = new ArrayList<Location>();
        for (JsonNode step : steps) {
            List<Location> section = parsePolyline(step.path("polyline").asText());
            if (section.size() < 2) {
                throw failed();
            }
            points.addAll(section);
        }
        checkReady(deadline);
        return new WalkingPath(
                nonnegativeLong(first.path("distance").asText()),
                nonnegativeLong(first.path("cost").path("duration").asText()),
                points);
    }

    private UriComponentsBuilder uri(String path) {
        return UriComponentsBuilder.fromUriString("https://restapi.amap.com" + path)
                .queryParam("key", properties.webServiceKey())
                .queryParam("output", "json");
    }

    private JsonNode request(URI uri) {
        try {
            JsonNode result =
                    http.get()
                            .uri(uri)
                            .exchange(
                                    (request, response) -> {
                                        if (!response.getStatusCode().is2xxSuccessful()) {
                                            throw failed();
                                        }
                                        byte[] bytes =
                                                response.getBody().readNBytes(2 * 1024 * 1024 + 1);
                                        if (bytes.length > 2 * 1024 * 1024) {
                                            throw failed();
                                        }
                                        return json.readTree(bytes);
                                    });
            if (result == null || !"1".equals(result.path("status").asText())) {
                throw failed();
            }
            return result;
        } catch (Exception exception) {
            // Deliberately do not attach exceptions containing credential-bearing request URLs.
            throw failed();
        }
    }

    private String coordinate(Location location) {
        return location.lng().setScale(6, RoundingMode.HALF_UP).toPlainString()
                + ","
                + location.lat().setScale(6, RoundingMode.HALF_UP).toPlainString();
    }

    private List<Location> parsePolyline(String encoded) {
        if (encoded.isBlank()) {
            throw failed();
        }
        var points = new ArrayList<Location>();
        try {
            for (String pair : encoded.split(";", -1)) {
                String[] coordinate = pair.split(",", -1);
                if (coordinate.length != 2) {
                    throw failed();
                }
                BigDecimal lng = new BigDecimal(coordinate[0]);
                BigDecimal lat = new BigDecimal(coordinate[1]);
                if (lng.abs().compareTo(BigDecimal.valueOf(180)) > 0
                        || lat.abs().compareTo(BigDecimal.valueOf(90)) > 0) {
                    throw failed();
                }
                points.add(new Location(lat, lng));
            }
        } catch (NumberFormatException exception) {
            throw failed();
        }
        return List.copyOf(points);
    }

    private long nonnegativeLong(String number) {
        try {
            long value = new BigDecimal(number).longValueExact();
            if (value < 0) {
                throw failed();
            }
            return value;
        } catch (NumberFormatException | ArithmeticException exception) {
            throw failed();
        }
    }

    private void checkReady(long deadline) {
        if (properties.webServiceKey().isBlank()) {
            throw BusinessException.upstream("尚未配置高德 Web 服务 Key");
        }
        if (System.nanoTime() >= deadline) {
            throw BusinessException.upstream("高德路径规划超时，请稍后重试");
        }
    }

    private BusinessException failed() {
        return BusinessException.upstream("高德服务暂不可用，请检查 Key、服务权限或配额");
    }
}
