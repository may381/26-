package cn.silvertravel.platform.security;

import static org.assertj.core.api.Assertions.*;

import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;

class MockIdentitySettingsTest {
    @Test
    void mockCannotBeEnabledOutsideDevelopmentOrAlongsideProduction() {
        assertThatThrownBy(
                        () ->
                                new MockIdentitySettings(
                                        true,
                                        new MockEnvironment()
                                                .withProperty(
                                                        "spring.profiles.active", "production")))
                .isInstanceOf(IllegalStateException.class);
        MockEnvironment mixed = new MockEnvironment();
        mixed.setActiveProfiles("local", "production");
        assertThatThrownBy(() -> new MockIdentitySettings(true, mixed))
                .isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> new MockIdentitySettings(true, new MockEnvironment()))
                .isInstanceOf(IllegalStateException.class);
        MockEnvironment local = new MockEnvironment();
        local.setActiveProfiles("local");
        assertThat(new MockIdentitySettings(true, local).enabled()).isTrue();
        assertThat(new MockIdentitySettings(false, mixed).enabled()).isFalse();
    }
}
