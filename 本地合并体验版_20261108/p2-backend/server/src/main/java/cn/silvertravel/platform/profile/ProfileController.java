package cn.silvertravel.platform.profile;

import cn.silvertravel.platform.common.api.ApiResponse;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
@RequestMapping("/api/v3/profile")
public class ProfileController {
    private final ProfileService service;

    public ProfileController(ProfileService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<ProfileView> get(@RequestParam String userId) {
        return ApiResponse.ok(service.get(userId));
    }

    @PatchMapping
    public ApiResponse<ProfileView> patch(
            @RequestParam String userId, @RequestBody JsonNode patch,
            @RequestHeader(value = "X-Expected-Profile-Version", required = false) Long expectedVersion) {
        return ApiResponse.ok(service.patch(userId, patch, expectedVersion));
    }
}
