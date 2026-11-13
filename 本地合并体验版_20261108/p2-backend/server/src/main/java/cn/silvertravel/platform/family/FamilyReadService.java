package cn.silvertravel.platform.family;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.family.persistence.*;
import cn.silvertravel.platform.help.HelpModels;
import cn.silvertravel.platform.profile.ProfileFields;
import cn.silvertravel.platform.profile.persistence.ProfileMapper;
import cn.silvertravel.platform.scenic.ScenicData.Location;
import cn.silvertravel.platform.security.*;
import cn.silvertravel.platform.trip.TripJourneyService;
import cn.silvertravel.platform.trip.persistence.TripMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class FamilyReadService {
    public record LinkView(String familyRelationId, String userId, String familyActorId) {}

    public record TripSummary(
            String id,
            String routeId,
            String status,
            Instant startedAt,
            boolean progressAvailable,
            List<String> visitedSpotIds,
            String nextSpotId,
            Instant estimatedFinishAt) {}

    public record HelpSummary(
            String id,
            HelpModels.Type type,
            HelpModels.Status businessStatus,
            Instant createdAt,
            Instant updatedAt) {}

    public record SharedLocation(Location coordinate, String source, Instant updatedAt) {}

    private record ProgressSnapshot(
            Location location, List<String> visitedSpotIds, String nextSpotId, Instant updatedAt) {}

    public record ElderView(
            String userId,
            String profileId,
            String nickname,
            String familyRelationId,
            FamilyModels.Permissions permissions,
            TripSummary trip,
            SharedLocation location,
            boolean locationAvailable,
            List<HelpSummary> helpEvents,
            String notice) {}

    public record InboxNotification(
            String id,
            String helpEventId,
            String type,
            HelpModels.Type helpType,
            HelpModels.Status businessStatus,
            HelpModels.NotificationStatus status,
            String deliveryMode,
            Instant createdAt,
            Instant updatedAt) {}

    private record Grant(
            String id, boolean location, boolean progress, boolean alert, boolean planning) {
        FamilyModels.Permissions permissions() {
            return new FamilyModels.Permissions(location, progress, alert, planning);
        }
    }

    private final JdbcTemplate jdbc;
    private final FamilyRelationMapper families;
    private final ProfileMapper profiles;
    private final TripMapper trips;
    private final TripJourneyService journey;
    private final BusinessAccessPolicy access;
    private final MockIdentitySettings settings;
    private final AuditService audit;
    private final ObjectMapper json;

    public FamilyReadService(
            JdbcTemplate jdbc,
            FamilyRelationMapper families,
            ProfileMapper profiles,
            TripMapper trips,
            TripJourneyService journey,
            BusinessAccessPolicy access,
            MockIdentitySettings settings,
            AuditService audit,
            ObjectMapper json) {
        this.jdbc = jdbc;
        this.families = families;
        this.profiles = profiles;
        this.trips = trips;
        this.journey = journey;
        this.access = access;
        this.settings = settings;
        this.audit = audit;
        this.json = json;
    }

    @Transactional
    public LinkView link(String userId, String relationId, String familyActorId) {
        var actor = access.requireElderOwner(userId);
        if (!settings.enabled())
            throw new AccessDeniedException("Mock account association is disabled");
        var family =
                MockIdentityDirectory.find(familyActorId)
                        .orElseThrow(() -> BusinessException.invalid("未知 mock 家属身份"));
        if (family.role() != ActorRole.FAMILY)
            throw BusinessException.invalid("目标必须为 mock FAMILY 身份");
        if (profiles.lockByUserId(userId) == null) throw BusinessException.notFound("老人档案不存在");
        var relation = families.lockOwned(relationId, userId);
        if (relation == null) throw BusinessException.notFound("家属关系不存在");
        if (!"ACTIVE".equals(relation.getStatus())) throw BusinessException.conflict("请先由老人批准家属关系");
        var existing =
                jdbc.queryForList(
                        "SELECT family_actor_id FROM family_identity_link WHERE family_relation_id=?",
                        String.class,
                        relationId);
        if (!existing.isEmpty()) {
            if (!existing.getFirst().equals(familyActorId))
                throw BusinessException.conflict("该关系已关联其他家属身份");
            return new LinkView(relationId, userId, familyActorId);
        }
        var old =
                jdbc.queryForList(
                        """
            SELECT f.id,f.status FROM family_identity_link l JOIN family_relation f ON f.id=l.family_relation_id
            WHERE l.family_actor_id=? AND l.user_id=? FOR UPDATE
            """,
                        familyActorId,
                        userId);
        if (!old.isEmpty()) {
            if (!"REVOKED".equals(old.getFirst().get("status")))
                throw BusinessException.conflict("该家属已关联此老人的其他生效关系");
            jdbc.update(
                    "DELETE FROM family_identity_link WHERE family_actor_id=? AND user_id=?",
                    familyActorId,
                    userId);
        }
        jdbc.update(
                "INSERT INTO family_identity_link(family_relation_id,user_id,family_actor_id,linked_at) VALUES (?,?,?,?)",
                relationId,
                userId,
                familyActorId,
                Timestamp.from(Instant.now()));
        audit.record(actor, userId, "FAMILY_MOCK_ACCOUNT_LINKED", "familyRelation", relationId);
        return new LinkView(relationId, userId, familyActorId);
    }

    @Transactional
    public ElderView elder(String userId) {
        var grant = grant(userId);
        var profile = profiles.findByUserId(userId);
        if (profile == null) throw BusinessException.notFound("老人摘要不存在");
        String nickname;
        try {
            nickname = json.readValue(profile.getProfileJson(), ProfileFields.class).nickname();
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Invalid stored profile", ex);
        }
        TripSummary trip = null;
        SharedLocation location = null;
        if (grant.progress || grant.location) {
            var active = trips.findActive(userId);
            if (active != null) {
                ProgressSnapshot progress = progress(active.getId(), userId);
                if (grant.progress) {
                    String currentRoute =
                            jdbc
                                    .query(
                                            "SELECT route_id FROM trip_route_adjustment WHERE trip_id=? AND user_id=? ORDER BY revision DESC LIMIT 1",
                                            (rs, n) -> rs.getString("route_id"),
                                            active.getId(),
                                            userId)
                                    .stream()
                                    .findFirst()
                                    .orElse(active.getRouteId());
                    trip =
                            new TripSummary(
                                    active.getId(),
                                    currentRoute,
                                    active.getStatus(),
                                    active.getCreatedAt(),
                                    progress != null,
                                    progress == null ? List.of() : progress.visitedSpotIds(),
                                    progress == null ? null : progress.nextSpotId(),
                                    progress == null
                                            ? null
                                            : journey.view(active).estimatedFinishAt());
                }
                if (grant.location && progress != null && progress.location() != null)
                    location =
                            new SharedLocation(
                                    progress.location(), "CLIENT_REPORTED", progress.updatedAt());
            }
        }
        List<HelpSummary> help = null;
        if (grant.alert)
            help =
                    jdbc.query(
                            "SELECT id,type,business_status,created_at,updated_at FROM help_event WHERE user_id=? ORDER BY created_at DESC,id LIMIT 20",
                            (rs, n) ->
                                    new HelpSummary(
                                            rs.getString("id"),
                                            HelpModels.Type.valueOf(rs.getString("type")),
                                            HelpModels.Status.valueOf(
                                                    rs.getString("business_status")),
                                            rs.getTimestamp("created_at").toInstant(),
                                            rs.getTimestamp("updated_at").toInstant()),
                            userId);
        return new ElderView(
                userId,
                profile.getId(),
                nickname,
                grant.id,
                grant.permissions(),
                trip,
                location,
                location != null,
                help,
                "仅返回授权摘要。位置和游览进度由客户端上报，尚未进行现场校验；求助通知仅为模拟。");
    }

    @Transactional
    public List<InboxNotification> notifications(String userId, int limit) {
        var grant = grant(userId);
        if (!grant.alert) throw new AccessDeniedException("Alert sharing is not authorized");
        if (limit < 1 || limit > 100) throw BusinessException.invalid("limit 必须为 1～100");
        return jdbc.query(
                """
                SELECT n.id,n.help_event_id,n.phase,n.status,n.delivery_mode,n.created_at,n.updated_at,
                       h.type,h.business_status
                FROM help_notification n JOIN help_event h ON h.id=n.help_event_id AND h.user_id=n.user_id
                WHERE n.recipient_type='family' AND n.recipient_id=? AND n.user_id=?
                ORDER BY n.created_at DESC,n.id LIMIT ?
                """,
                (rs, n) ->
                        new InboxNotification(
                                rs.getString("id"),
                                rs.getString("help_event_id"),
                                "HELP_" + rs.getString("phase"),
                                HelpModels.Type.valueOf(rs.getString("type")),
                                HelpModels.Status.valueOf(rs.getString("business_status")),
                                HelpModels.NotificationStatus.valueOf(rs.getString("status")),
                                rs.getString("delivery_mode"),
                                rs.getTimestamp("created_at").toInstant(),
                                rs.getTimestamp("updated_at").toInstant()),
                grant.id,
                userId,
                limit);
    }

    private Grant grant(String userId) {
        var actor = access.currentActor();
        if (actor.role() != ActorRole.FAMILY)
            throw new AccessDeniedException("Family identity required");
        if (userId == null || userId.isBlank() || userId.length() > 128)
            throw BusinessException.invalid("userId 无效");
        // Lock current authorization so revoke/permission writes serialize with projection
        // construction.
        var grants =
                jdbc.query(
                        """
                SELECT f.id,f.share_location,f.share_progress,f.share_alert,f.remote_planning
                FROM family_identity_link l JOIN family_relation f ON f.id=l.family_relation_id AND f.user_id=l.user_id
                WHERE l.family_actor_id=? AND l.user_id=? AND f.status='ACTIVE' FOR SHARE
                """,
                        (rs, n) ->
                                new Grant(
                                        rs.getString("id"),
                                        rs.getBoolean("share_location"),
                                        rs.getBoolean("share_progress"),
                                        rs.getBoolean("share_alert"),
                                        rs.getBoolean("remote_planning")),
                        actor.id(),
                        userId);
        if (grants.size() != 1) throw BusinessException.notFound("未找到已生效的授权关系");
        return grants.getFirst();
    }

    private ProgressSnapshot progress(String tripId, String userId) {
        var rows =
                jdbc.query(
                        "SELECT latitude,longitude,visited_spot_ids,next_spot_id,updated_at FROM trip_progress WHERE trip_id=? AND user_id=?",
                        (rs, n) -> {
                            List<String> visited;
                            try {
                                visited =
                                        json.readValue(
                                                rs.getString("visited_spot_ids"),
                                                json.getTypeFactory()
                                                        .constructCollectionType(
                                                                List.class, String.class));
                            } catch (JsonProcessingException exception) {
                                throw new IllegalStateException(
                                        "Invalid stored trip progress", exception);
                            }
                            var lat = rs.getBigDecimal("latitude");
                            var lng = rs.getBigDecimal("longitude");
                            return new ProgressSnapshot(
                                    lat == null || lng == null ? null : new Location(lat, lng),
                                    visited,
                                    rs.getString("next_spot_id"),
                                    rs.getTimestamp("updated_at").toInstant());
                        },
                        tripId,
                        userId);
        return rows.isEmpty() ? null : rows.getFirst();
    }
}
