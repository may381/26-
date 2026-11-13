ALTER TABLE agent_invocation
 ADD COLUMN cancel_request_id VARCHAR(36) NULL,
 ADD COLUMN cancel_attempts INT NOT NULL DEFAULT 0,
 ADD COLUMN receipt_attempts INT NOT NULL DEFAULT 0,
 ADD COLUMN receipt_json JSON NULL;
