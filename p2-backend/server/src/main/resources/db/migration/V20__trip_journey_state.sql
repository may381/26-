ALTER TABLE trip
    ADD COLUMN trip_version BIGINT NOT NULL DEFAULT 1,
    ADD COLUMN journey_anchor_at TIMESTAMP(6) NULL;

CREATE TABLE trip_skipped_stop (
    trip_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    spot_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    skipped_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (trip_id, spot_id),
    FOREIGN KEY (trip_id) REFERENCES trip(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE trip_rest (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    trip_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    started_at TIMESTAMP(6) NOT NULL,
    ended_at TIMESTAMP(6) NULL,
    planned_minutes INT NOT NULL,
    facility_id VARCHAR(128) COLLATE utf8mb4_0900_bin NULL,
    latitude DECIMAL(10,7) NOT NULL,
    longitude DECIMAL(10,7) NOT NULL,
    coordinate_system VARCHAR(8) NOT NULL,
    active_slot TINYINT
        GENERATED ALWAYS AS (CASE WHEN ended_at IS NULL THEN 1 ELSE NULL END) STORED,
    UNIQUE KEY uk_trip_rest_active (trip_id, active_slot),
    KEY idx_trip_rest_history (trip_id, started_at, id),
    FOREIGN KEY (trip_id) REFERENCES trip(id) ON DELETE CASCADE,
    CHECK (planned_minutes BETWEEN 1 AND 1440)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
