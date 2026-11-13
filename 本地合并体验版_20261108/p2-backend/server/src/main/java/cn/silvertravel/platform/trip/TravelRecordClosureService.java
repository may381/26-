package cn.silvertravel.platform.trip;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.profile.ProfileService;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import cn.silvertravel.platform.trip.TravelRecordModels.*;
import cn.silvertravel.platform.trip.persistence.TripMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.io.IOException;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

@Service
@Profile("!bootstrap")
public class TravelRecordClosureService {
    public record PreferenceDecisionRequest(
            @NotNull String preferenceUpdateId,
            @NotNull TravelRecordModels.PreferenceDecision decision) {}

    public record ShareRequest(@NotNull @Size(max = 3) List<@NotNull String> mediaIds) {
        public ShareRequest {
            if (mediaIds != null)
                mediaIds = Collections.unmodifiableList(new ArrayList<>(mediaIds));
        }
    }

    private record ShareRow(
            String id,
            String tripId,
            String userId,
            Instant expiresAt,
            Instant revokedAt,
            String routeSnapshot,
            Instant startedAt,
            Instant finishedAt) {}

    private final JdbcTemplate jdbc;
    private final TripMapper trips;
    private final TripProgressService progress;
    private final TravelRecordService records;
    private final ProfileService profiles;
    private final BusinessAccessPolicy access;
    private final AuditService audit;
    private final ObjectMapper json;
    private final cn.silvertravel.platform.media.MediaSigner signer;

    public TravelRecordClosureService(
            JdbcTemplate jdbc,
            TripMapper trips,
            TripProgressService progress,
            TravelRecordService records,
            ProfileService profiles,
            BusinessAccessPolicy access,
            AuditService audit,
            ObjectMapper json,
            cn.silvertravel.platform.media.MediaSigner signer) {
        this.jdbc = jdbc;
        this.trips = trips;
        this.progress = progress;
        this.records = records;
        this.profiles = profiles;
        this.access = access;
        this.audit = audit;
        this.json = json;
        this.signer = signer;
    }

    @Transactional
    public MediaSummary upload(String userId, String tripId, MultipartFile file) {
        var actor = access.requireElderOwner(userId);
        var trip = trips.lockOwned(tripId, userId);
        if (trip == null) throw BusinessException.notFound("游览记录不存在");
        if ("CANCELLED".equals(trip.getStatus()))
            throw BusinessException.conflict("已取消的游览不能添加记录附件");
        if (file == null || file.isEmpty() || file.getSize() > 10L * 1024 * 1024)
            throw BusinessException.invalid("附件大小必须为 1 字节～10 MiB");
        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (IOException exception) {
            throw BusinessException.invalid("无法读取附件");
        }
        String mimeType = sniff(bytes);
        if (mimeType == null)
            throw BusinessException.invalid("只支持 JPG、PNG、WebP 图片和 WAV、MP3、WebM、OGG、MP4 音频");
        String fileName = safeFileName(file.getOriginalFilename(), mimeType);
        String id = UUID.randomUUID().toString();
        Instant now = Instant.now();
        jdbc.update(
                "INSERT INTO trip_media(id,trip_id,user_id,mime_type,file_name,content,size_bytes,created_at) VALUES (?,?,?,?,?,?,?,?)",
                id,
                tripId,
                userId,
                mimeType,
                fileName,
                bytes,
                bytes.length,
                Timestamp.from(now));
        audit.record(actor, userId, "TRIP_MEDIA_ADDED", "tripMedia", id);
        return new MediaSummary(id, mimeType, fileName, bytes.length, now)
                .withLink(
                        signer.issue(
                                cn.silvertravel.platform.media.MediaSigner.Kind.TRIP, id, null));
    }

