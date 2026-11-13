ALTER TABLE elder_profile
 ADD COLUMN version BIGINT NOT NULL DEFAULT 1,
 ADD COLUMN created_at TIMESTAMP(6) NULL,
 ADD COLUMN updated_at TIMESTAMP(6) NULL,
 ADD CONSTRAINT ck_profile_version CHECK (version >= 1);

-- Historical creation/update times are unknown; do not invent them during backfill.
