package cn.silvertravel.platform.help;

import com.fasterxml.jackson.annotation.JsonInclude;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public final class HelpModels {
    private HelpModels() {}

    public enum Type {
        SOS,
        LOST,
        UNWELL,
        GENERAL
    }

    public enum Status {
        OPEN,
        ACKNOWLEDGED,
        RESOLVED
    }

    public enum NotificationStatus {
        PENDING,
        SENT,
        DELIVERED,
        FAILED
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Location(
            @DecimalMin("-90") @DecimalMax("90") BigDecimal lat,
            @DecimalMin("-180") @DecimalMax("180") BigDecimal lng,
            @Size(min = 1, max = 128) String spotId) {
        @AssertTrue(message = "定位必须是经纬度或景点 ID 二选一")
        @com.fasterxml.jackson.annotation.JsonIgnore
        public boolean isValidShape() {
            boolean coordinates = lat != null && lng != null && spotId == null;
            boolean spot = lat == null && lng == null && spotId != null && !spotId.isBlank();
            return coordinates || spot;
        }
    }

    public record CreateRequest(
            @NotBlank @Size(max = 128) String userId,
            @Size(min = 1, max = 36) @Pattern(regexp = ".*\\S.*") String tripId,
            @NotNull Type type,
            @Valid Location location,
            @Size(max = 500) String locationNote) {
        @AssertTrue(message = "至少提供定位或位置描述")
        @com.fasterxml.jackson.annotation.JsonIgnore
        public boolean isLocated() {
            return location != null || (locationNote != null && !locationNote.isBlank());
        }
    }

    public record Notification(
            String recipientType, String recipientId, NotificationStatus status) {}

    public record View(
            String id,
            String userId,
            String tripId,
            Type type,
            Location location,
            String locationNote,
            Status businessStatus,
            List<Notification> notifications,
            Instant createdAt,
            Instant updatedAt) {}
}
