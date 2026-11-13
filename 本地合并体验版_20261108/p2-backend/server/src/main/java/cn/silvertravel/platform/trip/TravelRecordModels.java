package cn.silvertravel.platform.trip;

import cn.silvertravel.platform.scenic.ScenicData;
import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.List;

public final class TravelRecordModels {
    private TravelRecordModels() {}

    public enum Effort {
        EASY,
        COMFORTABLE,
        TIRED
    }

    public record FeedbackRequest(
            @NotNull Effort effort,
            @Min(1) @Max(1440) Integer comfortableWalkMin,
            @Size(max = 500) String note) {}

    public record FeedbackView(
            String id,
            String tripId,
            String userId,
            Effort effort,
            Integer comfortableWalkMin,
            String note,
            Instant createdAt,
            boolean profileUpdated,
            boolean memoryWritten,
            String preferenceUpdateId,
            String preferenceStatus) {}

    public record PreferenceDecisionRequest(@NotNull PreferenceDecision decision) {}

    public enum PreferenceDecision {
        APPROVE,
        REJECT
    }

    public record PreferenceUpdateView(
            String id, Integer proposedWalkDurationMin, String status, Instant createdAt) {}

    public record MediaSummary(
            String id,
            String mimeType,
            String fileName,
            long sizeBytes,
            Instant createdAt,
            String url,
            Instant expiresAt) {
        public MediaSummary(
                String id, String mimeType, String fileName, long sizeBytes, Instant createdAt) {
            this(id, mimeType, fileName, sizeBytes, createdAt, null, null);
        }

        public MediaSummary withLink(cn.silvertravel.platform.media.MediaSigner.Link link) {
            return new MediaSummary(
                    id, mimeType, fileName, sizeBytes, createdAt, link.url(), link.expiresAt());
        }
    }

    public record RecordSummary(
            String id,
            String tripId,
            String userId,
            String routeId,
            String routeName,
            ScenicData.Source source,
            Instant startedAt,
            Instant finishedAt,
            long durationSeconds,
            boolean feedbackSubmitted) {}

    public record RecordPage(List<RecordSummary> items, String nextCursor) {}

    public record RecordDetail(
            String id,
            String tripId,
            String userId,
            String scenicId,
            String status,
            String routeId,
            String routeName,
            ScenicData.Source source,
            Instant startedAt,
            Instant finishedAt,
            long durationSeconds,
            List<String> plannedSpotIds,
            List<String> visitedSpotIds,
            String visitedEvidence,
            boolean progressAvailable,
            ScenicData.Route routeSnapshot,
            List<TripProgressService.AdjustmentView> adjustments,
            List<MediaSummary> media,
            FeedbackView feedback,
            PreferenceUpdateView preferenceUpdate,
            String notice) {}

    public record ShareView(
            String id,
            String shareUrl,
            String summaryText,
            Instant expiresAt,
            List<MediaSummary> media) {}

    public record SharedRecord(
            String summaryText,
            String routeName,
            Instant startedAt,
            Instant finishedAt,
            long durationSeconds,
            List<String> visitedSpotIds,
            List<String> mediaUrls,
            Instant expiresAt) {}

    public record BinaryMedia(byte[] bytes, String mimeType, String fileName) {}
}
