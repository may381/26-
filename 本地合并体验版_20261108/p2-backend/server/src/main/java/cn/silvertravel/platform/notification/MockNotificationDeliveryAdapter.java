package cn.silvertravel.platform.notification;

import cn.silvertravel.platform.help.HelpModels.NotificationStatus;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

@Component
@Profile("!bootstrap")
public class MockNotificationDeliveryAdapter implements NotificationDeliveryAdapter {
    @Override
    public String mode() {
        return "MOCK";
    }

    @Override
    public NotificationStatus progress(Attempt attempt) {
        return switch (attempt.currentStatus()) {
            case PENDING -> NotificationStatus.SENT;
            case SENT -> NotificationStatus.DELIVERED;
            default -> throw new IllegalArgumentException("终态模拟通知不能继续推进");
        };
    }
}
