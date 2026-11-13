package cn.silvertravel.platform.help;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.common.idempotency.IdempotencyService;
import cn.silvertravel.platform.help.HelpModels.*;
import cn.silvertravel.platform.help.persistence.*;
import cn.silvertravel.platform.notification.HelpNotificationService;
import cn.silvertravel.platform.scenic.ScenicDataProvider;
import cn.silvertravel.platform.security.*;
import cn.silvertravel.platform.trip.persistence.TripMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.UUID;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class HelpEventService {
    private final HelpEventMapper mapper;
    private final TripMapper trips;
    private final ScenicDataProvider scenic;
    private final BusinessAccessPolicy access;
    private final AuditService audit;
    private final HelpNotificationService notifications;
    private final IdempotencyService idempotency;
    private final ObjectMapper json;

    public HelpEventService(
            HelpEventMapper mapper,
            TripMapper trips,
            ScenicDataProvider scenic,
            BusinessAccessPolicy access,
            AuditService audit,
            HelpNotificationService notifications,
            IdempotencyService idempotency,
            ObjectMapper json) {
        this.mapper = mapper;
        this.trips = trips;
        this.scenic = scenic;
        this.access = access;
        this.audit = audit;
        this.notifications = notifications;
        this.idempotency = idempotency;
        this.json = json;
    }

    @Transactional
    public View create(CreateRequest request, String queryUserId, String key) {
        var actor = access.requireElderOwner(request.userId());
        if (queryUserId != null && !queryUserId.equals(request.userId())) {
            throw BusinessException.invalid("查询参数与请求正文 userId 不一致");
        }
        var normalized =
                new CreateRequest(
                        request.userId(),
                        request.tripId(),
                        request.type(),
                        request.location(),
                        request.locationNote() == null || request.locationNote().isBlank()
                                ? null
                                : request.locationNote().strip());
        return idempotency.execute(
                actor,
                "help.create",
                key,
                normalized,
                View.class,
                View::id,
                () -> createOnce(normalized, actor));
    }

    private View createOnce(CreateRequest request, CurrentActor actor) {
        var trip =
                request.tripId() == null
                        ? null
                        : trips.findOwned(request.tripId(), request.userId());
        if (request.tripId() != null && trip == null) {
            throw BusinessException.notFound("关联游览不存在");
        }
        String scenicId = trip == null ? null : trip.getScenicId();
        if (request.location() != null && request.location().spotId() != null) {
            String spotId = request.location().spotId();
            var matches =
                    scenic.listScenics().stream()
                            .filter(
                                    site ->
                                            scenic
                                                    .findById(site.id())
                                                    .orElseThrow()
                                                    .spots()
                                                    .stream()
                                                    .anyMatch(spot -> spot.id().equals(spotId)))
                            .toList();
            if (matches.size() != 1
                    || (scenicId != null && !scenicId.equals(matches.getFirst().id()))) {
                throw BusinessException.invalid("景点定位不存在、归属不符或存在歧义");
            }
            scenicId = matches.getFirst().id();
        }
        Instant now = Instant.now().truncatedTo(ChronoUnit.MICROS);
        var event = new HelpEventEntity();
        event.setId(UUID.randomUUID().toString());
        event.setUserId(request.userId());
        event.setTripId(request.tripId());
        event.setType(request.type().name());
        event.setLocationJson(request.location() == null ? null : encode(request.location()));
        event.setLocationNote(request.locationNote());
        event.setBusinessStatus(Status.OPEN.name());
        event.setDispatchRecipientType(scenicId == null ? "official" : "scenic");
        event.setDispatchRecipientId(scenicId == null ? "official-demo-desk" : scenicId);
        event.setCreatedAt(now);
        event.setUpdatedAt(now);
        mapper.insert(event);
        notifications.enqueue(event);
        audit.record(actor, request.userId(), "HELP_CREATED", "helpEvent", event.getId());
        return view(event);
    }

    @Transactional(readOnly = true)
    public List<View> list(String userId) {
        String scope = readScope(userId);
        return mapper.findList(scope).stream().map(this::view).toList();
    }

    @Transactional(readOnly = true)
    public View get(String id, String userId) {
        String scope = readScope(userId);
        var event = mapper.selectById(id);
        requireVisible(event, scope);
        return view(event);
    }

    @Transactional
    public View acknowledge(String id, String userId) {
        var actor = access.requireHelpAcknowledge();
        var event = mapper.lockById(id);
        requireVisible(event, filter(userId));
        if (!Status.OPEN.name().equals(event.getBusinessStatus())) {
            throw BusinessException.conflict("求助已被接单或解决");
        }
        event.setHandlerActorId(actor.id());
        event.setBusinessStatus(Status.ACKNOWLEDGED.name());
        event.setUpdatedAt(Instant.now().truncatedTo(ChronoUnit.MICROS));
        mapper.updateById(event);
        notifications.enqueue(event);
        audit.record(actor, event.getUserId(), "HELP_ACKNOWLEDGED", "helpEvent", id);
        return view(event);
    }

    @Transactional
    public View resolve(String id, String userId) {
        access.requireHelpAcknowledge();
        var event = mapper.lockById(id);
        requireVisible(event, filter(userId));
        var actor = access.requireHelpResolve(event.getHandlerActorId());
        if (!Status.ACKNOWLEDGED.name().equals(event.getBusinessStatus())) {
            throw BusinessException.conflict("仅已接单的求助可以解决");
        }
        event.setBusinessStatus(Status.RESOLVED.name());
        event.setUpdatedAt(Instant.now().truncatedTo(ChronoUnit.MICROS));
        mapper.updateById(event);
        notifications.enqueue(event);
        audit.record(actor, event.getUserId(), "HELP_RESOLVED", "helpEvent", id);
        return view(event);
    }

    private String readScope(String userId) {
        var actor = access.currentActor();
        if (actor.role() == ActorRole.ELDER) {
            if (userId != null) {
                access.requireElderOwner(userId);
            }
            return actor.elderUserId();
        }
        access.requireHelpAcknowledge();
        return filter(userId);
    }

    private String filter(String userId) {
        if (userId != null && userId.isBlank()) {
            throw BusinessException.invalid("userId 不能为空");
        }
        return userId;
    }

    private void requireVisible(HelpEventEntity event, String userId) {
        if (event == null || (userId != null && !userId.equals(event.getUserId()))) {
            throw BusinessException.notFound("求助记录不存在");
        }
    }

    private View view(HelpEventEntity event) {
        Location location = null;
        if (event.getLocationJson() != null) {
            try {
                location = json.readValue(event.getLocationJson(), Location.class);
            } catch (JsonProcessingException exception) {
                throw new IllegalStateException("定位记录无效", exception);
            }
        }
        return new View(
                event.getId(),
                event.getUserId(),
                event.getTripId(),
                Type.valueOf(event.getType()),
                location,
                event.getLocationNote(),
                Status.valueOf(event.getBusinessStatus()),
                notifications.latest(event.getId()),
                event.getCreatedAt(),
                event.getUpdatedAt());
    }

    private String encode(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("无法保存求助定位", exception);
        }
    }
}
