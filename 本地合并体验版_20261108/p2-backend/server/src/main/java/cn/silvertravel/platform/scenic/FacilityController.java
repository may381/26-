package cn.silvertravel.platform.scenic;

import cn.silvertravel.platform.common.api.ApiResponse;
import cn.silvertravel.platform.scenic.ScenicData.FacilityType;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Profile("!bootstrap")
public class FacilityController {
    private final SpotQueryService spots;

    public FacilityController(SpotQueryService spots) {
        this.spots = spots;
    }

    @GetMapping("/api/v3/facilities")
    public ApiResponse<List<SpotQueryService.FacilitySearchResult>> search(
            @RequestParam(required = false) String scenicId,
            @RequestParam(required = false) FacilityType type,
            @RequestParam(required = false) Double lat,
            @RequestParam(required = false) Double lng,
            @RequestParam(defaultValue = "20") int limit) {
        return ApiResponse.ok(spots.facilities(scenicId, type, lat, lng, limit));
    }
}
