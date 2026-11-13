package cn.silvertravel.platform.maps;

import cn.silvertravel.platform.common.api.ApiResponse;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;

/**
 * Map integration supplement authorized by the user; not a silent edit to the frozen v1 contract.
 */
@RestController
@Profile("!bootstrap")
@RequestMapping("/api/v3/routes")
public class RouteMapController {
    private final RouteMapService service;

    public RouteMapController(RouteMapService service) {
        this.service = service;
    }

    @GetMapping("/{id}/map")
    public ApiResponse<RouteMapService.View> get(@PathVariable String id) {
        return ApiResponse.ok(service.get(id));
    }
}
