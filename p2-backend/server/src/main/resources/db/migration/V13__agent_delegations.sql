CREATE TABLE agent_delegation (
 child_task_id VARCHAR(36) PRIMARY KEY,
 parent_task_id VARCHAR(36) NOT NULL,
 action_id VARCHAR(36) COLLATE utf8mb4_0900_bin NOT NULL UNIQUE,
 target_agent VARCHAR(16) NOT NULL,
 domain VARCHAR(32) NOT NULL,
 required_child BOOLEAN NOT NULL,
 request_json JSON NOT NULL,
 created_at TIMESTAMP(6) NOT NULL,
 INDEX idx_delegation_parent(parent_task_id),
 FOREIGN KEY(child_task_id) REFERENCES agent_task(id),
 FOREIGN KEY(parent_task_id) REFERENCES agent_task(id),
 FOREIGN KEY(action_id) REFERENCES agent_action(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
