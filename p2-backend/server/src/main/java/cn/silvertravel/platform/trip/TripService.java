package cn.silvertravel.platform.trip;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.profile.persistence.ProfileMapper;
import cn.silvertravel.platform.route.RouteCatalog;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import cn.silvertravel.platform.trip.persistence.*;
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
public class TripService {
    public enum Status {
        ACTIVE,
        FINISHED,
        CANCELLED
    }

    public record View(
            String id,
            String userId,
            String routeId,
            Status status,
            Instant startedAt,
            long tripVersion,
            long progressSeq,
            String currentSpotId,
            List<String> visitedSpotIds,
            List<String> skippedSpotIds,
            List<String> remainingSpotIds,
            Instant estimatedFinishAt,
            TripJourneyService.RestView activeRest) {}

    private final TripMapper mapper;
    private final ProfileMapper profiles;
    private final RouteCatalog catalog;
    private final BusinessAccessPolicy access;
    private final AuditService audit;
    private final ObjectMapper json;
    private final TripJourneyService journey;

    public TripService(
            TripMapper mapper,
            ProfileMapper profiles,
            RouteCatalog catalog,
            BusinessAccessPolicy access,
            AuditService audit,
            ObjectMapper json,
            TripJourneyService journey) {
        this.mapper = mapper;
        this.profiles = profiles;
        this.catalog = catalog;
        this.access = access;
        this.audit = audit;
        this.json = json;
        this.journey = journey;
    }

    @Transactional
    public View create(String userId, String routeId) {
        var actor = access.requireElderOwner(userId);
        if (profiles.lockByUserId(userId) == null) {
            throw BusinessException.notFound("请先建立老人档案");
        }
        if (mapper.findActive(userId) != null) {
            throw BusinessException.conflict("已有进行中的游览");
        }
        var selected = catalog.require(routeId);
        TripEntity trip = new TripEntity();
        trip.setId(UUID.randomUUID().toString());
        trip.setUserId(userId);
        trip.setRouteId(routeId);
        trip.setScenicId(selected.dataset().scenic().id());
        trip.setRouteSource(selected.route().source().name());
        try {
            trip.setRouteSnapshot(json.writeValueAsString(selected.route()));
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("无法保存路线快照", exception);
        }
        trip.setStatus(Status.ACTIVE.name());
        trip.setCreatedAt(Instant.now().truncatedTo(ChronoUnit.MICROS));
        trip.setTripVersion(1L);
        mapper.insert(trip);
        audit.record(actor, userId, "TRIP_STARTED", "trip", trip.getId());
        return journey.view(trip);
    }

    @Transactional(readOnly = true)
    public View active(String userId) {
        access.requireElderOwner(userId);
        TripEntity trip = mapper.findActive(userId);
        return trip == null ? null : journey.view(trip);
    }

    @Transactional(readOnly = true)
    public View get(String userId, String id) {
        access.requireElderOwner(userId);
        TripEntity trip = mapper.findOwned(id, userId);
        if (trip == null) {
            throw BusinessException.notFound("游览记录不存在");
        }
        return journey.view(trip);
    }

    @Transactional
    public View finish(String userId, String id) {
        var actor = access.requireElderOwner(userId);
        TripEntity trip = mapper.lockOwned(id, userId);
        if (trip == null) {
            throw BusinessException.notFound("游览记录不存在");
        }
        if (!Status.ACTIVE.name().equals(trip.getStatus())) {
            throw BusinessException.conflict("游览已结束");
        }
        trip.setStatus(Status.FINISHED.name());
        trip.setFinishedAt(Instant.now().truncatedTo(ChronoUnit.MICROS));
        trip.setTripVersion(trip.getTripVersion() + 1);
        journey.finishOpenRest(id, trip.getFinishedAt());
        mapper.updateById(trip);
        audit.record(actor, userId, "TRIP_FINISHED", "trip", id);
        return journey.view(trip);
    }
}
