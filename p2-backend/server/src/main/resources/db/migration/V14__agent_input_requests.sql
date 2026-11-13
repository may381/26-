CREATE TABLE agent_input_request (
 id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 owner_task_id VARCHAR(36) NOT NULL,
 root_task_id VARCHAR(36) NOT NULL,
 version INT NOT NULL,
 state VARCHAR(16) NOT NULL,
 question_json JSON NOT NULL,
 answer_json JSON NULL,
 presented BOOLEAN NOT NULL DEFAULT FALSE,
 created_at TIMESTAMP(6) NOT NULL,
 INDEX idx_pending_root(root_task_id,state,presented),
 FOREIGN KEY(owner_task_id) REFERENCES agent_task(id),
 FOREIGN KEY(root_task_id) REFERENCES agent_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
