package cn.silvertravel.platform.route;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.profile.ProfileFields.WalkSpeed;
import cn.silvertravel.platform.profile.ProfileService;
import cn.silvertravel.platform.scenic.ScenicData.*;
import java.time.Instant;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class RouteService {
    public record Candidate(
            String id,
            String name,
            List<String> spots,
            List<Segment> segments,
            Source source,
            Instant updatedAt,
            String verifiedBy,
            boolean recommended,
            String reason) {}

    public record Result(List<Candidate> routes) {}

    private final RouteCatalog catalog;
    private final ProfileService profiles;
    private final RouteRecommendationEngine engine;

    public RouteService(
            RouteCatalog catalog, ProfileService profiles, RouteRecommendationEngine engine) {
        this.catalog = catalog;
        this.profiles = profiles;
        this.engine = engine;
    }

    @Transactional(readOnly = true)
    public Result recommend(String userId, Integer duration, Boolean avoidSteps) {
        WalkSpeed speed = WalkSpeed.MEDIUM;
        int budget = 60;
        boolean avoid = false;
        if (userId != null) {
            if (userId.isBlank()) {
                throw BusinessException.invalid("userId 不能为空");
            }
            var profile = profiles.get(userId);
            speed = profile.walkSpeed();
            budget = profile.walkDurationMin();
            avoid = profile.avoidSteps();
        }
        if (duration != null) {
            if (duration < 1 || duration > 1440) {
                throw BusinessException.invalid("步行时长应为 1～1440 分钟");
            }
            budget = duration;
        }
        if (avoidSteps != null) {
            avoid = avoidSteps;
        }
        List<Route> routes = catalog.all().stream().map(RouteCatalog.Entry::route).toList();
        if (routes.isEmpty()) {
            throw BusinessException.notFound("当前没有可用路线");
        }
        var choice =
                engine.choose(
                        routes, new RouteRecommendationEngine.Preferences(speed, budget, avoid));
        return new Result(
                routes.stream()
                        .map(
                                route ->
                                        new Candidate(
                                                route.id(),
                                                route.name(),
                                                route.spots(),
                                                route.segments(),
                                                route.source(),
                                                route.updatedAt(),
                                                route.verifiedBy(),
                                                route.id().equals(choice.routeId()),
                                                route.id().equals(choice.routeId())
                                                        ? choice.reason()
                                                        : null))
                        .toList());
    }
}
