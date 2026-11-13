package cn.silvertravel.platform.family;

import cn.silvertravel.platform.family.persistence.FamilyRelationEntity;
import jakarta.validation.constraints.*;

public final class FamilyModels {
    private FamilyModels() {}

    public enum Status {
        PENDING,
        ACTIVE,
        REVOKED
    }

    public record CreateRequest(
            @NotBlank @Size(max = 100) String name,
            @NotBlank @Size(max = 100) String relation,
            @NotBlank @Size(max = 40) String phone) {}

    public record Permissions(
            @NotNull Boolean shareLocation,
            @NotNull Boolean shareProgress,
            @NotNull Boolean shareAlert,
            @NotNull Boolean remotePlanning) {
        public static Permissions none() {
            return new Permissions(false, false, false, false);
        }
    }

    public record View(
            String id,
            String name,
            String relation,
            String phone,
            Permissions permissions,
            Status status) {
        public static View of(FamilyRelationEntity entity) {
            return new View(
                    entity.getId(),
                    entity.getName(),
                    entity.getRelation(),
                    entity.getPhone(),
                    new Permissions(
                            entity.getShareLocation(),
                            entity.getShareProgress(),
                            entity.getShareAlert(),
                            entity.getRemotePlanning()),
                    Status.valueOf(entity.getStatus()));
        }
    }
}
