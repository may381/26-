package cn.silvertravel.platform.security;

import org.springframework.core.env.Environment;

public record MockIdentitySettings(boolean enabled) {
    public MockIdentitySettings(boolean enabled, Environment environment) {
        this(enabled);
        if (enabled
                && (!environment.matchesProfiles("local", "mock")
                        || environment.matchesProfiles("prod", "production"))) {
            throw new IllegalStateException(
                    "Mock identity requires local/mock and forbids production profiles");
        }
    }
}
