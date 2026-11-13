CREATE TABLE scenic_dataset (
    scenic_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    source VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    dataset_json JSON NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    verified_by VARCHAR(100) NOT NULL,
    PRIMARY KEY (scenic_id, source),
    CONSTRAINT ck_scenic_source CHECK (source IN ('MOCK', 'OPEN_DATA', 'FIELD'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
