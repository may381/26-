package cn.silvertravel.platform.trip;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.common.idempotency.IdempotencyService;
import cn.silvertravel.platform.route.RouteCatalog;
import cn.silvertravel.platform.scenic.ScenicData.Location;
import cn.silvertravel.platform.scenic.ScenicData.Route;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import cn.silvertravel.platform.trip.persistence.TripMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class TripProgressService {
    public record ReportRequest(
            @NotNull @Min(1) Long progressSeq,
            @NotNull @Valid Location location,
            @Size(max = 128) String currentSpotId,
            @NotNull @Size(max = 1000) List<@NotBlank @Size(max = 128) String> visitedSpotIds,
            @Size(max = 128) String nextSpotId,
            Instant estimatedFinishAt) {
        public ReportRequest {
            if (visitedSpotIds != null)
                visitedSpotIds = Collections.unmodifiableList(new ArrayList<>(visitedSpotIds));
        }
    }

    public record ProgressView(
            long progressSeq,
            Location location,
            String currentSpotId,
            List<String> visitedSpotIds,
            String nextSpotId,
            Instant estimatedFinishAt,
            String source,
            Instant updatedAt) {}

    public record AdjustmentRequest(
            @NotBlank @Size(max = 128) String routeId,
            @Size(max = 500) String reason,
            @NotNull @Min(0) Long expectedProgressSeq) {}

    public record AdjustmentView(
            String id,
            String tripId,
            int revision,
            String routeId,
            Route route,
            List<String> visitedSpotIds,
            List<String> remainingSpotIds,
            String reason,
            Instant createdAt) {}

    public record CurrentRoute(Route route, int revision) {}

    private record AdjustmentCommand(String tripId, AdjustmentRequest request) {}

    private final TripMapper trips;
    private final RouteCatalog routes;
    private final BusinessAccessPolicy access;
    private final AuditService audit;
    private final IdempotencyService idempotency;
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;

    public TripProgressService(
            TripMapper trips,
            RouteCatalog routes,
            BusinessAccessPolicy access,
            AuditService audit,
            IdempotencyService idempotency,
            JdbcTemplate jdbc,
            ObjectMapper json) {
        this.trips = trips;
        this.routes = routes;
        this.access = access;
        this.audit = audit;
        this.idempotency = idempotency;
        this.jdbc = jdbc;
        this.json = json;
    }

    @Transactional
    public ProgressView report(String userId, String tripId, ReportRequest request) {
        var actor = access.requireElderOwner(userId);
        var trip = trips.lockOwned(tripId, userId);
        if (trip == null) throw BusinessException.notFound("游览记录不存在");
        if (!"ACTIVE".equals(trip.getStatus())) throw BusinessException.conflict("只有进行中的游览可以上报进度");
        Route route = currentRoute(tripId, userId).route();
        Set<String> routeSpots = new HashSet<>(route.spots());
        var existing =
                jdbc.query(
                        "SELECT progress_seq,request_hash,visited_spot_ids FROM trip_progress WHERE trip_id=? FOR UPDATE",
                        (rs, n) ->
                                new ExistingProgress(
                                        rs.getLong("progress_seq"),
                                        rs.getString("request_hash"),
                                        readStrings(rs.getString("visited_spot_ids"))),
                        tripId);
        Set<String> allowedVisitedSpots = new HashSet<>(routeSpots);
        if (!existing.isEmpty()) allowedVisitedSpots.addAll(existing.getFirst().visited());
        if (request.currentSpotId() != null && !routeSpots.contains(request.currentSpotId()))
            throw BusinessException.invalid("currentSpotId 不属于当前路线");
        if (request.nextSpotId() != null && !routeSpots.contains(request.nextSpotId()))
            throw BusinessException.invalid("nextSpotId 不属于当前路线");
        if (request.visitedSpotIds().stream().anyMatch(id -> !allowedVisitedSpots.contains(id)))
            throw BusinessException.invalid("visitedSpotIds 包含路线及历史已游点以外的景点");
        Set<String> uniqueVisited = new LinkedHashSet<>(request.visitedSpotIds());
        if (uniqueVisited.size() != request.visitedSpotIds().size())
            throw BusinessException.invalid("visitedSpotIds 不能重复");
        String hash = hash(encode(request));
        if (!existing.isEmpty()) {
            ExistingProgress saved = existing.getFirst();
            if (request.progressSeq() < saved.sequence())
                throw BusinessException.conflict("进度序号已过期");
            if (request.progressSeq() == saved.sequence()) {
                if (!saved.hash().equals(hash))
                    throw BusinessException.conflict("同一 progressSeq 不能提交不同内容");
                return getProgress(tripId, userId);
            }
            uniqueVisited.addAll(saved.visited());
        }
        var skipped = trips.skippedSpots(tripId);
        if ((request.currentSpotId() != null && skipped.contains(request.currentSpotId()))
                || (request.nextSpotId() != null && skipped.contains(request.nextSpotId()))
                || uniqueVisited.stream().anyMatch(skipped::contains)) {
            throw BusinessException.conflict("已跳过的景点不能上报为到访或下一站");
        }
        Instant now = Instant.now();
        String visitedJson = encode(List.copyOf(uniqueVisited));
        if (existing.isEmpty()) {
            jdbc.update(
                    "INSERT INTO trip_progress(trip_id,user_id,progress_seq,request_hash,latitude,longitude,current_spot_id,visited_spot_ids,next_spot_id,estimated_finish_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    tripId,
                    userId,
                    request.progressSeq(),
                    hash,
                    request.location().lat(),
                    request.location().lng(),
                    request.currentSpotId(),
                    visitedJson,
                    request.nextSpotId(),
                    null,
                    Timestamp.from(now));
        } else {
            jdbc.update(
                    "UPDATE trip_progress SET progress_seq=?,request_hash=?,latitude=?,longitude=?,current_spot_id=?,visited_spot_ids=?,next_spot_id=?,estimated_finish_at=?,updated_at=? WHERE trip_id=? AND user_id=?",
                    request.progressSeq(),
                    hash,
                    request.location().lat(),
                    request.location().lng(),
                    request.currentSpotId(),
                    visitedJson,
                    request.nextSpotId(),
                    null,
                    Timestamp.from(now),
                    tripId,
                    userId);
        }
        trips.advanceVersion(tripId, Timestamp.from(now));
        audit.record(actor, userId, "TRIP_PROGRESS_REPORTED", "trip", tripId);
        return getProgress(tripId, userId);
    }

    @Transactional(readOnly = true)
    public ProgressView getProgress(String tripId, String userId) {
        access.requireElderOwner(userId);
        if (trips.findOwned(tripId, userId) == null) throw BusinessException.notFound("游览记录不存在");
        return getProgressForVerifiedTrip(tripId, userId);
    }

    @Transactional(readOnly = true)
    ProgressView getProgressForVerifiedTrip(String tripId, String userId) {
        var rows =
                jdbc.query(
                        "SELECT progress_seq,latitude,longitude,current_spot_id,visited_spot_ids,next_spot_id,estimated_finish_at,updated_at FROM trip_progress WHERE trip_id=? AND user_id=?",
                        (rs, n) ->
                                new ProgressView(
                                        rs.getLong("progress_seq"),
                                        new Location(
                                                rs.getBigDecimal("latitude"),
                                                rs.getBigDecimal("longitude")),
                                        rs.getString("current_spot_id"),
                                        readStrings(rs.getString("visited_spot_ids")),
                                        rs.getString("next_spot_id"),
                                        rs.getTimestamp("estimated_finish_at") == null
                                                ? null
                                                : rs.getTimestamp("estimated_finish_at")
                                                        .toInstant(),
                                        "CLIENT_REPORTED",
                                        rs.getTimestamp("updated_at").toInstant()),
                        tripId,
                        userId);
        return rows.isEmpty() ? null : rows.getFirst();
    }

    @Transactional
    public AdjustmentView adjust(
            String userId, String tripId, AdjustmentRequest request, String key) {
        var actor = access.requireElderOwner(userId);
        return idempotency.execute(
                actor,
                "trip.route.adjust",
                key,
                new AdjustmentCommand(tripId, request),
                AdjustmentView.class,
                AdjustmentView::id,
                () -> adjustOnce(userId, tripId, request));
    }

    @Transactional(readOnly = true)
    public List<AdjustmentView> listAdjustments(String userId, String tripId) {
        access.requireElderOwner(userId);
        if (trips.findOwned(tripId, userId) == null) throw BusinessException.notFound("游览记录不存在");
        return jdbc.query(
                "SELECT id,revision,route_id,route_snapshot,visited_spot_ids,remaining_spot_ids,reason,created_at FROM trip_route_adjustment WHERE trip_id=? AND user_id=? ORDER BY revision",
                (rs, n) -> adjustmentView(rs, tripId),
                tripId,
                userId);
    }

    @Transactional(readOnly = true)
    public CurrentRoute currentRoute(String tripId, String userId) {
        var rows =
                jdbc.query(
                        "SELECT revision,route_snapshot FROM trip_route_adjustment WHERE trip_id=? AND user_id=? ORDER BY revision DESC LIMIT 1",
                        (rs, n) ->
                                new CurrentRoute(
                                        readRoute(rs.getString("route_snapshot")),
                                        rs.getInt("revision")),
                        tripId,
                        userId);
        if (!rows.isEmpty()) return rows.getFirst();
        var trip = trips.findOwned(tripId, userId);
        if (trip == null) throw BusinessException.notFound("游览记录不存在");
        return new CurrentRoute(readRoute(trip.getRouteSnapshot()), 0);
    }

    private AdjustmentView adjustOnce(String userId, String tripId, AdjustmentRequest request) {
        var trip = trips.lockOwned(tripId, userId);
        if (trip == null) throw BusinessException.notFound("游览记录不存在");
        if (!"ACTIVE".equals(trip.getStatus())) throw BusinessException.conflict("只有进行中的游览可以调整路线");
        ProgressView progress = getProgress(tripId, userId);
        long currentSeq = progress == null ? 0 : progress.progressSeq();
        if (currentSeq != request.expectedProgressSeq())
            throw BusinessException.conflict("游览进度已变化，请刷新后重新调整");
        var current = currentRoute(tripId, userId);
        var next = routes.require(request.routeId());
        if (!trip.getScenicId().equals(next.dataset().scenic().id()))
            throw BusinessException.invalid("调整后的路线必须属于当前景区");
        List<String> visited = progress == null ? List.of() : progress.visitedSpotIds();
        var skipped = trips.skippedSpots(tripId);
        List<String> remaining =
                next.route().spots().stream()
                        .filter(id -> !visited.contains(id) && !skipped.contains(id))
                        .toList();
        int revision = current.revision() + 1;
        String id = UUID.randomUUID().toString();
        Instant now = Instant.now();
        jdbc.update(
                "INSERT INTO trip_route_adjustment(id,trip_id,user_id,revision,route_id,route_snapshot,visited_spot_ids,remaining_spot_ids,reason,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                id,
                tripId,
                userId,
                revision,
                request.routeId(),
                encode(next.route()),
                encode(visited),
                encode(remaining),
                request.reason(),
                Timestamp.from(now));
        trips.advanceVersion(tripId, Timestamp.from(now));
        audit.record(access.currentActor(), userId, "TRIP_ROUTE_ADJUSTED", "trip", tripId);
        return new AdjustmentView(
                id,
                tripId,
                revision,
                request.routeId(),
                next.route(),
                visited,
                remaining,
                request.reason(),
                now);
    }

    private record ExistingProgress(long sequence, String hash, List<String> visited) {}

    private AdjustmentView adjustmentView(java.sql.ResultSet rs, String tripId)
            throws java.sql.SQLException {
        return new AdjustmentView(
                rs.getString("id"),
                tripId,
                rs.getInt("revision"),
                rs.getString("route_id"),
                readRoute(rs.getString("route_snapshot")),
                readStrings(rs.getString("visited_spot_ids")),
                readStrings(rs.getString("remaining_spot_ids")),
                rs.getString("reason"),
                rs.getTimestamp("created_at").toInstant());
    }

    private Route readRoute(String value) {
        try {
            return json.readValue(value, Route.class);
        } catch (java.io.IOException exception) {
            throw new IllegalStateException("Stored route is invalid", exception);
        }
    }

    private List<String> readStrings(String value) {
        try {
            return json.readValue(
                    value, json.getTypeFactory().constructCollectionType(List.class, String.class));
        } catch (java.io.IOException exception) {
            throw new IllegalStateException("Stored progress is invalid", exception);
        }
    }

    private String encode(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Unable to serialize trip progress", exception);
        }
    }

    private String hash(String value) {
        try {
            return HexFormat.of()
                    .formatHex(
                            MessageDigest.getInstance("SHA-256")
                                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(exception);
        }
    }
}
