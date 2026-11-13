package cn.silvertravel.platform.help;

import cn.silvertravel.platform.common.api.ApiResponse;
import cn.silvertravel.platform.help.HelpModels.*;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
@RequestMapping("/api/v3/help-events")
public class HelpEventController {
    private final HelpEventService service;

    public HelpEventController(HelpEventService service) {
        this.service = service;
    }

    @PostMapping
    public ApiResponse<View> create(
            @RequestBody @Valid CreateRequest request,
            @RequestParam(required = false) String userId,
            @RequestHeader(name = "Idempotency-Key", required = false) String key) {
        return response(service.create(request, userId, key));
    }

    @GetMapping
    public ApiResponse<List<View>> list(@RequestParam(required = false) String userId) {
        return response(service.list(userId));
    }

    @GetMapping("/{id}")
    public ApiResponse<View> get(
            @PathVariable String id, @RequestParam(required = false) String userId) {
        return response(service.get(id, userId));
    }

    @PostMapping("/{id}/acknowledge")
    public ApiResponse<View> acknowledge(
            @PathVariable String id, @RequestParam(required = false) String userId) {
        return response(service.acknowledge(id, userId));
    }

    @PostMapping("/{id}/resolve")
    public ApiResponse<View> resolve(
            @PathVariable String id, @RequestParam(required = false) String userId) {
        return response(service.resolve(id, userId));
    }

    private <T> ApiResponse<T> response(T data) {
        return new ApiResponse<>("OK", "成功（通知仅为站内模拟演示，未实际触达家属、景区或官方）", data);
    }
}
