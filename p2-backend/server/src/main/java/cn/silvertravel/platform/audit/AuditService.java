package cn.silvertravel.platform.audit;

import cn.silvertravel.platform.audit.persistence.*;
import cn.silvertravel.platform.security.CurrentActor;
import java.time.Instant;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class AuditService {
    private final AuditLogMapper mapper;

    public AuditService(AuditLogMapper mapper) {
        this.mapper = mapper;
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void record(
            CurrentActor actor, String userId, String action, String targetType, String targetId) {
        AuditLog entry = new AuditLog();
        entry.setId(UUID.randomUUID().toString());
        entry.setActorId(actor.id());
        entry.setTargetUserId(userId);
        entry.setAction(action);
        entry.setTargetType(targetType);
        entry.setTargetId(targetId);
        entry.setResult("SUCCESS");
        entry.setTraceId(MDC.get("traceId"));
        entry.setOccurredAt(Instant.now());
        mapper.insert(entry);
    }
}
