ALTER TABLE trip ADD UNIQUE KEY uk_trip_id_owner (id,user_id);
ALTER TABLE family_relation ADD UNIQUE KEY uk_family_relation_owner (id,user_id);

CREATE TABLE trip_progress (
    trip_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    progress_seq BIGINT NOT NULL,
    request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    latitude DECIMAL(10,7) NULL,
    longitude DECIMAL(10,7) NULL,
    current_spot_id VARCHAR(128) COLLATE utf8mb4_0900_bin NULL,
    visited_spot_ids JSON NOT NULL,
    next_spot_id VARCHAR(128) COLLATE utf8mb4_0900_bin NULL,
    estimated_finish_at TIMESTAMP(6) NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (trip_id),
    CONSTRAINT fk_trip_progress_owner FOREIGN KEY (trip_id,user_id) REFERENCES trip (id,user_id) ON DELETE CASCADE,
    CONSTRAINT ck_trip_progress_seq CHECK (progress_seq >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE trip_route_adjustment (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    trip_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    revision INT NOT NULL,
    route_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    route_snapshot JSON NOT NULL,
    visited_spot_ids JSON NOT NULL,
    remaining_spot_ids JSON NOT NULL,
    reason VARCHAR(500) NULL,
    created_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_trip_adjustment_revision (trip_id,revision),
    CONSTRAINT fk_trip_adjustment_owner FOREIGN KEY (trip_id,user_id) REFERENCES trip (id,user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE family_route_suggestion (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    family_relation_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    family_actor_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    route_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    route_snapshot JSON NOT NULL,
    note VARCHAR(500) NULL,
    status VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    decision_note VARCHAR(500) NULL,
    created_at TIMESTAMP(6) NOT NULL,
    decided_at TIMESTAMP(6) NULL,
    PRIMARY KEY (id),
    INDEX idx_route_suggestion_owner (user_id,status,created_at),
    CONSTRAINT fk_route_suggestion_relation FOREIGN KEY (family_relation_id,user_id) REFERENCES family_relation (id,user_id) ON DELETE CASCADE,
    CONSTRAINT ck_route_suggestion_status CHECK (status IN ('PENDING','ACCEPTED','REJECTED','EXPIRED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE family_message (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    family_relation_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    sender_actor_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    sender_role VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    body VARCHAR(2000) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    read_at TIMESTAMP(6) NULL,
    PRIMARY KEY (id),
    INDEX idx_family_message_inbox (user_id,created_at,id),
    CONSTRAINT fk_family_message_relation FOREIGN KEY (family_relation_id,user_id) REFERENCES family_relation (id,user_id) ON DELETE CASCADE,
    CONSTRAINT ck_family_message_sender CHECK (sender_role IN ('ELDER','FAMILY'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE trip_media (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    trip_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    mime_type VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    content LONGBLOB NOT NULL,
    size_bytes INT NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_trip_media_owner (trip_id,user_id,created_at),
    CONSTRAINT fk_trip_media_owner FOREIGN KEY (trip_id,user_id) REFERENCES trip (id,user_id) ON DELETE CASCADE,
    CONSTRAINT ck_trip_media_size CHECK (size_bytes BETWEEN 1 AND 10485760),
    CONSTRAINT ck_trip_media_type CHECK (mime_type IN ('image/jpeg','image/png','image/webp','audio/wav','audio/mpeg','audio/webm','audio/ogg','audio/mp4'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE travel_record_share (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    trip_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    expires_at TIMESTAMP(6) NOT NULL,
    revoked_at TIMESTAMP(6) NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_travel_share_owner FOREIGN KEY (trip_id,user_id) REFERENCES trip (id,user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE travel_record_share_media (
    share_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    media_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    PRIMARY KEY (share_id,media_id),
    CONSTRAINT fk_share_media_share FOREIGN KEY (share_id) REFERENCES travel_record_share(id) ON DELETE CASCADE,
    CONSTRAINT fk_share_media_media FOREIGN KEY (media_id) REFERENCES trip_media(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE trip_preference_update (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    trip_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    walk_duration_min INT NOT NULL,
    status VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    decided_at TIMESTAMP(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_trip_preference_trip (trip_id),
    CONSTRAINT fk_trip_preference_owner FOREIGN KEY (trip_id,user_id) REFERENCES trip (id,user_id) ON DELETE CASCADE,
    CONSTRAINT ck_trip_preference_duration CHECK (walk_duration_min BETWEEN 1 AND 1440),
    CONSTRAINT ck_trip_preference_status CHECK (status IN ('PENDING','APPROVED','REJECTED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
