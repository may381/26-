package cn.silvertravel.platform.trip;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.common.idempotency.IdempotencyService;
import cn.silvertravel.platform.scenic.ScenicDataProvider;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import cn.silvertravel.platform.trip.persistence.TripEntity;
import cn.silvertravel.platform.trip.persistence.TripMapper;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.UUID;
import java.util.function.BiConsumer;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class TripJourneyService {
    public record VersionRequest(@NotNull @Min(1) Long expectedTripVersion) {}

    public record RestLocation(
            @NotNull @DecimalMin("-90") @DecimalMax("90") BigDecimal lat,
            @NotNull @DecimalMin("-180") @DecimalMax("180") BigDecimal lng,
            @NotNull @Pattern(regexp = "GCJ-02|WGS84") String coordinateSystem) {}

    public record StartRest(
            @NotNull @Min(1) Long expectedTripVersion,
            @NotNull @Min(1) @Max(1440) Integer plannedMinutes,
            @Size(max = 128) String facilityId,
            @NotNull @Valid RestLocation location) {}

    public record ExtendRest(
            @NotNull @Min(1) Long expectedTripVersion,
            @NotNull @Min(1) @Max(1440) Integer additionalMinutes) {}

    public record RestView(
            String id,
            String status,
            Instant restStartedAt,
            int plannedMinutes,
            String facilityId,
            RestLocation location,
            Instant restEndedAt) {}

    private record Command(String tripId, String targetId, Object request) {}

    private final TripMapper trips;
    private final TripProgressService progress;
    private final ScenicDataProvider scenic;
    private final BusinessAccessPolicy access;
    private final IdempotencyService idempotency;
    private final AuditService audit;
    private final JdbcTemplate jdbc;

    public TripJourneyService(
            TripMapper trips,
            TripProgressService progress,
            ScenicDataProvider scenic,
            BusinessAccessPolicy access,
            IdempotencyService idempotency,
            AuditService audit,
            JdbcTemplate jdbc) {
        this.trips = trips;
        this.progress = progress;
        this.scenic = scenic;
        this.access = access;
        this.idempotency = idempotency;
        this.audit = audit;
        this.jdbc = jdbc;
    }

    public TripService.View view(TripEntity trip) {
        String id = trip.getId();
        var route = progress.currentRoute(id, trip.getUserId()).route();
        var latest = progress.getProgressForVerifiedTrip(id, trip.getUserId());
        var visited = latest == null ? List.<String>of() : latest.visitedSpotIds();
        var skipped = trips.skippedSpots(id);
        var remaining =
                route.spots().stream()
                        .filter(spot -> !visited.contains(spot) && !skipped.contains(spot))
                        .toList();
        var rests = readRests(id);
        var activeRest =
                rests.stream().filter(rest -> rest.restEndedAt() == null).findFirst().orElse(null);
        String current = latest == null ? null : latest.currentSpotId();
        if (current == null || skipped.contains(current) || !route.spots().contains(current)) {
            current = remaining.isEmpty() ? null : remaining.getFirst();
        }

        Instant anchor = trip.getJourneyAnchorAt();
        if (anchor == null) {
            anchor = latest == null ? trip.getCreatedAt() : latest.updatedAt();
        }
        long walkingMinutes =
                route.segments().stream()
                        .filter(segment -> remaining.contains(segment.toSpotId()))
                        .mapToLong(segment -> segment.walkMin())
                        .sum();
        Instant estimatedFinish = anchor.plus(Duration.ofMinutes(walkingMinutes));
        for (RestView rest : rests) {
            Instant end =
                    rest.restEndedAt() == null
                            ? rest.restStartedAt().plus(Duration.ofMinutes(rest.plannedMinutes()))
                            : rest.restEndedAt();
            Instant start = rest.restStartedAt().isAfter(anchor) ? rest.restStartedAt() : anchor;
            if (end.isAfter(start)) {
                estimatedFinish = estimatedFinish.plus(Duration.between(start, end));
            }
        }
        if (trip.getFinishedAt() != null) {
            estimatedFinish = trip.getFinishedAt();
        }
        return new TripService.View(
                id,
                trip.getUserId(),
                route.id(),
                TripService.Status.valueOf(trip.getStatus()),
                trip.getCreatedAt(),
                trip.getTripVersion(),
                latest == null ? 0 : latest.progressSeq(),
                current,
                visited,
                skipped,
                remaining,
                estimatedFinish,
                activeRest);
    }

    @Transactional
    public TripService.View skip(
            String userId, String id, String spotId, VersionRequest request, String key) {
        return change(
                userId,
                id,
                spotId,
                "TRIP_STOP_SKIPPED",
                request,
                request.expectedTripVersion(),
                key,
                true,
                (trip, changedAt) -> {
                    if (!view(trip).remainingSpotIds().contains(spotId)) {
                        throw BusinessException.conflict("只能跳过当前路线中尚未到访的剩余站点");
                    }
                    jdbc.update(
                            "INSERT INTO trip_skipped_stop(trip_id,spot_id,skipped_at) VALUES (?,?,?)",
                            id,
                            spotId,
                            Timestamp.from(changedAt));
                });
    }

    @Transactional
    public TripService.View startRest(String userId, String id, StartRest request, String key) {
        return change(
                userId,
                id,
                null,
                "TRIP_REST_STARTED",
                request,
                request.expectedTripVersion(),
                key,
                true,
                (trip, changedAt) -> {
                    if (readRests(id).stream().anyMatch(rest -> rest.restEndedAt() == null)) {
                        throw BusinessException.conflict("已有进行中的休息");
                    }
                    if (request.facilityId() != null
                            && scenic.findById(trip.getScenicId()).stream()
                                    .flatMap(dataset -> dataset.facilities().stream())
                                    .noneMatch(
                                            facility ->
                                                    facility.id().equals(request.facilityId()))) {
                        throw BusinessException.invalid("设施不属于当前游览景区");
                    }
                    RestLocation location = request.location();
                    jdbc.update(
                            """
                            INSERT INTO trip_rest
                            (id,trip_id,started_at,planned_minutes,facility_id,latitude,longitude,coordinate_system)
                            VALUES (?,?,?,?,?,?,?,?)
                            """,
                            UUID.randomUUID().toString(),
                            id,
                            Timestamp.from(changedAt),
                            request.plannedMinutes(),
                            request.facilityId(),
                            location.lat(),
                            location.lng(),
                            location.coordinateSystem());
                });
    }

    @Transactional
    public TripService.View extendRest(
            String userId, String id, String restId, ExtendRest request, String key) {
        return change(
                userId,
                id,
                restId,
                "TRIP_REST_EXTENDED",
                request,
                request.expectedTripVersion(),
                key,
                false,
                (trip, changedAt) -> {
                    int updated =
                            jdbc.update(
                                    """
                            UPDATE trip_rest SET planned_minutes=planned_minutes+?
                            WHERE id=? AND trip_id=? AND ended_at IS NULL AND planned_minutes+?<=1440
                            """,
                                    request.additionalMinutes(),
                                    restId,
                                    id,
                                    request.additionalMinutes());
                    if (updated != 1) throw BusinessException.conflict("休息不可延长或已超过时长上限");
                });
    }

    @Transactional
    public TripService.View finishRest(
            String userId, String id, String restId, VersionRequest request, String key) {
        return change(
                userId,
                id,
                restId,
                "TRIP_REST_FINISHED",
                request,
                request.expectedTripVersion(),
                key,
                false,
                (trip, changedAt) -> {
                    int updated =
                            jdbc.update(
                                    """
                            UPDATE trip_rest SET ended_at=? WHERE id=? AND trip_id=? AND ended_at IS NULL
                            """,
                                    Timestamp.from(changedAt),
                                    restId,
                                    id);
                    if (updated != 1) throw BusinessException.conflict("没有匹配的进行中休息");
                });
    }

    @Transactional(readOnly = true)
    public List<RestView> listRests(String userId, String id) {
        access.requireElderOwner(userId);
        if (trips.findOwned(id, userId) == null) {
            throw BusinessException.notFound("游览记录不存在");
        }
        return readRests(id);
    }

    void finishOpenRest(String id, Instant endedAt) {
        jdbc.update(
                "UPDATE trip_rest SET ended_at=? WHERE trip_id=? AND ended_at IS NULL",
                Timestamp.from(endedAt),
                id);
    }

    private List<RestView> readRests(String id) {
        return jdbc.query(
                """
                SELECT * FROM trip_rest WHERE trip_id=? ORDER BY started_at,id
                """,
                (rs, row) -> {
                    Timestamp end = rs.getTimestamp("ended_at");
                    return new RestView(
                            rs.getString("id"),
                            end == null ? "RESTING" : "FINISHED",
                            rs.getTimestamp("started_at").toInstant(),
                            rs.getInt("planned_minutes"),
                            rs.getString("facility_id"),
                            new RestLocation(
                                    rs.getBigDecimal("latitude"),
                                    rs.getBigDecimal("longitude"),
                                    rs.getString("coordinate_system")),
                            end == null ? null : end.toInstant());
                },
                id);
    }

    private TripService.View change(
            String userId,
            String id,
            String targetId,
            String operation,
            Object request,
            long expectedVersion,
            String key,
            boolean resetAnchor,
            BiConsumer<TripEntity, Instant> write) {
        var actor = access.requireElderOwner(userId);
        return idempotency.execute(
                actor,
                operation,
                key,
                new Command(id, targetId, request),
                TripService.View.class,
                TripService.View::id,
                () -> {
                    TripEntity trip = trips.lockOwned(id, userId);
                    if (trip == null) throw BusinessException.notFound("游览记录不存在");
                    if (!"ACTIVE".equals(trip.getStatus()))
                        throw BusinessException.conflict("游览已结束");
                    if (trip.getTripVersion() != expectedVersion) {
                        throw BusinessException.conflict("游览状态已更新，请刷新后重试");
                    }
                    Instant changedAt = now();
                    write.accept(trip, changedAt);
                    trips.advanceVersion(id, resetAnchor ? Timestamp.from(changedAt) : null);
                    audit.record(actor, userId, operation, "trip", id);
                    return view(trips.findOwned(id, userId));
                });
    }

    private Instant now() {
        return Instant.now().truncatedTo(ChronoUnit.MICROS);
    }
}
