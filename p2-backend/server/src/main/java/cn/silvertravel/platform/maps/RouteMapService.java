package cn.silvertravel.platform.maps;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.route.RouteCatalog;
import cn.silvertravel.platform.scenic.ScenicData.*;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;

@Service
@Profile("!bootstrap")
public class RouteMapService {
    public record SpotMarker(String id, String name, Location location) {}

    public record FacilityMarker(String id, String name, FacilityType type, Location location) {}

    public record Leg(
            String fromSpotId,
            String toSpotId,
            long distanceMeters,
            long durationSeconds,
            List<Location> path) {}

    public record View(
            String routeId,
            String name,
            Source source,
            String provider,
            String coordinateSystem,
            boolean accessibilityVerified,
            String notice,
            List<SpotMarker> spots,
            List<FacilityMarker> facilities,
            List<Leg> legs) {}

    private final RouteCatalog catalog;
    private final AmapClient amap;

    public RouteMapService(RouteCatalog catalog, AmapClient amap) {
        this.catalog = catalog;
        this.amap = amap;
    }

    public View get(String routeId) {
        var entry = catalog.require(routeId);
        if (entry.route().spots().size() > 20 || entry.dataset().facilities().size() > 200) {
            throw BusinessException.invalid("单次地图规划最多支持 20 个景点和 200 个设施");
        }
        var orderedSpots =
                entry.route().spots().stream()
                        .map(
                                id ->
                                        entry.dataset().spots().stream()
                                                .filter(spot -> spot.id().equals(id))
                                                .findFirst()
                                                .orElseThrow())
                        .toList();
        var originals = new ArrayList<Location>();
        orderedSpots.forEach(spot -> originals.add(spot.location()));
        entry.dataset().facilities().forEach(facility -> originals.add(facility.location()));
        long deadline = System.nanoTime() + Duration.ofSeconds(20).toNanos();
        List<Location> converted = amap.convertWgs84(originals, deadline);
        var spots = new ArrayList<SpotMarker>();
        for (int i = 0; i < orderedSpots.size(); i++) {
            var spot = orderedSpots.get(i);
            spots.add(new SpotMarker(spot.id(), spot.name(), converted.get(i)));
        }
        var facilities = new ArrayList<FacilityMarker>();
        for (int i = 0; i < entry.dataset().facilities().size(); i++) {
            var facility = entry.dataset().facilities().get(i);
            facilities.add(
                    new FacilityMarker(
                            facility.id(),
                            facility.name(),
                            facility.type(),
                            converted.get(orderedSpots.size() + i)));
        }
        var legs = new ArrayList<Leg>();
        for (int i = 0; i < spots.size() - 1; i++) {
            var path = amap.walking(spots.get(i).location(), spots.get(i + 1).location(), deadline);
            legs.add(
                    new Leg(
                            spots.get(i).id(),
                            spots.get(i + 1).id(),
                            path.distanceMeters(),
                            path.durationSeconds(),
                            path.path()));
        }
        return new View(
                routeId,
                entry.route().name(),
                entry.route().source(),
                "AMAP",
                "GCJ-02",
                false,
                (entry.route().source() == Source.MOCK ? "演示点位，不可作为真实导航。" : "")
                        + "高德路径未核实台阶、坡度和休息点，不能据此保证适老可达性。",
                List.copyOf(spots),
                List.copyOf(facilities),
                List.copyOf(legs));
    }
}
