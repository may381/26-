CREATE TABLE trip_feedback (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    trip_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    effort VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    comfortable_walk_min INT NULL,
    note VARCHAR(500) NULL,
    created_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (trip_id),
    UNIQUE KEY uk_trip_feedback_id (id),
    CONSTRAINT fk_feedback_trip_owner FOREIGN KEY (trip_id,user_id) REFERENCES trip (id,user_id) ON DELETE CASCADE,
    CONSTRAINT ck_feedback_effort CHECK (effort IN ('EASY','COMFORTABLE','TIRED')),
    CONSTRAINT ck_feedback_duration CHECK (comfortable_walk_min IS NULL OR comfortable_walk_min BETWEEN 1 AND 1440)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE INDEX idx_trip_finished_page ON trip (user_id,status,finished_at,id);
