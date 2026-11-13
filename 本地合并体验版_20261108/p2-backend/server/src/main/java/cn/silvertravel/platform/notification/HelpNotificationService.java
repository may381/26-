package cn.silvertravel.platform.notification;

import cn.silvertravel.platform.family.persistence.FamilyRelationMapper;
import cn.silvertravel.platform.help.HelpModels.*;
import cn.silvertravel.platform.help.persistence.HelpEventEntity;
import cn.silvertravel.platform.notification.persistence.*;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.UUID;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class HelpNotificationService {
    private final HelpNotificationMapper mapper;
    private final FamilyRelationMapper families;

    public HelpNotificationService(HelpNotificationMapper mapper, FamilyRelationMapper families) {
        this.mapper = mapper;
        this.families = families;
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void enqueue(HelpEventEntity event) {
        add(event, event.getDispatchRecipientType(), event.getDispatchRecipientId());
        for (var family : families.findByUserId(event.getUserId())) {
            if ("ACTIVE".equals(family.getStatus())
                    && Boolean.TRUE.equals(family.getShareAlert())) {
                add(event, "family", family.getId());
            }
        }
    }

    public List<Notification> latest(String helpId) {
        var recipients = new LinkedHashMap<String, Notification>();
        for (var row : mapper.findByHelpId(helpId)) {
            recipients.put(
                    row.getRecipientType() + ":" + row.getRecipientId(),
                    new Notification(
                            row.getRecipientType(),
                            row.getRecipientId(),
                            NotificationStatus.valueOf(row.getStatus())));
        }
        return List.copyOf(recipients.values());
    }

    private void add(HelpEventEntity event, String type, String recipientId) {
        Instant now = Instant.now().truncatedTo(ChronoUnit.MICROS);
        var notification = new HelpNotificationEntity();
        notification.setId(UUID.randomUUID().toString());
        notification.setHelpEventId(event.getId());
        notification.setUserId(event.getUserId());
        notification.setPhase(event.getBusinessStatus());
        notification.setRecipientType(type);
        notification.setRecipientId(recipientId);
        notification.setStatus(NotificationStatus.PENDING.name());
        notification.setDeliveryMode("MOCK");
        notification.setCreatedAt(now);
        notification.setUpdatedAt(now);
        mapper.insert(notification);
    }
}
