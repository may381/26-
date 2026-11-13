package cn.silvertravel.platform.security;

import java.util.Map;
import java.util.Optional;

/** Fixed local fixtures, not accounts or real authentication credentials. */
public final class MockIdentityDirectory {
    private static final Map<String, CurrentActor> ACTORS =
            Map.of(
                    "u100", new CurrentActor("u100", ActorRole.ELDER, "u100"),
                    "u101", new CurrentActor("u101", ActorRole.ELDER, "u101"),
                    "family-operator-001",
                            new CurrentActor("family-operator-001", ActorRole.FAMILY, null),
                    "family-operator-002",
                            new CurrentActor("family-operator-002", ActorRole.FAMILY, null),
                    "scenic-operator-001",
                            new CurrentActor("scenic-operator-001", ActorRole.SCENIC, null),
                    "scenic-operator-002",
                            new CurrentActor("scenic-operator-002", ActorRole.SCENIC, null),
                    "official-operator-001",
                            new CurrentActor("official-operator-001", ActorRole.OFFICIAL, null),
                    "admin-operator-001",
                            new CurrentActor("admin-operator-001", ActorRole.ADMIN, null));

    private MockIdentityDirectory() {}

    public static Optional<CurrentActor> find(String id) {
        return Optional.ofNullable(ACTORS.get(id));
    }
}
