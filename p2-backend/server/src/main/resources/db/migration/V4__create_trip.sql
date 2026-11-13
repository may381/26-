CREATE TABLE trip (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    route_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    scenic_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    route_source VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    route_snapshot JSON NOT NULL,
    status VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    finished_at TIMESTAMP(6) NULL,
    active_user_id VARCHAR(128) COLLATE utf8mb4_0900_bin
        GENERATED ALWAYS AS (CASE WHEN status = 'ACTIVE' THEN user_id ELSE NULL END) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY uk_trip_active_user (active_user_id),
    INDEX idx_trip_user_status (user_id, status),
    CONSTRAINT fk_trip_profile FOREIGN KEY (user_id) REFERENCES elder_profile(user_id),
    CONSTRAINT ck_trip_status CHECK (status IN ('ACTIVE', 'FINISHED', 'CANCELLED')),
    CONSTRAINT ck_trip_source CHECK (route_source IN ('MOCK', 'OPEN_DATA', 'FIELD'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
