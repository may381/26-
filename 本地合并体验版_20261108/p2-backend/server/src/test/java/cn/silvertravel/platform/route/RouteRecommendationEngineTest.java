package cn.silvertravel.platform.route;

import static org.assertj.core.api.Assertions.*;

import cn.silvertravel.platform.profile.ProfileFields.WalkSpeed;
import cn.silvertravel.platform.scenic.*;
import cn.silvertravel.platform.scenic.ScenicData.Route;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Validation;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class RouteRecommendationEngineTest {
    private final RouteRecommendationEngine engine = new RouteRecommendationEngine();

    private List<Route> routes() {
        try (var validator = Validation.buildDefaultValidatorFactory()) {
            return new ScenicDatasetImporter(
                            new ObjectMapper().findAndRegisterModules(), validator.getValidator())
                    .read(new ClassPathResource("fixtures/qingfeng.json"))
                    .routes();
        }
    }

    @Test
    void preferencesProduceDistinctDeterministicChoices() {
        List<Route> routes = routes();
        assertThat(
                        engine.choose(
                                        routes,
                                        new RouteRecommendationEngine.Preferences(
                                                WalkSpeed.MEDIUM, 40, true))
                                .routeId())
                .isEqualTo("r1");
        assertThat(
                        engine.choose(
                                        routes,
                                        new RouteRecommendationEngine.Preferences(
                                                WalkSpeed.MEDIUM, 60, false))
                                .routeId())
                .isEqualTo("r2");
        var preferences = new RouteRecommendationEngine.Preferences(WalkSpeed.MEDIUM, 70, false);
        assertThat(engine.choose(routes, preferences).routeId()).isEqualTo("r3");
        var reversed = new ArrayList<>(routes);
        Collections.reverse(reversed);
        assertThat(engine.choose(reversed, preferences))
                .isEqualTo(engine.choose(routes, preferences));
    }

    @Test
    void speedAndNoMatchAreExplainedWithoutClaimingZeroSteps() {
        Route easy = routes().getFirst();
        assertThat(engine.estimatedMinutes(easy, WalkSpeed.SLOW)).isEqualTo(60);
        assertThat(engine.estimatedMinutes(easy, WalkSpeed.FAST)).isEqualTo(32);
        var choice =
                engine.choose(
                        routes(),
                        new RouteRecommendationEngine.Preferences(WalkSpeed.SLOW, 20, true));
        assertThat(choice.routeId()).isEqualTo("r1");
        assertThat(choice.reason()).contains("无完全匹配，此为最接近方案", "20 级台阶", "60 分钟");
    }
}
