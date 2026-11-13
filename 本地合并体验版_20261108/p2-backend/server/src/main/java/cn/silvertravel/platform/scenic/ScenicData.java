package cn.silvertravel.platform.scenic;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

/** Internal dataset schema. Additional fields are a local draft, not new public API. */
public final class ScenicData {
    private ScenicData() {}

    public enum Source {
        MOCK,
        OPEN_DATA,
        FIELD
    }

    public enum FacilityType {
        TOILET,
        BENCH,
        MEDICAL,
        EXIT,
        SERVICE_DESK
    }

    public record Location(
            @NotNull @DecimalMin("-90") @DecimalMax("90") BigDecimal lat,
            @NotNull @DecimalMin("-180") @DecimalMax("180") BigDecimal lng) {}

    public record Scenic(
            @NotBlank @Size(max = 128) String id,
            @NotBlank @Size(max = 100) String name,
            @NotNull Source source,
            @NotNull Instant updatedAt,
            @NotBlank @Size(max = 100) String verifiedBy) {}

    public record Spot(
            @NotBlank @Size(max = 128) String id,
            @NotBlank @Size(max = 100) String name,
            @NotNull @Valid Location location,
            @NotNull Source source,
            @NotNull Instant updatedAt,
            @NotBlank @Size(max = 100) String verifiedBy,
            @Size(max = 4000) String description) {}

    public record Facility(
            @NotBlank @Size(max = 128) String id,
            @NotBlank @Size(max = 100) String name,
            @NotNull FacilityType type,
            @NotBlank @Size(max = 128) String spotId,
            @NotNull @Valid Location location,
            @NotNull Source source,
            @NotNull Instant updatedAt,
            @NotBlank @Size(max = 100) String verifiedBy) {}

    public record Segment(
            @NotBlank String fromSpotId,
            @NotBlank String toSpotId,
            @NotNull @Min(0) @Max(100000) Integer steps,
            @NotNull @DecimalMin("0") @DecimalMax("100") BigDecimal slope,
            @NotNull @Min(1) @Max(1440) Integer walkMin,
            @NotNull @Size(max = 1000) List<@NotBlank String> restFacilities,
            @NotNull Source source,
            @NotNull Instant updatedAt,
            @NotBlank @Size(max = 100) String verifiedBy) {
        public Segment {
            if (restFacilities != null) restFacilities = List.copyOf(restFacilities);
        }
    }

    public record Route(
            @NotBlank @Size(max = 128) String id,
            @NotBlank @Size(max = 100) String name,
            @NotNull @Size(min = 2, max = 1000) List<@NotBlank String> spots,
            @NotNull @Size(min = 1, max = 999) List<@NotNull @Valid Segment> segments,
            @NotNull Source source,
            @NotNull Instant updatedAt,
            @NotBlank @Size(max = 100) String verifiedBy) {
        public Route {
            if (spots != null) spots = List.copyOf(spots);
            if (segments != null) segments = List.copyOf(segments);
        }

        public int totalSteps() {
            return segments.stream().mapToInt(Segment::steps).sum();
        }

        public int totalWalkMin() {
            return segments.stream().mapToInt(Segment::walkMin).sum();
        }

        public long restCount() {
            return segments.stream().flatMap(s -> s.restFacilities().stream()).distinct().count();
        }
    }

    public record Dataset(
            @NotNull @Valid Scenic scenic,
            @NotNull @Size(min = 1, max = 10000) List<@NotNull @Valid Spot> spots,
            @NotNull @Size(max = 10000) List<@NotNull @Valid Facility> facilities,
            @NotNull @Size(min = 1, max = 1000) List<@NotNull @Valid Route> routes) {
        public Dataset {
            if (spots != null) spots = List.copyOf(spots);
            if (facilities != null) facilities = List.copyOf(facilities);
            if (routes != null) routes = List.copyOf(routes);
        }
    }
}
