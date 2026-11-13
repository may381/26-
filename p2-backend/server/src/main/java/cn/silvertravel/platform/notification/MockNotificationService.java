package cn.silvertravel.platform.notification;

import cn.silvertravel.platform.family.persistence.FamilyRelationMapper;
import cn.silvertravel.platform.help.HelpModels.NotificationStatus;
import cn.silvertravel.platform.notification.persistence.HelpNotificationMapper;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import org.springframework.context.annotation.Profile;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class MockNotificationService {
    private final HelpNotificationMapper notifications;
    private final FamilyRelationMapper families;
    private final Environment environment;
    private final NotificationDeliveryAdapter adapter;

    public MockNotificationService(
            HelpNotificationMapper notifications,
            FamilyRelationMapper families,
            Environment environment,
            NotificationDeliveryAdapter adapter) {
        this.notifications = notifications;
        this.families = families;
        this.environment = environment;
        this.adapter = adapter;
    }

    @Transactional
    public int advance() {
        if (!environment.matchesProfiles("local", "mock")
                || environment.matchesProfiles("prod", "production")) {
            throw new IllegalStateException("模拟通知仅允许开发环境执行");
        }
        var batch = notifications.lockPendingBatch();
        for (var notification : batch) {
            if (!"MOCK".equals(adapter.mode())
                    || !adapter.mode().equals(notification.getDeliveryMode())) {
                throw new IllegalStateException("模拟任务仅能调用 MOCK 渠道适配器");
            }
            boolean permitted = true;
            if ("family".equals(notification.getRecipientType())) {
                var relation =
                        families.lockOwned(notification.getRecipientId(), notification.getUserId());
                permitted =
                        relation != null
                                && "ACTIVE".equals(relation.getStatus())
                                && Boolean.TRUE.equals(relation.getShareAlert());
            }
            NotificationStatus result =
                    !permitted
                            ? NotificationStatus.FAILED
                            : adapter.progress(
                                    new NotificationDeliveryAdapter.Attempt(
                                            notification.getId(),
                                            notification.getHelpEventId(),
                                            notification.getPhase(),
                                            notification.getRecipientType(),
                                            notification.getRecipientId(),
                                            NotificationStatus.valueOf(notification.getStatus())));
            notification.setStatus(result.name());
            notification.setUpdatedAt(Instant.now().truncatedTo(ChronoUnit.MICROS));
            notifications.updateById(notification);
        }
        return batch.size();
    }
}
