CREATE TABLE elder_profile (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    profile_json JSON NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_profile_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE family_relation (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    name VARCHAR(100) NOT NULL,
    relation VARCHAR(100) NOT NULL,
    phone VARCHAR(40) NOT NULL,
    share_location BOOLEAN NOT NULL DEFAULT FALSE,
    share_progress BOOLEAN NOT NULL DEFAULT FALSE,
    share_alert BOOLEAN NOT NULL DEFAULT FALSE,
    remote_planning BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_family_user_status (user_id, status),
    CONSTRAINT fk_family_profile FOREIGN KEY (user_id) REFERENCES elder_profile (user_id),
    CONSTRAINT ck_family_status CHECK (status IN ('PENDING', 'ACTIVE', 'REVOKED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
