package cn.silvertravel.platform.notification;

import cn.silvertravel.platform.help.HelpModels.NotificationStatus;

/** Real adapters must use notificationId for provider idempotency and verify delivery receipts. */
public interface NotificationDeliveryAdapter {
    record Attempt(
            String notificationId,
            String helpEventId,
            String phase,
            String recipientType,
            String recipientId,
            NotificationStatus currentStatus) {}

    String mode();

    NotificationStatus progress(Attempt attempt);
}