    @Transactional(readOnly = true)
    public BinaryMedia media(String userId, String tripId, String mediaId) {
        access.requireElderOwner(userId);
        var rows =
                jdbc.query(
                        "SELECT mime_type,file_name,content FROM trip_media WHERE id=? AND trip_id=? AND user_id=?",
                        (rs, n) ->
                                new BinaryMedia(
                                        rs.getBytes("content"),
                                        rs.getString("mime_type"),
                                        rs.getString("file_name")),
                        mediaId,
                        tripId,
                        userId);
        if (rows.isEmpty()) throw BusinessException.notFound("游览附件不存在");
        return rows.getFirst();
    }

    @Transactional
    public PreferenceUpdateView decidePreference(
            String userId, String tripId, PreferenceDecisionRequest request) {
        var actor = access.requireElderOwner(userId);
        var trip = trips.lockOwned(tripId, userId);
        if (trip == null || !"FINISHED".equals(trip.getStatus()))
            throw BusinessException.notFound("已结束的游览记录不存在");
        var rows =
                jdbc.query(
                        "SELECT id,walk_duration_min,status,created_at FROM trip_preference_update WHERE id=? AND trip_id=? AND user_id=? FOR UPDATE",
                        (rs, n) ->
                                new PreferenceUpdateView(
                                        rs.getString("id"),
                                        rs.getInt("walk_duration_min"),
                                        rs.getString("status"),
                                        rs.getTimestamp("created_at").toInstant()),
                        request.preferenceUpdateId(),
                        tripId,
                        userId);
        if (rows.isEmpty()) throw BusinessException.notFound("待确认偏好不存在");
        var saved = rows.getFirst();
        String decision =
                request.decision() == PreferenceDecision.APPROVE ? "APPROVED" : "REJECTED";
        if (!"PENDING".equals(saved.status())) {
            if (saved.status().equals(decision)) return saved;
            throw BusinessException.conflict("偏好建议已经处理，不能改写原决定");
        }
        if (request.decision() == PreferenceDecision.APPROVE) {
            ObjectNode patch =
                    json.createObjectNode().put("walkDurationMin", saved.proposedWalkDurationMin());
            profiles.patch(userId, patch);
        }
        Instant now = Instant.now();
        jdbc.update(
                "UPDATE trip_preference_update SET status=?,decided_at=? WHERE id=? AND user_id=?",
                decision,
                Timestamp.from(now),
                saved.id(),
                userId);
        audit.record(actor, userId, "TRIP_PREFERENCE_" + decision, "preferenceUpdate", saved.id());
        return new PreferenceUpdateView(
                saved.id(), saved.proposedWalkDurationMin(), decision, saved.createdAt());
    }

    @Transactional
    public ShareView createShare(String userId, String tripId, ShareRequest request) {
        var actor = access.requireElderOwner(userId);
        var trip = trips.lockOwned(tripId, userId);
        if (trip == null || !"FINISHED".equals(trip.getStatus()))
            throw BusinessException.notFound("已结束的游览记录不存在");
        if (request.mediaIds().size() > 3
                || new HashSet<>(request.mediaIds()).size() != request.mediaIds().size())
            throw BusinessException.invalid("最多选择3个不同的分享附件");
        var allMedia =
                jdbc.queryForList(
                        "SELECT id FROM trip_media WHERE trip_id=? AND user_id=?",
                        String.class,
                        tripId,
                        userId);
        if (!allMedia.containsAll(request.mediaIds()))
            throw BusinessException.notFound("分享附件不属于本次游览");
        String shareId = UUID.randomUUID().toString();
        Instant now = Instant.now();
        Instant expires = now.plus(Duration.ofDays(7));
        jdbc.update(
                "INSERT INTO travel_record_share(id,trip_id,user_id,created_at,expires_at) VALUES (?,?,?,?,?)",
                shareId,
                tripId,
                userId,
                Timestamp.from(now),
                Timestamp.from(expires));
        for (String mediaId : request.mediaIds())
            jdbc.update(
                    "INSERT INTO travel_record_share_media(share_id,media_id) VALUES (?,?)",
                    shareId,
                    mediaId);
        var detail = records.get(userId, tripId);
        String summary =
                "银龄智游游览小结："
                        + detail.routeName()
                        + "；游览时间 "
                        + detail.startedAt()
                        + " 至 "
                        + detail.finishedAt()
                        + "；记录到访景点 "
                        + detail.visitedSpotIds().size()
                        + " 个。到访信息由客户端上报，尚未现场核验。";
        var media = mediaSummaries(tripId, userId, request.mediaIds());
        audit.record(actor, userId, "TRAVEL_RECORD_SHARED", "travelRecordShare", shareId);
        return new ShareView(
                shareId, "/api/v3/travel-record-shares/" + shareId, summary, expires, media);
    }

