package cn.silvertravel.platform.trip;

import cn.silvertravel.platform.common.api.ApiResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
@RequestMapping("/api/v3/trips")
public class TripController {
    public record CreateRequest(@NotBlank @Size(max = 128) String routeId) {}

    private final TripService service;
    private final TripProgressService progress;
    private final TripJourneyService journey;

    public TripController(
            TripService service, TripProgressService progress, TripJourneyService journey) {
        this.service = service;
        this.progress = progress;
        this.journey = journey;
    }

    @PostMapping
    public ApiResponse<TripService.View> create(
            @RequestParam String userId, @RequestBody @Valid CreateRequest request) {
        return ApiResponse.ok(service.create(userId, request.routeId()));
    }

    @GetMapping("/active")
    public ApiResponse<TripService.View> active(@RequestParam String userId) {
        return ApiResponse.ok(service.active(userId));
    }

    @GetMapping("/{id}")
    public ApiResponse<TripService.View> get(@RequestParam String userId, @PathVariable String id) {
        return ApiResponse.ok(service.get(userId, id));
    }

    @PostMapping("/{id}/finish")
    public ApiResponse<TripService.View> finish(
            @RequestParam String userId, @PathVariable String id) {
        return ApiResponse.ok(service.finish(userId, id));
    }

    @PostMapping("/{id}/progress")
    @Transactional
    public ApiResponse<TripProgressService.ProgressView> reportProgress(
            @RequestParam String userId,
            @PathVariable String id,
            @RequestBody @Valid TripProgressService.ReportRequest request) {
        return ApiResponse.ok(withJourneyEta(userId, id, progress.report(userId, id, request)));
    }

    @GetMapping("/{id}/progress")
    @Transactional(readOnly = true)
    public ApiResponse<TripProgressService.ProgressView> getProgress(
            @RequestParam String userId, @PathVariable String id) {
        return ApiResponse.ok(withJourneyEta(userId, id, progress.getProgress(id, userId)));
    }

    private TripProgressService.ProgressView withJourneyEta(
            String userId, String id, TripProgressService.ProgressView value) {
        if (value == null) return null;
        return new TripProgressService.ProgressView(
                value.progressSeq(),
                value.location(),
                value.currentSpotId(),
                value.visitedSpotIds(),
                value.nextSpotId(),
                service.get(userId, id).estimatedFinishAt(),
                value.source(),
                value.updatedAt());
    }

    @PostMapping("/{id}/adjustments")
    public ApiResponse<TripProgressService.AdjustmentView> adjust(
            @RequestParam String userId,
            @PathVariable String id,
            @RequestBody @Valid TripProgressService.AdjustmentRequest request,
            @RequestHeader("Idempotency-Key") String key) {
        return ApiResponse.ok(progress.adjust(userId, id, request, key));
    }

    @GetMapping("/{id}/adjustments")
    public ApiResponse<List<TripProgressService.AdjustmentView>> adjustments(
            @RequestParam String userId, @PathVariable String id) {
        return ApiResponse.ok(progress.listAdjustments(userId, id));
    }

    @PostMapping("/{id}/stops/{spotId}/skip")
    public ApiResponse<TripService.View> skip(
            @RequestParam String userId,
            @PathVariable String id,
            @PathVariable String spotId,
            @Valid @RequestBody TripJourneyService.VersionRequest request,
            @RequestHeader("Idempotency-Key") String key) {
        return ApiResponse.ok(journey.skip(userId, id, spotId, request, key));
    }

    @PostMapping("/{id}/rests")
    public ApiResponse<TripService.View> startRest(
            @RequestParam String userId,
            @PathVariable String id,
            @Valid @RequestBody TripJourneyService.StartRest request,
            @RequestHeader("Idempotency-Key") String key) {
        return ApiResponse.ok(journey.startRest(userId, id, request, key));
    }

    @PatchMapping("/{id}/rests/{restId}")
    public ApiResponse<TripService.View> extendRest(
            @RequestParam String userId,
            @PathVariable String id,
            @PathVariable String restId,
            @Valid @RequestBody TripJourneyService.ExtendRest request,
            @RequestHeader("Idempotency-Key") String key) {
        return ApiResponse.ok(journey.extendRest(userId, id, restId, request, key));
    }

    @PostMapping("/{id}/rests/{restId}/finish")
    public ApiResponse<TripService.View> finishRest(
            @RequestParam String userId,
            @PathVariable String id,
            @PathVariable String restId,
            @Valid @RequestBody TripJourneyService.VersionRequest request,
            @RequestHeader("Idempotency-Key") String key) {
        return ApiResponse.ok(journey.finishRest(userId, id, restId, request, key));
    }

    @GetMapping("/{id}/rests")
    public ApiResponse<List<TripJourneyService.RestView>> rests(
            @RequestParam String userId, @PathVariable String id) {
        return ApiResponse.ok(journey.listRests(userId, id));
    }
}
