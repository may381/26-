package cn.silvertravel.platform.family;

import cn.silvertravel.platform.common.api.ApiResponse;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
public class FamilyCollaborationController {
    private final FamilyCollaborationService service;

    public FamilyCollaborationController(FamilyCollaborationService service) {
        this.service = service;
    }

    @PostMapping("/api/v3/family/route-suggestions")
    public ApiResponse<FamilyCollaborationService.SuggestionView> suggestRoute(
            @RequestParam String userId,
            @Valid @RequestBody FamilyCollaborationService.SuggestionRequest request) {
        return ApiResponse.ok(service.suggest(userId, request));
    }

    @GetMapping("/api/v3/family/route-suggestions")
    public ApiResponse<List<FamilyCollaborationService.SuggestionView>> routeSuggestions(
            @RequestParam String userId) {
        return ApiResponse.ok(service.suggestions(userId));
    }

    @PostMapping("/api/v3/family/route-suggestions/{id}/decision")
    public ApiResponse<FamilyCollaborationService.SuggestionView> decideRouteSuggestion(
            @RequestParam String userId,
            @PathVariable String id,
            @Valid @RequestBody FamilyCollaborationService.DecisionRequest request) {
        return ApiResponse.ok(service.decide(userId, id, request));
    }

    @PostMapping("/api/v3/family/messages")
    public ApiResponse<FamilyCollaborationService.MessageView> sendMessage(
            @RequestParam String userId,
            @Valid @RequestBody FamilyCollaborationService.MessageRequest request) {
        return ApiResponse.ok(service.sendMessage(userId, request));
    }

    @GetMapping("/api/v3/family/messages")
    public ApiResponse<List<FamilyCollaborationService.MessageView>> inbox(
            @RequestParam String userId, @RequestParam(defaultValue = "20") int limit) {
        return ApiResponse.ok(service.inbox(userId, limit));
    }
}
