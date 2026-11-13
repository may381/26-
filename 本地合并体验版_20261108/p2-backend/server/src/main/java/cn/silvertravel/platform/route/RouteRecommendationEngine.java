package cn.silvertravel.platform.route;

import cn.silvertravel.platform.profile.ProfileFields.WalkSpeed;
import cn.silvertravel.platform.scenic.ScenicData.Route;
import java.util.Comparator;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class RouteRecommendationEngine {
    public record Preferences(WalkSpeed walkSpeed, int durationMin, boolean avoidSteps) {}

    public record Choice(String routeId, String reason) {}

    public Choice choose(List<Route> routes, Preferences preferences) {
        if (routes.isEmpty()) {
            throw new IllegalArgumentException("No routes to recommend");
        }
        int minimumSteps = routes.stream().mapToInt(Route::totalSteps).min().orElseThrow();
        List<Route> matches =
                routes.stream()
                        .filter(
                                route ->
                                        estimatedMinutes(route, preferences.walkSpeed())
                                                        <= preferences.durationMin()
                                                && (!preferences.avoidSteps()
                                                        || route.totalSteps() == minimumSteps))
                        .toList();
        boolean fallback = matches.isEmpty();
        Route selected =
                (fallback ? routes : matches)
                        .stream()
                                .min(
                                        Comparator.comparingDouble(
                                                        (Route route) ->
                                                                score(
                                                                        route,
                                                                        preferences,
                                                                        minimumSteps,
                                                                        fallback))
                                                .thenComparing(Route::id))
                                .orElseThrow();
        String reason =
                (fallback ? "无完全匹配，此为最接近方案；" : "")
                        + "按步速估算约 "
                        + estimatedMinutes(selected, preferences.walkSpeed())
                        + " 分钟，"
                        + selected.totalSteps()
                        + " 级台阶，"
                        + selected.restCount()
                        + " 处休息点"
                        + (preferences.avoidSteps() && selected.totalSteps() == minimumSteps
                                ? "；候选中台阶最少"
                                : "");
        return new Choice(selected.id(), reason);
    }

    public int estimatedMinutes(Route route, WalkSpeed speed) {
        return switch (speed) {
            case SLOW -> (route.totalWalkMin() * 3 + 1) / 2;
            case MEDIUM -> route.totalWalkMin();
            case FAST -> (route.totalWalkMin() * 4 + 4) / 5;
        };
    }

    private double score(Route route, Preferences preferences, int minimumSteps, boolean fallback) {
        int minutes = estimatedMinutes(route, preferences.walkSpeed());
        return Math.abs(minutes - preferences.durationMin())
                + route.totalSteps() * 0.05
                - route.restCount() * 2
                + (preferences.avoidSteps() ? (route.totalSteps() - minimumSteps) * 2.0 : 0)
                + (fallback ? Math.max(0, minutes - preferences.durationMin()) * 10.0 : 0);
    }
}
