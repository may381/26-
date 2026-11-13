package cn.silvertravel.platform.family;

import cn.silvertravel.platform.common.api.ApiResponse;
import cn.silvertravel.platform.family.FamilyModels.*;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
@RequestMapping("/api/v3/family-relations")
public class FamilyRelationController {
    private final FamilyRelationService service;

    public FamilyRelationController(FamilyRelationService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<List<View>> list(@RequestParam String userId) {
        return ApiResponse.ok(service.list(userId));
    }

    @PostMapping
    public ApiResponse<View> create(
            @RequestParam String userId, @RequestBody @Valid CreateRequest request) {
        return ApiResponse.ok(service.create(userId, request));
    }

    @PostMapping("/{id}/approve")
    public ApiResponse<View> approve(@RequestParam String userId, @PathVariable String id) {
        return ApiResponse.ok(service.approve(userId, id));
    }

    @PostMapping("/{id}/revoke")
    public ApiResponse<View> revoke(@RequestParam String userId, @PathVariable String id) {
        return ApiResponse.ok(service.revoke(userId, id));
    }

    @PatchMapping("/{id}/permissions")
    public ApiResponse<View> permissions(
            @RequestParam String userId, @PathVariable String id, @RequestBody JsonNode patch) {
        return ApiResponse.ok(service.permissions(userId, id, patch));
    }
}
