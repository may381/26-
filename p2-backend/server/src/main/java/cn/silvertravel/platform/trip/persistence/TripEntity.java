package cn.silvertravel.platform.trip.persistence;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;

@TableName("trip")
public class TripEntity {
    @TableId private String id;
    private String userId;
    private String routeId;
    private String scenicId;
    private String routeSource;
    private String routeSnapshot;
    private String status;
    private Instant createdAt;
    private Instant finishedAt;
    private Long tripVersion;
    private Instant journeyAnchorAt;

    public Long getTripVersion() {
        return tripVersion;
    }

    public void setTripVersion(Long tripVersion) {
        this.tripVersion = tripVersion;
    }

    public Instant getJourneyAnchorAt() {
        return journeyAnchorAt;
    }

    public void setJourneyAnchorAt(Instant journeyAnchorAt) {
        this.journeyAnchorAt = journeyAnchorAt;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getRouteId() {
        return routeId;
    }

    public void setRouteId(String routeId) {
        this.routeId = routeId;
    }

    public String getScenicId() {
        return scenicId;
    }

    public void setScenicId(String scenicId) {
        this.scenicId = scenicId;
    }

    public String getRouteSource() {
        return routeSource;
    }

    public void setRouteSource(String routeSource) {
        this.routeSource = routeSource;
    }

    public String getRouteSnapshot() {
        return routeSnapshot;
    }

    public void setRouteSnapshot(String routeSnapshot) {
        this.routeSnapshot = routeSnapshot;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getFinishedAt() {
        return finishedAt;
    }

    public void setFinishedAt(Instant finishedAt) {
        this.finishedAt = finishedAt;
    }
}
