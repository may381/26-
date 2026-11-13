package cn.silvertravel.platform.profile;

import cn.silvertravel.platform.profile.ProfileFields.*;
import java.util.List;

public record ProfileView(
        String id,
        String nickname,
        Integer age,
        String residence,
        String language,
        WalkSpeed walkSpeed,
        Integer walkDurationMin,
        Boolean avoidSteps,
        List<String> interests,
        InteractionPreference interactionPreference,
        List<EmergencyContact> emergencyContacts,
        Long version,
        java.time.Instant createdAt,
        java.time.Instant updatedAt) {
    public static ProfileView of(cn.silvertravel.platform.profile.persistence.ProfileEntity entity, ProfileFields fields) {
        ProfileView base = of(entity.getId(), fields);
        return new ProfileView(base.id(), base.nickname(), base.age(), base.residence(), base.language(),
                base.walkSpeed(), base.walkDurationMin(), base.avoidSteps(), base.interests(),
                base.interactionPreference(), base.emergencyContacts(), entity.getVersion(), entity.getCreatedAt(), entity.getUpdatedAt());
    }
    public static ProfileView of(String id, ProfileFields fields) {
        return new ProfileView(
                id,
                fields.nickname(),
                fields.age(),
                fields.residence(),
                fields.language(),
                fields.walkSpeed(),
                fields.walkDurationMin(),
                fields.avoidSteps(),
                fields.interests(),
                fields.interactionPreference(),
                fields.emergencyContacts(), null, null, null);
    }
}