    @Transactional(readOnly = true)
    public SharedRecord sharedRecord(String shareId) {
        ShareRow share = share(shareId);
        if (share.revokedAt() != null || !share.expiresAt().isAfter(Instant.now()))
            throw BusinessException.notFound("分享链接不存在或已过期");
        var route = readRoute(share.routeSnapshot());
        var progressView = progress.getProgressForVerifiedTrip(share.tripId(), share.userId());
        List<String> visited = progressView == null ? List.of() : progressView.visitedSpotIds();
        long duration = Duration.between(share.startedAt(), share.finishedAt()).getSeconds();
        List<String> mediaUrls =
                jdbc
                        .queryForList(
                                "SELECT media_id FROM travel_record_share_media WHERE share_id=? ORDER BY media_id",
                                String.class,
                                shareId)
                        .stream()
                        .map(id -> "/api/v3/travel-record-shares/" + shareId + "/media/" + id)
                        .toList();
        String text =
                "银龄智游游览小结：" + route.name() + "；记录到访景点 " + visited.size() + " 个。到访信息由客户端上报，尚未现场核验。";
        return new SharedRecord(
                text,
                route.name(),
                share.startedAt(),
                share.finishedAt(),
                duration,
                visited,
                mediaUrls,
                share.expiresAt());
    }

    @Transactional(readOnly = true)
    public BinaryMedia sharedMedia(String shareId, String mediaId) {
        ShareRow share = share(shareId);
        if (share.revokedAt() != null || !share.expiresAt().isAfter(Instant.now()))
            throw BusinessException.notFound("分享链接不存在或已过期");
        var rows =
                jdbc.query(
                        "SELECT m.mime_type,m.file_name,m.content FROM travel_record_share_media s JOIN trip_media m ON m.id=s.media_id WHERE s.share_id=? AND s.media_id=? AND m.trip_id=? AND m.user_id=?",
                        (rs, n) ->
                                new BinaryMedia(
                                        rs.getBytes("content"),
                                        rs.getString("mime_type"),
                                        rs.getString("file_name")),
                        shareId,
                        mediaId,
                        share.tripId(),
                        share.userId());
        if (rows.isEmpty()) throw BusinessException.notFound("分享附件不存在");
        return rows.getFirst();
    }

    @Transactional
    public void revokeShare(String userId, String tripId, String shareId) {
        var actor = access.requireElderOwner(userId);
        int updated =
                jdbc.update(
                        "UPDATE travel_record_share SET revoked_at=? WHERE id=? AND trip_id=? AND user_id=? AND revoked_at IS NULL",
                        Timestamp.from(Instant.now()),
                        shareId,
                        tripId,
                        userId);
        if (updated == 0) throw BusinessException.notFound("分享链接不存在");
        audit.record(actor, userId, "TRAVEL_RECORD_SHARE_REVOKED", "travelRecordShare", shareId);
    }

    private ShareRow share(String id) {
        var rows =
                jdbc.query(
                        "SELECT s.id,s.trip_id,s.user_id,s.expires_at,s.revoked_at,t.route_snapshot,t.created_at,t.finished_at FROM travel_record_share s JOIN trip t ON t.id=s.trip_id AND t.user_id=s.user_id WHERE s.id=?",
                        (rs, n) ->
                                new ShareRow(
                                        rs.getString("id"),
                                        rs.getString("trip_id"),
                                        rs.getString("user_id"),
                                        rs.getTimestamp("expires_at").toInstant(),
                                        rs.getTimestamp("revoked_at") == null
                                                ? null
                                                : rs.getTimestamp("revoked_at").toInstant(),
                                        rs.getString("route_snapshot"),
                                        rs.getTimestamp("created_at").toInstant(),
                                        rs.getTimestamp("finished_at").toInstant()),
                        id);
        if (rows.isEmpty()) throw BusinessException.notFound("分享链接不存在");
        return rows.getFirst();
    }

