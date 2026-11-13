package cn.silvertravel.platform.scenic;

import cn.silvertravel.platform.common.api.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
@RequestMapping("/api/v3/spots")
public class SpotQueryController {
    private final SpotQueryService service;

    public SpotQueryController(SpotQueryService service) {
        this.service = service;
    }

    @GetMapping
    @Operation(summary = "查询景点名称介绍和 WGS84 坐标；无介绍返回 null，不调用高德")
    public ApiResponse<List<SpotQueryService.SpotSummary>> list(
            @RequestParam(required = false) String scenicId) {
        return ApiResponse.ok(service.list(scenicId));
    }

    @GetMapping("/{id}")
    @Operation(summary = "景点详情和关联设施；设施列表不表示最近或步行可达")
    public ApiResponse<SpotQueryService.SpotDetail> get(
            @PathVariable String id, @RequestParam(required = false) String scenicId) {
        return ApiResponse.ok(service.get(id, scenicId));
    }
}
