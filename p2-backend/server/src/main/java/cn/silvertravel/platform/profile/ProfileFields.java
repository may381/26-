package cn.silvertravel.platform.profile;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.List;

public record ProfileFields(
        @NotBlank @Size(max = 100) String nickname,
        @NotNull @Min(1) @Max(150) Integer age,
        @NotBlank @Size(max = 200) String residence,
        @NotBlank @Size(max = 50) String language,
        @NotNull WalkSpeed walkSpeed,
        @NotNull @Min(1) @Max(1440) Integer walkDurationMin,
        @NotNull Boolean avoidSteps,
        @NotNull @Size(max = 30) List<@NotBlank @Size(max = 100) String> interests,
        @NotNull InteractionPreference interactionPreference,
        @NotNull @Size(max = 10) List<@NotNull @Valid EmergencyContact> emergencyContacts) {

    public enum WalkSpeed {
        SLOW,
        MEDIUM,
        FAST
    }

    public enum InteractionPreference {
        VOICE,
        TEXT
    }

    public record EmergencyContact(
            @NotBlank @Size(max = 100) String name,
            @NotBlank @Size(max = 40) String phone,
            @NotBlank @Size(max = 100) String relation) {}
}
