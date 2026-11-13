package cn.silvertravel.platform.family;

import cn.silvertravel.platform.common.api.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
public class FamilyReadController {
    public record LinkRequest(@NotBlank @Size(max = 128) String familyActorId) {}

    private final FamilyReadService service;

    public FamilyReadController(FamilyReadService service) {
        this.service = service;
    }

    @PostMapping("/api/v3/family-relations/{id}/mock-account")
    @Operation(summary = "仅本地 mock：老人将本人 ACTIVE 关系关联到指定固定家属身份")
    public ApiResponse<FamilyReadService.LinkView> link(
            @PathVariable String id,
            @RequestParam String userId,
            @Valid @RequestBody LinkRequest request) {
        return ApiResponse.ok(service.link(userId, id, request.familyActorId()));
    }

    @GetMapping("/api/v3/family/elder")
    @Operation(summary = "FAMILY 授权内老人摘要；未采集的实时位置和进度不伪造")
    public ApiResponse<FamilyReadService.ElderView> elder(@RequestParam String userId) {
        return ApiResponse.ok(service.elder(userId));
    }

    @GetMapping("/api/v3/notifications")
    @Operation(summary = "FAMILY 当前关系的模拟求助收件列表；需 ACTIVE 和 shareAlert")
    public ApiResponse<List<FamilyReadService.InboxNotification>> notifications(
            @RequestParam String userId, @RequestParam(defaultValue = "20") int limit) {
        return new ApiResponse<>(
                "OK", "通知列表仅为站内模拟收件，不代表短信微信或官方真实触达", service.notifications(userId, limit));
    }
}
