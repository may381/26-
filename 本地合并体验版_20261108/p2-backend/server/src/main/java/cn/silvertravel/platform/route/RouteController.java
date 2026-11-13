package cn.silvertravel.platform.route;

import cn.silvertravel.platform.common.api.ApiResponse;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
@RequestMapping("/api/v3/routes")
public class RouteController {
    private final RouteService service;

    public RouteController(RouteService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<RouteService.Result> recommend(
            @RequestParam(required = false) String userId,
            @RequestParam(required = false) Integer walkDurationMin,
            @RequestParam(required = false) Boolean avoidSteps) {
        return ApiResponse.ok(service.recommend(userId, walkDurationMin, avoidSteps));
    }
}
