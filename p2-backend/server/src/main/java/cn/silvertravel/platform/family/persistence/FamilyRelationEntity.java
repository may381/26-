package cn.silvertravel.platform.family.persistence;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

@TableName("family_relation")
public class FamilyRelationEntity {
    @TableId private String id;
    private String userId;
    private String name;
    private String relation;
    private String phone;
    private Boolean shareLocation;
    private Boolean shareProgress;
    private Boolean shareAlert;
    private Boolean remotePlanning;
    private String status;

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

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getRelation() {
        return relation;
    }

    public void setRelation(String relation) {
        this.relation = relation;
    }

    public String getPhone() {
        return phone;
    }

    public void setPhone(String phone) {
        this.phone = phone;
    }

    public Boolean getShareLocation() {
        return shareLocation;
    }

    public void setShareLocation(Boolean shareLocation) {
        this.shareLocation = shareLocation;
    }

    public Boolean getShareProgress() {
        return shareProgress;
    }

    public void setShareProgress(Boolean shareProgress) {
        this.shareProgress = shareProgress;
    }

    public Boolean getShareAlert() {
        return shareAlert;
    }

    public void setShareAlert(Boolean shareAlert) {
        this.shareAlert = shareAlert;
    }

    public Boolean getRemotePlanning() {
        return remotePlanning;
    }

    public void setRemotePlanning(Boolean remotePlanning) {
        this.remotePlanning = remotePlanning;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}
