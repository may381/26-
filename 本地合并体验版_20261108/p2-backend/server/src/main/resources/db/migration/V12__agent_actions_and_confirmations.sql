CREATE TABLE agent_plan_step (
 id VARCHAR(36) PRIMARY KEY,
 task_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NOT NULL,
 request_key VARCHAR(128) NOT NULL,
 request_json JSON NOT NULL,
 prepare_key VARCHAR(36) NOT NULL,
 tool VARCHAR(64) NOT NULL,
 args JSON NOT NULL,
 UNIQUE KEY uk_step_request(task_id,request_key),
 FOREIGN KEY(task_id) REFERENCES agent_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
CREATE TABLE agent_action (
 id VARCHAR(36) PRIMARY KEY,
 task_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NOT NULL,
 step_id VARCHAR(36) NOT NULL UNIQUE,
 tool VARCHAR(64) NOT NULL,
 args JSON NOT NULL,
 execution_status VARCHAR(32) NOT NULL,
 result JSON NULL,
 created_at TIMESTAMP(6) NOT NULL,
 FOREIGN KEY(task_id) REFERENCES agent_task(id),
 FOREIGN KEY(step_id) REFERENCES agent_plan_step(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
CREATE TABLE agent_confirmation (
 id VARCHAR(36) PRIMARY KEY,
 action_id VARCHAR(36) NOT NULL UNIQUE,
 task_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NOT NULL,
 state VARCHAR(32) NOT NULL,
 version BIGINT NOT NULL,
 expires_at TIMESTAMP(6) NOT NULL,
 created_at TIMESTAMP(6) NOT NULL,
 decided_at TIMESTAMP(6) NULL,
 FOREIGN KEY(action_id) REFERENCES agent_action(id),
 FOREIGN KEY(task_id) REFERENCES agent_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
