package cn.silvertravel.platform.security;

import java.security.Principal;

/** The caller identity, distinct from the elder selected by a request userId. */
public record CurrentActor(String id, ActorRole role, String elderUserId) implements Principal {
    @Override
    public String getName() {
        return id;
    }
}
