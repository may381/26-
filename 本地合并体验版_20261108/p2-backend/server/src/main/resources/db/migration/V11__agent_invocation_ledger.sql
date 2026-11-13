CREATE TABLE agent_invocation (
 id VARCHAR(36) PRIMARY KEY,
 task_id VARCHAR(36) NOT NULL,
 task_version BIGINT NOT NULL,
 agent_id VARCHAR(16) NOT NULL,
 state VARCHAR(32) NOT NULL,
 request_json JSON NOT NULL,
 response_json JSON NULL,
 deadline_at TIMESTAMP(6) NOT NULL,
 created_at TIMESTAMP(6) NOT NULL,
 updated_at TIMESTAMP(6) NOT NULL,
 UNIQUE KEY uk_invocation_task_version(task_id,task_version),
 INDEX idx_invocation_recovery(state,deadline_at),
 FOREIGN KEY(task_id) REFERENCES agent_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