    private List<MediaSummary> mediaSummaries(String tripId, String userId, List<String> ids) {
        if (ids.isEmpty()) return List.of();
        String marks = String.join(",", Collections.nCopies(ids.size(), "?"));
        Object[] args = new Object[ids.size() + 2];
        args[0] = tripId;
        args[1] = userId;
        for (int i = 0; i < ids.size(); i++) args[i + 2] = ids.get(i);
        return jdbc.query(
                "SELECT id,mime_type,file_name,size_bytes,created_at FROM trip_media WHERE trip_id=? AND user_id=? AND id IN ("
                        + marks
                        + ") ORDER BY created_at,id",
                (rs, n) ->
                        new MediaSummary(
                                rs.getString("id"),
                                rs.getString("mime_type"),
                                rs.getString("file_name"),
                                rs.getLong("size_bytes"),
                                rs.getTimestamp("created_at").toInstant()),
                args);
    }

    private String sniff(byte[] bytes) {
        if (starts(bytes, 0xff, 0xd8, 0xff)) return "image/jpeg";
        if (starts(bytes, 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)) return "image/png";
        if (bytes.length >= 12 && ascii(bytes, 0, "RIFF") && ascii(bytes, 8, "WEBP"))
            return "image/webp";
        if (bytes.length >= 12 && ascii(bytes, 0, "RIFF") && ascii(bytes, 8, "WAVE"))
            return "audio/wav";
        if (starts(bytes, 0x4f, 0x67, 0x67, 0x53)) return "audio/ogg";
        if (starts(bytes, 0x1a, 0x45, 0xdf, 0xa3)) return "audio/webm";
        if (bytes.length >= 8 && ascii(bytes, 4, "ftyp")) return "audio/mp4";
        if (starts(bytes, 0x49, 0x44, 0x33)
                || (bytes.length >= 2 && (bytes[0] & 0xff) == 0xff && (bytes[1] & 0xe0) == 0xe0))
            return "audio/mpeg";
        return null;
    }

    private boolean starts(byte[] bytes, int... prefix) {
        if (bytes.length < prefix.length) return false;
        for (int i = 0; i < prefix.length; i++) if ((bytes[i] & 0xff) != prefix[i]) return false;
        return true;
    }

    private boolean ascii(byte[] bytes, int offset, String value) {
        if (bytes.length < offset + value.length()) return false;
        for (int i = 0; i < value.length(); i++)
            if (bytes[offset + i] != (byte) value.charAt(i)) return false;
        return true;
    }

    private String safeFileName(String original, String mimeType) {
        String base = original == null ? "" : original.replace('\\', '/');
        base = base.substring(base.lastIndexOf('/') + 1).replaceAll("[^A-Za-z0-9._-]", "_");
        if (base.isBlank() || base.length() > 120) {
            String ext =
                    switch (mimeType) {
                        case "image/jpeg" -> ".jpg";
                        case "image/png" -> ".png";
                        case "image/webp" -> ".webp";
                        case "audio/wav" -> ".wav";
                        case "audio/mpeg" -> ".mp3";
                        case "audio/webm" -> ".webm";
                        case "audio/ogg" -> ".ogg";
                        default -> ".m4a";
                    };
            return "travel-media" + ext;
        }
        return base;
    }

    private cn.silvertravel.platform.scenic.ScenicData.Route readRoute(String value) {
        try {
            return json.readValue(value, cn.silvertravel.platform.scenic.ScenicData.Route.class);
        } catch (java.io.IOException exception) {
            throw new IllegalStateException("Stored route is invalid", exception);
        }
    }
}
