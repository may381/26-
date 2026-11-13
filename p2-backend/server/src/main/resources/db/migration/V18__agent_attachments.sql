CREATE TABLE agent_attachment (
 id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 user_id VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
 purpose VARCHAR(32) NOT NULL,
 mime_type VARCHAR(32) NOT NULL,
 size_bytes INT NOT NULL,
 width INT NOT NULL,
 height INT NOT NULL,
 state VARCHAR(16) NOT NULL,
 content LONGBLOB NULL,
 created_at TIMESTAMP(6) NOT NULL,
 expires_at TIMESTAMP(6) NOT NULL,
 INDEX idx_attachment_owner(user_id,state,expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE agent_task_attachment (
 task_id VARCHAR(36) NOT NULL,
 attachment_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 PRIMARY KEY(task_id,attachment_id),
 FOREIGN KEY(task_id) REFERENCES agent_task(id),
 FOREIGN KEY(attachment_id) REFERENCES agent_attachment(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE agent_attachment_read (
 invocation_id VARCHAR(36) NOT NULL,
 attachment_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 read_at TIMESTAMP(6) NOT NULL,
 PRIMARY KEY(invocation_id,attachment_id),
 FOREIGN KEY(invocation_id) REFERENCES agent_invocation(id),
 FOREIGN KEY(attachment_id) REFERENCES agent_attachment(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE agent_message_attachment (
 message_id VARCHAR(36) NOT NULL,
 attachment_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 PRIMARY KEY(message_id,attachment_id),
 FOREIGN KEY(message_id) REFERENCES agent_message(id),
 FOREIGN KEY(attachment_id) REFERENCES agent_attachment(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
