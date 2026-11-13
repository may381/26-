package cn.silvertravel.platform.security;

import java.util.Objects;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.AuthenticationCredentialsNotFoundException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

@Component
public class BusinessAccessPolicy {
    public CurrentActor currentActor() {
        var authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null
                || !authentication.isAuthenticated()
                || !(authentication.getPrincipal() instanceof CurrentActor actor)) {
            throw new AuthenticationCredentialsNotFoundException(
                    "Missing platform caller identity");
        }
        return actor;
    }

    public CurrentActor requireElderOwner(String targetUserId) {
        CurrentActor actor = currentActor();
        if (targetUserId == null
                || targetUserId.isBlank()
                || actor.role() != ActorRole.ELDER
                || !Objects.equals(actor.elderUserId(), targetUserId)) {
            throw new AccessDeniedException("Elder ownership required");
        }
        return actor;
    }

    public CurrentActor requireHelpAcknowledge() {
        CurrentActor actor = currentActor();
        if (actor.role() != ActorRole.SCENIC
                && actor.role() != ActorRole.OFFICIAL
                && actor.role() != ActorRole.ADMIN) {
            throw new AccessDeniedException("Help handler role required");
        }
        return actor;
    }

    /** actualHandlerId must come from the persisted help event, never a request field. */
    public CurrentActor requireHelpResolve(String actualHandlerId) {
        CurrentActor actor = requireHelpAcknowledge();
        if (actor.role() != ActorRole.ADMIN && !Objects.equals(actor.id(), actualHandlerId)) {
            throw new AccessDeniedException("Actual handler required");
        }
        return actor;
    }
}
