ALTER TABLE trip ADD UNIQUE KEY uk_trip_id_user (id, user_id);

CREATE TABLE help_event (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    trip_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    type VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    location_json JSON NULL,
    location_note VARCHAR(500) NULL,
    business_status VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    handler_actor_id VARCHAR(128) COLLATE utf8mb4_0900_bin NULL,
    dispatch_recipient_type VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    dispatch_recipient_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_help_id_user (id, user_id),
    INDEX idx_help_user_created (user_id, created_at),
    INDEX idx_help_status_created (business_status, created_at),
    CONSTRAINT fk_help_trip_user FOREIGN KEY (trip_id, user_id) REFERENCES trip (id, user_id),
    CONSTRAINT ck_help_type CHECK (type IN ('SOS','LOST','UNWELL','GENERAL')),
    CONSTRAINT ck_help_status CHECK (business_status IN ('OPEN','ACKNOWLEDGED','RESOLVED')),
    CONSTRAINT ck_help_dispatch CHECK (dispatch_recipient_type IN ('scenic','official')),
    CONSTRAINT ck_help_location CHECK (location_json IS NOT NULL OR location_note IS NOT NULL),
    CONSTRAINT ck_help_handler CHECK (
        (business_status = 'OPEN' AND handler_actor_id IS NULL)
        OR (business_status IN ('ACKNOWLEDGED','RESOLVED') AND handler_actor_id IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE help_notification (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    help_event_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    phase VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    recipient_type VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    recipient_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    status VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    delivery_mode VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_notification_phase_recipient (help_event_id, phase, recipient_type, recipient_id),
    INDEX idx_notification_pending (status, created_at),
    CONSTRAINT fk_notification_help FOREIGN KEY (help_event_id, user_id) REFERENCES help_event (id, user_id),
    CONSTRAINT ck_notification_phase CHECK (phase IN ('OPEN','ACKNOWLEDGED','RESOLVED')),
    CONSTRAINT ck_notification_recipient CHECK (recipient_type IN ('family','scenic','official')),
    CONSTRAINT ck_notification_status CHECK (status IN ('PENDING','SENT','DELIVERED','FAILED')),
    CONSTRAINT ck_notification_mode CHECK (delivery_mode = 'MOCK')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE idempotency_request (
    actor_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    operation VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    request_key VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    request_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    resource_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    response_json JSON NULL,
    created_at TIMESTAMP(6) NOT NULL,
    expires_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (actor_id, operation, request_key),
    INDEX idx_idempotency_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
