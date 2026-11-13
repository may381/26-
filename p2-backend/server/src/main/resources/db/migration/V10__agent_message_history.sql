CREATE TABLE agent_message (
 id VARCHAR(36) PRIMARY KEY,
 conversation_id VARCHAR(36) NOT NULL,
 task_id VARCHAR(36) NOT NULL,
 user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
 role VARCHAR(16) NOT NULL,
 text TEXT NOT NULL,
 created_at TIMESTAMP(6) NOT NULL,
 UNIQUE KEY uk_agent_reply(task_id,role,id),
 INDEX idx_agent_history(conversation_id,created_at,id),
 FOREIGN KEY (task_id) REFERENCES agent_task(id),
 FOREIGN KEY (conversation_id) REFERENCES agent_conversation(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
