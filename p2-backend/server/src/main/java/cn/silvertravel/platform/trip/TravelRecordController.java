package cn.silvertravel.platform.trip;

import cn.silvertravel.platform.common.api.ApiResponse;
import cn.silvertravel.platform.media.BinaryMediaResponse;
import cn.silvertravel.platform.trip.TravelRecordModels.*;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.validation.Valid;
import org.springframework.context.annotation.Profile;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@Profile("!bootstrap")
public class TravelRecordController {
    private final TravelRecordService service;
    private final TravelRecordClosureService closure;

    public TravelRecordController(TravelRecordService service, TravelRecordClosureService closure) {
        this.service = service;
        this.closure = closure;
    }

    @GetMapping("/api/v3/travel-records")
    @Operation(summary = "本人已结束游览记录；游标分页，计划不能视为实际到访")
    public ApiResponse<RecordPage> list(
            @RequestParam String userId,
            @RequestParam(defaultValue = "20") int limit,
            @RequestParam(required = false) String cursor) {
        return ApiResponse.ok(service.list(userId, limit, cursor));
    }

    @GetMapping("/api/v3/travel-records/{id}")
    @Operation(summary = "本人游后详情与原路线快照；记录ID即Trip UUID")
    public ApiResponse<RecordDetail> get(@RequestParam String userId, @PathVariable String id) {
        return ApiResponse.ok(service.get(userId, id));
    }

    @PostMapping("/api/v3/trips/{id}/feedback")
    @Operation(summary = "本人已结束游览反馈；需要动作Key，不自动修改档案或记忆")
    public ApiResponse<FeedbackView> feedback(
            @RequestParam String userId,
            @PathVariable String id,
            @Valid @RequestBody FeedbackRequest request,
            @RequestHeader("Idempotency-Key") String key) {
        return new ApiResponse<>(
                "OK", "反馈已保存，未修改档案或长期记忆", service.submit(userId, id, request, key));
    }

    @PostMapping(
            value = "/api/v3/trips/{id}/attachments",
            consumes = org.springframework.http.MediaType.MULTIPART_FORM_DATA_VALUE)
    @Operation(summary = "上传游览照片或语音；JPG/PNG/WebP、WAV/MP3/WebM/OGG/MP4，最多10MiB")
    public ApiResponse<MediaSummary> upload(
            @RequestParam String userId,
            @PathVariable String id,
            @RequestPart("file") MultipartFile file) {
        return ApiResponse.ok(closure.upload(userId, id, file));
    }

    @GetMapping("/api/v3/trips/{id}/attachments/{mediaId}")
    public ResponseEntity<ByteArrayResource> media(
            @RequestParam String userId, @PathVariable String id, @PathVariable String mediaId) {
        return BinaryMediaResponse.of(closure.media(userId, id, mediaId));
    }

    @PostMapping("/api/v3/travel-records/{id}/preference-confirmation")
    public ApiResponse<PreferenceUpdateView> preferenceConfirmation(
            @RequestParam String userId,
            @PathVariable String id,
            @RequestBody @Valid TravelRecordClosureService.PreferenceDecisionRequest request) {
        return ApiResponse.ok(closure.decidePreference(userId, id, request));
    }

    @PostMapping("/api/v3/travel-records/{id}/share")
    public ApiResponse<ShareView> share(
            @RequestParam String userId,
            @PathVariable String id,
            @RequestBody @Valid TravelRecordClosureService.ShareRequest request) {
        return ApiResponse.ok(closure.createShare(userId, id, request));
    }

    @DeleteMapping("/api/v3/travel-records/{id}/share/{shareId}")
    public ApiResponse<Void> revokeShare(
            @RequestParam String userId, @PathVariable String id, @PathVariable String shareId) {
        closure.revokeShare(userId, id, shareId);
        return ApiResponse.ok(null);
    }

    @GetMapping("/api/v3/travel-record-shares/{shareId}")
    @Operation(summary = "匿名分享页；分享ID是7天有效的随机凭证，不返回老人身份资料")
    public ApiResponse<SharedRecord> sharedRecord(@PathVariable String shareId) {
        return ApiResponse.ok(closure.sharedRecord(shareId));
    }

    @GetMapping("/api/v3/travel-record-shares/{shareId}/media/{mediaId}")
    public ResponseEntity<ByteArrayResource> sharedMedia(
            @PathVariable String shareId, @PathVariable String mediaId) {
        return BinaryMediaResponse.of(closure.sharedMedia(shareId, mediaId));
    }
}
