package cn.silvertravel.platform.scenic;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.scenic.ScenicData.*;
import java.time.Instant;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;

@Service
@Profile("!bootstrap")
public class SpotQueryService {
    public record SpotSummary(
            String id,
            String scenicId,
            String name,
            String description,
            boolean descriptionAvailable,
            Location location,
            String coordinateSystem,
            Source source,
            Instant updatedAt,
            String verifiedBy) {}

    public record FacilityView(
            String id,
            String name,
            FacilityType type,
            String spotId,
            Location location,
            String coordinateSystem,
            Source source,
            Instant updatedAt,
            String verifiedBy) {}

    public record FacilitySearchResult(FacilityView facility, Double distanceMeters) {}

    public record SpotDetail(
            String id,
            String scenicId,
            String name,
            String description,
            boolean descriptionAvailable,
            Location location,
            String coordinateSystem,
            Source source,
            Instant updatedAt,
            String verifiedBy,
            List<FacilityView> facilities) {}

    private record Entry(Dataset dataset, Spot spot) {}

    private final ScenicDataProvider provider;

    public SpotQueryService(ScenicDataProvider provider) {
        this.provider = provider;
    }

    public List<SpotSummary> list(String scenicId) {
        return entries(scenicId).values().stream().map(this::summary).toList();
    }

    public SpotDetail get(String id, String scenicId) {
        var entry = entries(scenicId).get(id);
        if (entry == null) throw BusinessException.notFound("景点不存在");
        var s = summary(entry);
        var facilities =
                entry.dataset.facilities().stream()
                        .filter(f -> f.spotId().equals(id))
                        .sorted(Comparator.comparing(Facility::id))
                        .map(
                                f ->
                                        new FacilityView(
                                                f.id(),
                                                f.name(),
                                                f.type(),
                                                f.spotId(),
                                                f.location(),
                                                "WGS84",
                                                f.source(),
                                                f.updatedAt(),
                                                f.verifiedBy()))
                        .toList();
        return new SpotDetail(
                s.id,
                s.scenicId,
                s.name,
                s.description,
                s.descriptionAvailable,
                s.location,
                s.coordinateSystem,
                s.source,
                s.updatedAt,
                s.verifiedBy,
                facilities);
    }

    public List<FacilitySearchResult> facilities(
            String scenicId, FacilityType type, Double lat, Double lng, int limit) {
        if ((lat == null) != (lng == null))
            throw BusinessException.invalid("lat 和 lng 必须同时提供");
        if (lat != null && (!Double.isFinite(lat) || lat < -90 || lat > 90))
            throw BusinessException.invalid("lat 超出范围");
        if (lng != null && (!Double.isFinite(lng) || lng < -180 || lng > 180))
            throw BusinessException.invalid("lng 超出范围");
        if (limit < 1 || limit > 100) throw BusinessException.invalid("limit 必须为 1～100");
        List<Dataset> datasets =
                scenicId == null
                        ? provider.listScenics().stream()
                                .map(s -> provider.findById(s.id()).orElseThrow())
                                .toList()
                        : List.of(
                                provider.findById(scenicId)
                                        .orElseThrow(
                                                () -> BusinessException.notFound("景区不存在")));
        Comparator<FacilitySearchResult> order =
                Comparator.comparing(
                                FacilitySearchResult::distanceMeters,
                                Comparator.nullsLast(Double::compareTo))
                        .thenComparing(result -> result.facility().id());
        return datasets.stream()
                .flatMap(data -> data.facilities().stream())
                .filter(facility -> type == null || facility.type() == type)
                .map(
                        facility -> {
                            var view =
                                    new FacilityView(
                                            facility.id(),
                                            facility.name(),
                                            facility.type(),
                                            facility.spotId(),
                                            facility.location(),
                                            "WGS84",
                                            facility.source(),
                                            facility.updatedAt(),
                                            facility.verifiedBy());
                            Double distance =
                                    lat == null
                                            ? null
                                            : distanceMeters(
                                                    lat,
                                                    lng,
                                                    facility.location().lat().doubleValue(),
                                                    facility.location().lng().doubleValue());
                            return new FacilitySearchResult(view, distance);
                        })
                .sorted(order)
                .limit(limit)
                .toList();
    }

    private double distanceMeters(double lat1, double lng1, double lat2, double lng2) {
        double earthRadiusMeters = 6_371_000;
        double dLat = Math.toRadians(lat2 - lat1);
        double dLng = Math.toRadians(lng2 - lng1);
        double a =
                Math.sin(dLat / 2) * Math.sin(dLat / 2)
                        + Math.cos(Math.toRadians(lat1))
                                * Math.cos(Math.toRadians(lat2))
                                * Math.sin(dLng / 2)
                                * Math.sin(dLng / 2);
        return earthRadiusMeters * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    private SortedMap<String, Entry> entries(String scenicId) {
        List<Dataset> datasets;
        if (scenicId != null) {
            if (scenicId.isBlank() || scenicId.length() > 128)
                throw BusinessException.invalid("scenicId 无效");
            datasets =
                    List.of(
                            provider.findById(scenicId)
                                    .orElseThrow(() -> BusinessException.notFound("景区不存在")));
        } else
            datasets =
                    provider.listScenics().stream()
                            .map(s -> provider.findById(s.id()).orElseThrow())
                            .toList();
        var result = new TreeMap<String, Entry>();
        for (var data : datasets)
            for (var spot : data.spots())
                if (result.putIfAbsent(spot.id(), new Entry(data, spot)) != null)
                    throw BusinessException.conflict("景点 ID 跨景区重复，请使用 scenicId 指定景区");
        return result;
    }

    private SpotSummary summary(Entry e) {
        var s = e.spot;
        String description =
                s.description() == null || s.description().isBlank() ? null : s.description();
        return new SpotSummary(
                s.id(),
                e.dataset.scenic().id(),
                s.name(),
                description,
                description != null,
                s.location(),
                "WGS84",
                s.source(),
                s.updatedAt(),
                s.verifiedBy());
    }
}
