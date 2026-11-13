CREATE TABLE elder_memory_revision (
 user_id VARCHAR(128) COLLATE utf8mb4_0900_bin PRIMARY KEY,
 revision BIGINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE memory_candidate (
 id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
 root_task_id VARCHAR(36) NOT NULL,
 version INT NOT NULL DEFAULT 1,
 state VARCHAR(16) NOT NULL,
 payload JSON NOT NULL,
 created_at TIMESTAMP(6) NOT NULL,
 FOREIGN KEY(root_task_id) REFERENCES agent_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE memory_review (
 id VARCHAR(36) PRIMARY KEY,
 candidate_id VARCHAR(36) NOT NULL UNIQUE,
 candidate_version INT NOT NULL,
 version INT NOT NULL DEFAULT 1,
 payload JSON NOT NULL,
 created_at TIMESTAMP(6) NOT NULL,
 FOREIGN KEY(candidate_id) REFERENCES memory_candidate(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE elder_memory (
 id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
 candidate_id VARCHAR(36) NOT NULL UNIQUE,
 version INT NOT NULL DEFAULT 1,
 state VARCHAR(16) NOT NULL,
 payload JSON NULL,
 confirmed_at TIMESTAMP(6) NOT NULL,
 updated_at TIMESTAMP(6) NOT NULL,
 INDEX idx_memory_owner(user_id,state),
 FOREIGN KEY(candidate_id) REFERENCES memory_candidate(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE agent_memory_read (
 invocation_id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
 revision BIGINT NOT NULL,
 memory_refs JSON NOT NULL,
 FOREIGN KEY(invocation_id) REFERENCES agent_invocation(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
ALTER TABLE agent_confirmation ADD COLUMN summary TEXT NULL;
