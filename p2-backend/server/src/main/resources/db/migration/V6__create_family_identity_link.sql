ALTER TABLE family_relation ADD UNIQUE KEY uk_family_id_user (id,user_id);

CREATE TABLE family_identity_link (
    family_relation_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    family_actor_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    linked_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (family_relation_id),
    UNIQUE KEY uk_family_actor_elder (family_actor_id,user_id),
    CONSTRAINT fk_family_identity_relation FOREIGN KEY (family_relation_id,user_id)
        REFERENCES family_relation (id,user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
