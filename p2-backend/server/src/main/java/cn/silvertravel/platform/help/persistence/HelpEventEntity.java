package cn.silvertravel.platform.help.persistence;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;

@TableName("help_event")
public class HelpEventEntity {
    @TableId private String id;
    private String userId;
    private String tripId;
    private String type;
    private String locationJson;
    private String locationNote;
    private String businessStatus;
    private String handlerActorId;
    private String dispatchRecipientType;
    private String dispatchRecipientId;
    private Instant createdAt;
    private Instant updatedAt;

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

    public String getTripId() {
        return tripId;
    }

    public void setTripId(String tripId) {
        this.tripId = tripId;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getLocationJson() {
        return locationJson;
    }

    public void setLocationJson(String locationJson) {
        this.locationJson = locationJson;
    }

    public String getLocationNote() {
        return locationNote;
    }

    public void setLocationNote(String locationNote) {
        this.locationNote = locationNote;
    }

    public String getBusinessStatus() {
        return businessStatus;
    }

    public void setBusinessStatus(String businessStatus) {
        this.businessStatus = businessStatus;
    }

    public String getHandlerActorId() {
        return handlerActorId;
    }

    public void setHandlerActorId(String handlerActorId) {
        this.handlerActorId = handlerActorId;
    }

    public String getDispatchRecipientType() {
        return dispatchRecipientType;
    }

    public void setDispatchRecipientType(String value) {
        this.dispatchRecipientType = value;
    }

    public String getDispatchRecipientId() {
        return dispatchRecipientId;
    }

    public void setDispatchRecipientId(String value) {
        this.dispatchRecipientId = value;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }
}
