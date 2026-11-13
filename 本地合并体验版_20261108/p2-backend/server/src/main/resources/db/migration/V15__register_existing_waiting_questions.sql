INSERT INTO agent_input_request(id,owner_task_id,root_task_id,version,state,question_json,presented,created_at)
SELECT JSON_UNQUOTE(JSON_EXTRACT(t.snapshot,'$.inputRequest.inputRequestId')),
       t.id,
       COALESCE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(t.snapshot,'$.parentTaskId')),'null'),t.id),
       CAST(JSON_UNQUOTE(JSON_EXTRACT(t.snapshot,'$.inputRequest.version')) AS UNSIGNED),
       'PENDING',JSON_REMOVE(JSON_EXTRACT(t.snapshot,'$.inputRequest'),'$.ownerTaskId','$.version'),TRUE,t.updated_at
FROM agent_task t
WHERE t.state='WAITING_INPUT'
  AND JSON_TYPE(JSON_EXTRACT(t.snapshot,'$.inputRequest'))='OBJECT'
  AND JSON_UNQUOTE(JSON_EXTRACT(t.snapshot,'$.inputRequest.ownerTaskId'))=t.id
  AND NOT EXISTS (SELECT 1 FROM agent_input_request q WHERE q.id=JSON_UNQUOTE(JSON_EXTRACT(t.snapshot,'$.inputRequest.inputRequestId')));
