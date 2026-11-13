package cn.silvertravel.platform.family;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.route.RouteCatalog;
import cn.silvertravel.platform.scenic.ScenicData.Route;
import cn.silvertravel.platform.security.ActorRole;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class FamilyCollaborationService {
    public enum Decision {
        ACCEPT,
        REJECT
    }

    public record SuggestionRequest(
            @NotBlank @Size(max = 128) String routeId, @Size(max = 500) String note) {}

    public record DecisionRequest(
            @NotNull Decision decision, @Size(max = 500) String note) {}

    public record SuggestionView(
            String id,
            String userId,
            String familyRelationId,
            String familyActorId,
            String routeId,
            Route route,
            String note,
            String status,
            String decisionNote,
            Instant createdAt,
            Instant decidedAt) {}

    public record MessageRequest(@NotBlank @Size(max = 2000) String text) {}

    public record MessageView(
            String id,
            String userId,
            String familyRelationId,
            String senderActorId,
            String senderRole,
            String text,
            Instant createdAt,
            Instant readAt) {}

    private final JdbcTemplate jdbc;
    private final RouteCatalog routes;
    private final BusinessAccessPolicy access;
    private final AuditService audit;
    private final ObjectMapper json;

    public FamilyCollaborationService(
            JdbcTemplate jdbc,
            RouteCatalog routes,
            BusinessAccessPolicy access,
            AuditService audit,
            ObjectMapper json) {
        this.jdbc = jdbc;
        this.routes = routes;
        this.access = access;
        this.audit = audit;
        this.json = json;
    }

    @Transactional
    public SuggestionView suggest(String userId, SuggestionRequest request) {
        var actor = access.currentActor();
        if (actor.role() != ActorRole.FAMILY)
            throw new AccessDeniedException("Family identity required");
        var relation = familyRelation(actor.id(), userId, true);
        var route = routes.require(request.routeId());
        var rows =
                jdbc.query(
                        "SELECT id FROM family_relation WHERE id=? AND user_id=? FOR UPDATE",
                        (rs, n) -> rs.getString("id"),
                        relation.id,
                        userId);
        if (rows.isEmpty()) throw BusinessException.notFound("有效家属关系不存在");
        String id = UUID.randomUUID().toString();
        Instant now = Instant.now();
        jdbc.update(
                "INSERT INTO family_route_suggestion(id,family_relation_id,user_id,family_actor_id,route_id,route_snapshot,note,status,created_at) VALUES (?,?,?,?,?,?,?,'PENDING',?)",
                id,
                relation.id,
                userId,
                actor.id(),
                route.route().id(),
                encode(route.route()),
                normalize(request.note()),
                Timestamp.from(now));
        audit.record(actor, userId, "FAMILY_ROUTE_SUGGESTED", "routeSuggestion", id);
        return new SuggestionView(
                id,
                userId,
                relation.id,
                actor.id(),
                route.route().id(),
                route.route(),
                normalize(request.note()),
                "PENDING",
                null,
                now,
                null);
    }

    @Transactional(readOnly = true)
    public List<SuggestionView> suggestions(String userId) {
        access.requireElderOwner(userId);
        return jdbc.query(
                "SELECT id,family_relation_id,user_id,family_actor_id,route_id,route_snapshot,note,status,decision_note,created_at,decided_at FROM family_route_suggestion WHERE user_id=? ORDER BY created_at DESC,id",
                (rs, n) -> suggestion(rs),
                userId);
    }

    @Transactional
    public SuggestionView decide(String userId, String id, DecisionRequest request) {
        var actor = access.requireElderOwner(userId);
        var rows =
                jdbc.query(
                        "SELECT id,family_relation_id,user_id,family_actor_id,route_id,route_snapshot,note,status,decision_note,created_at,decided_at FROM family_route_suggestion WHERE id=? AND user_id=? FOR UPDATE",
                        (rs, n) -> suggestion(rs),
                        id,
                        userId);
        if (rows.isEmpty()) throw BusinessException.notFound("路线建议不存在");
        SuggestionView saved = rows.getFirst();
        if (!"PENDING".equals(saved.status()))
            throw BusinessException.conflict("路线建议已经处理");
        var relation =
                jdbc.queryForList(
                        "SELECT status,remote_planning FROM family_relation WHERE id=? AND user_id=? FOR UPDATE",
                        saved.familyRelationId(),
                        userId);
        if (relation.isEmpty() || !"ACTIVE".equals(relation.getFirst().get("status")))
            throw BusinessException.conflict("家属授权已失效，不能采纳该建议");
        if (!Boolean.TRUE.equals(relation.getFirst().get("remote_planning")))
            throw new AccessDeniedException("Remote planning is not authorized");
        Instant now = Instant.now();
        String status = request.decision() == Decision.ACCEPT ? "ACCEPTED" : "REJECTED";
        jdbc.update(
                "UPDATE family_route_suggestion SET status=?,decision_note=?,decided_at=? WHERE id=? AND user_id=?",
                status,
                normalize(request.note()),
                Timestamp.from(now),
                id,
                userId);
        audit.record(actor, userId, "FAMILY_ROUTE_SUGGESTION_" + status, "routeSuggestion", id);
        return new SuggestionView(
                saved.id(),
                saved.userId(),
                saved.familyRelationId(),
                saved.familyActorId(),
                saved.routeId(),
                saved.route(),
                saved.note(),
                status,
                normalize(request.note()),
                saved.createdAt(),
                now);
    }

    @Transactional
    public MessageView sendMessage(String userId, MessageRequest request) {
        var actor = access.currentActor();
        if (actor.role() != ActorRole.FAMILY)
            throw new AccessDeniedException("Family identity required");
        var relation = familyRelation(actor.id(), userId, false);
        String id = UUID.randomUUID().toString();
        Instant now = Instant.now();
        jdbc.update(
                "INSERT INTO family_message(id,family_relation_id,user_id,sender_actor_id,sender_role,body,created_at) VALUES (?,?,?,?,'FAMILY',?,?)",
                id,
                relation.id,
                userId,
                actor.id(),
                request.text().strip(),
                Timestamp.from(now));
        audit.record(actor, userId, "FAMILY_MESSAGE_SENT", "familyMessage", id);
        return new MessageView(
                id, userId, relation.id, actor.id(), "FAMILY", request.text().strip(), now, null);
    }

    @Transactional
    public List<MessageView> inbox(String userId, int limit) {
        access.requireElderOwner(userId);
        if (limit < 1 || limit > 100) throw BusinessException.invalid("limit 必须为 1～100");
        Instant now = Instant.now();
        var unreadIds =
                jdbc.queryForList(
                        "SELECT m.id FROM family_message m JOIN family_relation f ON f.id=m.family_relation_id AND f.user_id=m.user_id WHERE m.user_id=? AND m.sender_role='FAMILY' AND m.read_at IS NULL AND f.status='ACTIVE' ORDER BY m.created_at DESC,m.id LIMIT ? FOR UPDATE",
                        String.class,
                        userId,
                        limit);
        for (String messageId : unreadIds)
            jdbc.update(
                    "UPDATE family_message SET read_at=? WHERE id=? AND user_id=? AND read_at IS NULL",
                    Timestamp.from(now),
                    messageId,
                    userId);
        return jdbc.query(
                "SELECT m.id,m.user_id,m.family_relation_id,m.sender_actor_id,m.sender_role,m.body,m.created_at,m.read_at FROM family_message m JOIN family_relation f ON f.id=m.family_relation_id AND f.user_id=m.user_id WHERE m.user_id=? AND m.sender_role='FAMILY' AND f.status='ACTIVE' ORDER BY m.created_at DESC,m.id LIMIT ?",
                (rs, n) ->
                        new MessageView(
                                rs.getString("id"),
                                rs.getString("user_id"),
                                rs.getString("family_relation_id"),
                                rs.getString("sender_actor_id"),
                                rs.getString("sender_role"),
                                rs.getString("body"),
                                rs.getTimestamp("created_at").toInstant(),
                                rs.getTimestamp("read_at").toInstant()),
                userId,
                limit);
    }

    private record RelationRef(String id) {}

    private RelationRef familyRelation(String actorId, String userId, boolean planning) {
        if (userId == null || userId.isBlank() || userId.length() > 128)
            throw BusinessException.invalid("userId 无效");
        String sql =
                "SELECT f.id FROM family_identity_link l JOIN family_relation f ON f.id=l.family_relation_id AND f.user_id=l.user_id WHERE l.family_actor_id=? AND l.user_id=? AND f.status='ACTIVE'"
                        + (planning ? " AND f.remote_planning=TRUE" : "")
                        + " FOR SHARE";
        var rows = jdbc.query(sql, (rs, n) -> new RelationRef(rs.getString("id")), actorId, userId);
        if (rows.size() != 1)
            throw BusinessException.notFound("没有可用的老人家属授权关系");
        return rows.getFirst();
    }

    private SuggestionView suggestion(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new SuggestionView(
                rs.getString("id"),
                rs.getString("user_id"),
                rs.getString("family_relation_id"),
                rs.getString("family_actor_id"),
                rs.getString("route_id"),
                readRoute(rs.getString("route_snapshot")),
                rs.getString("note"),
                rs.getString("status"),
                rs.getString("decision_note"),
                rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("decided_at") == null
                        ? null
                        : rs.getTimestamp("decided_at").toInstant());
    }

    private Route readRoute(String value) {
        try {
            return json.readValue(value, Route.class);
        } catch (java.io.IOException exception) {
            throw new IllegalStateException("Stored suggested route is invalid", exception);
        }
    }

    private String encode(Route route) {
        try {
            return json.writeValueAsString(route);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Unable to store route suggestion", exception);
        }
    }

    private String normalize(String note) {
        return note == null || note.isBlank() ? null : note.strip();
    }
}
