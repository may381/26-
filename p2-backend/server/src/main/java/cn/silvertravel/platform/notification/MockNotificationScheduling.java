package cn.silvertravel.platform.notification;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.*;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

@Configuration(proxyBeanMethods = false)
@Profile("!bootstrap & (local | mock)")
@ConditionalOnProperty(name = "app.notifications.mock-enabled", havingValue = "true")
@EnableScheduling
public class MockNotificationScheduling {
    private final MockNotificationService service;

    public MockNotificationScheduling(MockNotificationService service) {
        this.service = service;
    }

    @Scheduled(fixedDelayString = "${app.notifications.mock-delay-ms:2000}", initialDelay = 2000)
    public void tick() {
        service.advance();
    }
}
