CREATE TABLE agent_conversation (
 id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
 created_at TIMESTAMP(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE agent_task (
 id VARCHAR(36) PRIMARY KEY,
 user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
 conversation_id VARCHAR(36) NOT NULL,
 version BIGINT NOT NULL,
 state VARCHAR(32) NOT NULL,
 snapshot JSON NOT NULL,
 request_json JSON NOT NULL,
 created_at TIMESTAMP(6) NOT NULL,
 updated_at TIMESTAMP(6) NOT NULL,
 INDEX idx_agent_queue(state,created_at),
 FOREIGN KEY (conversation_id) REFERENCES agent_conversation(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
