-- 构造「父任务(a1,已完成) + 子任务(a2,QUEUED)」结构，
-- 验证 P2(http 模式) 真实把子任务派活给 A2(18002)，A2 回结果单后 P2 写回。
--
-- 关键约束（踩过的坑）：
--  1) delegation.parent_task_id 必须是真实存在的父任务（FOREIGN KEY 约束），
--     且不能指向子任务本身，否则 finish() 会把子任务当成未完成的子任务，
--     抛 IllegalStateException("子任务尚未结束")。
--  2) 子任务 snapshot.parentTaskId 保持 NULL（当作根任务），finish() 才会把
--     A2 回复写入 agent_message；否则回复只进父任务快照。
--  3) claim() 用 Instant.parse(expiresAt)，只认 ISO-8601（如 2026-11-04T...Z），
--     不能用空格本地时间。
--  4) http 模式要求 P2 的 .env 配齐 AGENT_A1/A2/A3 三个 URL 与 Key。
--
-- 执行：mysql -usilver_app -p<密码> -P3308 silver_tourism_demo < insert_test_task.sql

-- 0) 清理本用户全部测试数据（测试库，u100 为专用 mock 老人，无生产数据）
DELETE FROM agent_message WHERE task_id IN (SELECT id FROM agent_task WHERE user_id='u100');
DELETE FROM agent_invocation WHERE task_id IN (SELECT id FROM agent_task WHERE user_id='u100');
DELETE FROM agent_delegation WHERE child_task_id IN (SELECT id FROM agent_task WHERE user_id='u100');
DELETE FROM agent_action WHERE task_id IN (SELECT id FROM agent_task WHERE user_id='u100');
DELETE FROM agent_plan_step WHERE task_id IN (SELECT id FROM agent_task WHERE user_id='u100');
DELETE FROM agent_task WHERE user_id='u100';
DELETE FROM agent_conversation WHERE user_id='u100';

-- 1) 时间统一用 ISO-8601
SET @now = NOW(6);
SET @now_iso = DATE_FORMAT(@now, '%Y-%m-%dT%H:%i:%s.%fZ');
SET @exp_iso = DATE_FORMAT(DATE_ADD(@now, INTERVAL 1 DAY), '%Y-%m-%dT%H:%i:%s.%fZ');
SET @T = UUID();  -- 子任务 (a2)
SET @P = UUID();  -- 父任务 (a1, SUCCEEDED)
SET @C = UUID();  -- 会话
SET @M = UUID();  -- 消息
SET @S = UUID();  -- plan_step
SET @A = UUID();  -- action

-- 2) 会话
INSERT INTO agent_conversation (id, user_id, created_at) VALUES (@C, 'u100', @now);

-- 3) 父任务（仅用于满足 delegation.parent_task_id 外键，并让子任务的 results 为空）
INSERT INTO agent_task (id, user_id, conversation_id, version, state, snapshot, request_json, created_at, updated_at)
VALUES (@P, 'u100', @C, 2, 'SUCCEEDED',
  JSON_OBJECT(
    'taskId', @P, 'conversationId', @C, 'sourceMessageId', @M,
    'parentTaskId', NULL, 'relatedTaskId', NULL, 'version', 2,
    'status', 'SUCCEEDED', 'phase', 'AGENT_RESULT', 'reply', NULL, 'inputRequest', NULL,
    'error', NULL, 'createdAt', @now_iso, 'updatedAt', @now_iso, 'expiresAt', @exp_iso,
    'results', JSON_ARRAY(), 'confirmationIds', JSON_ARRAY(), 'childTasks', JSON_ARRAY(),
    'pendingInputRequests', JSON_ARRAY(), 'effects', JSON_ARRAY()
  ),
  JSON_OBJECT('protocolVersion', '3.0', 'userId', 'u100', 'conversationId', @C,
    'input', JSON_OBJECT('text', '父任务'), 'context', NULL, 'relatedTaskId', NULL),
  @now, @now);

-- 4) 子任务（a2，QUEUED，被 P2 调度钟派活）
INSERT INTO agent_task (id, user_id, conversation_id, version, state, snapshot, request_json, created_at, updated_at)
VALUES (@T, 'u100', @C, 1, 'QUEUED',
  JSON_OBJECT(
    'taskId', @T, 'conversationId', @C, 'sourceMessageId', @M,
    'parentTaskId', NULL, 'relatedTaskId', NULL, 'version', 1,
    'status', 'QUEUED', 'phase', 'ACCEPTED', 'reply', NULL, 'inputRequest', NULL,
    'error', NULL, 'createdAt', @now_iso, 'updatedAt', @now_iso, 'expiresAt', @exp_iso,
    'results', JSON_ARRAY(), 'confirmationIds', JSON_ARRAY(), 'childTasks', JSON_ARRAY(),
    'pendingInputRequests', JSON_ARRAY(), 'effects', JSON_ARRAY()
  ),
  JSON_OBJECT('protocolVersion', '3.0', 'userId', 'u100', 'conversationId', @C,
    'input', JSON_OBJECT('text', '我想了解一下景区的无障碍设施情况'), 'context', NULL, 'relatedTaskId', NULL),
  @now, @now);

-- 5) plan_step（agent_action.step_id 的 FK 来源）
INSERT INTO agent_plan_step (id, task_id, request_key, request_json, prepare_key, tool, args)
VALUES (@S, @T, 'reqkey', JSON_OBJECT(), 'prepkey', 'agent.delegate', JSON_OBJECT());

-- 6) action（agent_delegation.action_id 的 FK 来源）
INSERT INTO agent_action (id, task_id, step_id, tool, args, execution_status, result, created_at)
VALUES (@A, @T, @S, 'agent.delegate', JSON_OBJECT(), 'PENDING', NULL, @now);

-- 7) delegation（子任务 target=a2；parent_task_id 指向独立的已完成父任务）
INSERT INTO agent_delegation (child_task_id, parent_task_id, action_id, target_agent, domain, required_child, request_json, created_at)
VALUES (@T, @P, @A, 'a2', 'care', FALSE, JSON_OBJECT(), @now);

SELECT 'INSERTED task=' AS msg, @T AS task_id, @P AS parent_task_id;
