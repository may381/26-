CREATE TABLE speech_audio (
    id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    content MEDIUMBLOB NOT NULL,
    expires_at TIMESTAMP(6) NOT NULL,
    KEY idx_speech_audio_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
