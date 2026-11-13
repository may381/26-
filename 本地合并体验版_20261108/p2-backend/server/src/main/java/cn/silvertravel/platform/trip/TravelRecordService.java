package cn.silvertravel.platform.trip;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.common.idempotency.IdempotencyService;
import cn.silvertravel.platform.scenic.ScenicData.Route;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import cn.silvertravel.platform.trip.TravelRecordModels.*;
import cn.silvertravel.platform.trip.persistence.*;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.Timestamp;
import java.time.*;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class TravelRecordService {
    private record Cursor(String userId, Instant finishedAt, String id) {}

    private record FeedbackCommand(String tripId, FeedbackRequest feedback) {}

    private final TripMapper trips;
    private final BusinessAccessPolicy access;
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    private final AuditService audit;
    private final IdempotencyService idempotency;
    private final TripProgressService progress;
    private final cn.silvertravel.platform.media.MediaSigner signer;

    public TravelRecordService(
            TripMapper trips,
            BusinessAccessPolicy access,
            JdbcTemplate jdbc,
            ObjectMapper json,
            AuditService audit,
            IdempotencyService idempotency,
            TripProgressService progress,
            cn.silvertravel.platform.media.MediaSigner signer) {
        this.trips = trips;
        this.access = access;
        this.jdbc = jdbc;
        this.json = json;
        this.audit = audit;
        this.idempotency = idempotency;
        this.progress = progress;
        this.signer = signer;
    }

    @Transactional(readOnly = true)
    public RecordPage list(String userId, int limit, String cursor) {
        access.requireElderOwner(userId);
        if (limit < 1 || limit > 100) throw BusinessException.invalid("limit 必须为 1～100");
        Cursor before = decode(cursor, userId);
        var rows =
                trips.findFinishedPage(
                        userId,
                        before == null ? null : Timestamp.from(before.finishedAt),
                        before == null ? null : before.id,
                        limit + 1);
        boolean more = rows.size() > limit;
        var page = rows.subList(0, Math.min(limit, rows.size()));
        Set<String> submitted = Set.of();
        if (!page.isEmpty()) {
            List<Object> params = new ArrayList<>();
            params.add(userId);
            page.forEach(t -> params.add(t.getId()));
            String placeholders = String.join(",", Collections.nCopies(page.size(), "?"));
            submitted =
                    new HashSet<>(
                            jdbc.queryForList(
                                    "SELECT trip_id FROM trip_feedback WHERE user_id=? AND trip_id IN ("
                                            + placeholders
                                            + ")",
                                    String.class,
                                    params.toArray()));
        }
        final Set<String> feedbackTrips = submitted;
        var items =
                page.stream()
                        .map(
                                t -> {
                                    Route r = snapshot(t);
                                    return new RecordSummary(
                                            t.getId(),
                                            t.getId(),
                                            userId,
                                            t.getRouteId(),
                                            r.name(),
                                            r.source(),
                                            t.getCreatedAt(),
                                            t.getFinishedAt(),
                                            duration(t),
                                            feedbackTrips.contains(t.getId()));
                                })
                        .toList();
        String next = null;
        if (more) {
            var last = page.getLast();
            next = encode(new Cursor(userId, last.getFinishedAt(), last.getId()));
        }
        return new RecordPage(items, next);
    }

    @Transactional(readOnly = true)
    public RecordDetail get(String userId, String id) {
        access.requireElderOwner(userId);
        requireUuid(id);
        var trip = trips.findOwned(id, userId);
        if (trip == null || !"FINISHED".equals(trip.getStatus()))
            throw BusinessException.notFound("已结束的游后记录不存在");
        Route route = snapshot(trip);
        var tripProgress = progress.getProgress(id, userId);
        return new RecordDetail(
                id,
                id,
                userId,
                trip.getScenicId(),
                trip.getStatus(),
                trip.getRouteId(),
                route.name(),
                route.source(),
                trip.getCreatedAt(),
                trip.getFinishedAt(),
                duration(trip),
                route.spots(),
                tripProgress == null ? List.of() : tripProgress.visitedSpotIds(),
                tripProgress == null ? "NONE" : tripProgress.source(),
                tripProgress != null,
                route,
                progress.listAdjustments(userId, id),
                media(id, userId),
                feedback(id, userId),
                preferenceUpdate(id, userId),
                "路线为开始游览时的计划快照；实际到访进度由客户端上报，尚未进行现场校验。durationSeconds 为游览历时，不是连续步行时长。偏好只有老人确认后才写回档案。");
    }

    @Transactional
    public FeedbackView submit(String userId, String tripId, FeedbackRequest input, String key) {
        var actor = access.requireElderOwner(userId);
        requireUuid(tripId);
        if (key == null) throw BusinessException.invalid("游后反馈需要 Idempotency-Key");
        var normalized =
                new FeedbackRequest(
                        input.effort(),
                        input.comfortableWalkMin(),
                        input.note() == null || input.note().isBlank()
                                ? null
                                : input.note().strip());
        return idempotency.execute(
                actor,
                "trip.feedback.create",
                key,
                new FeedbackCommand(tripId, normalized),
                FeedbackView.class,
                FeedbackView::id,
                () -> {
                    var trip = trips.lockOwned(tripId, userId);
                    if (trip == null) throw BusinessException.notFound("游览记录不存在");
                    if (!"FINISHED".equals(trip.getStatus()))
                        throw BusinessException.conflict("请先结束游览再提交反馈");
                    if (feedback(tripId, userId) != null)
                        throw BusinessException.conflict("本次游览已提交反馈，请勿重复创建");
                    String id = UUID.randomUUID().toString();
                    Instant now = Instant.now().truncatedTo(ChronoUnit.MICROS);
                    jdbc.update(
                            "INSERT INTO trip_feedback(id,trip_id,user_id,effort,comfortable_walk_min,note,created_at) VALUES (?,?,?,?,?,?,?)",
                            id,
                            tripId,
                            userId,
                            normalized.effort().name(),
                            normalized.comfortableWalkMin(),
                            normalized.note(),
                            Timestamp.from(now));
                    String preferenceId = null;
                    String preferenceStatus = null;
                    if (normalized.comfortableWalkMin() != null) {
                        preferenceId = UUID.randomUUID().toString();
                        preferenceStatus = "PENDING";
                        jdbc.update(
                                "INSERT INTO trip_preference_update(id,trip_id,user_id,walk_duration_min,status,created_at) VALUES (?,?,?,?,'PENDING',?)",
                                preferenceId,
                                tripId,
                                userId,
                                normalized.comfortableWalkMin(),
                                Timestamp.from(now));
                    }
                    audit.record(actor, userId, "TRIP_FEEDBACK_CREATED", "tripFeedback", id);
                    return new FeedbackView(
                            id,
                            tripId,
                            userId,
                            normalized.effort(),
                            normalized.comfortableWalkMin(),
                            normalized.note(),
                            now,
                            false,
                            false,
                            preferenceId,
                            preferenceStatus);
                });
    }

    private FeedbackView feedback(String tripId, String userId) {
        var rows =
                jdbc.query(
                        "SELECT f.id,f.effort,f.comfortable_walk_min,f.note,f.created_at,p.id AS preference_id,p.status AS preference_status FROM trip_feedback f LEFT JOIN trip_preference_update p ON p.trip_id=f.trip_id AND p.user_id=f.user_id WHERE f.trip_id=? AND f.user_id=?",
                        (rs, n) ->
                                new FeedbackView(
                                        rs.getString("id"),
                                        tripId,
                                        userId,
                                        Effort.valueOf(rs.getString("effort")),
                                        rs.getObject("comfortable_walk_min", Integer.class),
                                        rs.getString("note"),
                                        rs.getTimestamp("created_at").toInstant(),
                                        "APPROVED".equals(rs.getString("preference_status")),
                                        false,
                                        rs.getString("preference_id"),
                                        rs.getString("preference_status")),
                        tripId,
                        userId);
        return rows.isEmpty() ? null : rows.getFirst();
    }

    private PreferenceUpdateView preferenceUpdate(String tripId, String userId) {
        var rows =
                jdbc.query(
                        "SELECT id,walk_duration_min,status,created_at FROM trip_preference_update WHERE trip_id=? AND user_id=?",
                        (rs, n) ->
                                new PreferenceUpdateView(
                                        rs.getString("id"),
                                        rs.getInt("walk_duration_min"),
                                        rs.getString("status"),
                                        rs.getTimestamp("created_at").toInstant()),
                        tripId,
                        userId);
        return rows.isEmpty() ? null : rows.getFirst();
    }

    private List<MediaSummary> media(String tripId, String userId) {
        return jdbc.query(
                "SELECT id,mime_type,file_name,size_bytes,created_at FROM trip_media WHERE trip_id=? AND user_id=? ORDER BY created_at,id",
                (rs, n) ->
                        new MediaSummary(
                                        rs.getString("id"),
                                        rs.getString("mime_type"),
                                        rs.getString("file_name"),
                                        rs.getLong("size_bytes"),
                                        rs.getTimestamp("created_at").toInstant())
                                .withLink(
                                        signer.issue(
                                                cn.silvertravel.platform.media.MediaSigner.Kind
                                                        .TRIP,
                                                rs.getString("id"),
                                                null)),
                tripId,
                userId);
    }

    private Route snapshot(TripEntity trip) {
        try {
            return json.readValue(trip.getRouteSnapshot(), Route.class);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Invalid persisted route snapshot", ex);
        }
    }

    private long duration(TripEntity trip) {
        if (trip.getFinishedAt() == null || trip.getFinishedAt().isBefore(trip.getCreatedAt()))
            throw new IllegalStateException("Invalid persisted trip times");
        return Duration.between(trip.getCreatedAt(), trip.getFinishedAt()).getSeconds();
    }

    private String encode(Cursor cursor) {
        try {
            return Base64.getUrlEncoder()
                    .withoutPadding()
                    .encodeToString(json.writeValueAsBytes(cursor));
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Unable to encode page cursor", ex);
        }
    }

    private Cursor decode(String encoded, String userId) {
        if (encoded == null) return null;
        try {
            if (encoded.length() > 512 || !encoded.matches("[A-Za-z0-9_-]+"))
                throw new IllegalArgumentException();
            var cursor = json.readValue(Base64.getUrlDecoder().decode(encoded), Cursor.class);
            if (cursor == null
                    || !userId.equals(cursor.userId)
                    || cursor.finishedAt == null
                    || cursor.id == null) throw new IllegalArgumentException();
            requireUuid(cursor.id);
            if (cursor.finishedAt.isBefore(Instant.EPOCH)
                    || cursor.finishedAt.isAfter(Instant.parse("9999-12-31T23:59:59Z")))
                throw new IllegalArgumentException();
            return cursor;
        } catch (java.io.IOException | IllegalArgumentException | BusinessException ex) {
            throw BusinessException.invalid("cursor 无效，请从第一页重新查询");
        }
    }

    private void requireUuid(String id) {
        if (id == null
                || !id.matches(
                        "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"))
            throw BusinessException.invalid("记录 ID 必须为 UUID");
    }
}
