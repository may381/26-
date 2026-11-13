package cn.silvertravel.platform.agent;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.Duration;
import java.net.http.HttpClient;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/** Persist before sending. An uncertain invocation is never automatically submitted again. */
@Service
@Profile("!bootstrap")
public class AgentTaskExecutor {
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    private final AgentProperties properties;
    private final TransactionTemplate tx;
    private final RestClient http;
    private final RestClient controlHttp;
    private final AgentActionService actions;
    private final AgentDelegationService delegations;
    private final AgentInputService inputs;
    private final AgentMemoryService memory;private final AgentAttachmentService attachments;private final AgentResponseChecks responseChecks;private final AgentBusinessToolService business;private final AgentConversationContext conversations;
    public AgentTaskExecutor(JdbcTemplate jdbc,ObjectMapper json,AgentProperties properties,PlatformTransactionManager manager,AgentActionService actions,AgentDelegationService delegations,AgentInputService inputs,AgentMemoryService memory,AgentAttachmentService attachments,AgentResponseChecks responseChecks,AgentBusinessToolService business,AgentConversationContext conversations) {
        this.jdbc=jdbc;this.json=json;this.properties=properties;this.tx=new TransactionTemplate(manager);
        this.actions=actions;this.delegations=delegations;this.inputs=inputs;this.memory=memory;this.attachments=attachments;this.responseChecks=responseChecks;this.business=business;this.conversations=conversations;
        var factory=new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).followRedirects(HttpClient.Redirect.NEVER).build());
        factory.setReadTimeout(Duration.ofSeconds(60));http=RestClient.builder().requestFactory(factory).build();
        var controlFactory=new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).followRedirects(HttpClient.Redirect.NEVER).build());controlFactory.setReadTimeout(Duration.ofSeconds(3));controlHttp=RestClient.builder().requestFactory(controlFactory).build();
    }
    @Scheduled(fixedDelay=1000)
    public void tick() {
        recoverExpired();delegations.reconcile();
        for(String task:jdbc.queryForList("SELECT id FROM agent_task WHERE state='QUEUED' ORDER BY created_at LIMIT 5",String.class)) {
            ObjectNode invocation=tx.execute(status->claim(task));
            if(invocation==null)continue;
            try {JsonNode result=call(invocation);tx.executeWithoutResult(status->finish(invocation,result));}
            catch(RuntimeException failure){org.slf4j.LoggerFactory.getLogger(getClass()).warn("Agent invocation failed: {}",failure.getClass().getSimpleName());if(!recoverReceipt(invocation))tx.executeWithoutResult(status->unknown(invocation));}
            delegations.reconcile();
        }
    }
    private ObjectNode claim(String id) {
        var rows=jdbc.queryForList("SELECT user_id,snapshot,request_json FROM agent_task WHERE id=? AND state='QUEUED' FOR UPDATE",id);
        if(rows.isEmpty())return null;
        var row=rows.getFirst();ObjectNode s=read(row.get("snapshot"));JsonNode original=read(row.get("request_json"));Instant now=Instant.now();
        if(!Instant.parse(s.path("expiresAt").asText()).isAfter(now))return null;
        String rootTask=inputs.root(id);
        int calls=jdbc.queryForObject("SELECT COUNT(*) FROM agent_invocation WHERE task_id=? OR task_id IN (SELECT child_task_id FROM agent_delegation WHERE parent_task_id=?)",Integer.class,rootTask,rootTask);
        if(calls>=20){s.put("status","FAILED").put("phase","BUDGET_EXHAUSTED").put("version",s.path("version").asLong()+1);s.putObject("error").put("code","TASK_CALL_LIMIT").put("message","本任务树已达20次调用限制，请结束后重新提出需求").put("retryable",false);jdbc.update("UPDATE agent_task SET state='FAILED',version=version+1,snapshot=?,updated_at=? WHERE id=?",encode(s),Timestamp.from(now),id);return null;}
        long version=s.path("version").asLong()+1;String invocation=UUID.randomUUID().toString();
        s.put("version",version).put("status","RUNNING").put("phase","AGENT_CALL").put("updatedAt",now.toString());
        ObjectNode request=json.createObjectNode();request.put("protocolVersion","3.0").put("userId",row.get("user_id").toString()).put("conversationId",s.path("conversationId").asText()).put("messageId",s.path("sourceMessageId").asText());
        request.set("input",original.path("input"));request.withObject("input").remove("responseTo");
        request.putObject("task").put("id",id).put("parentTaskId",s.path("parentTaskId").isNull()?null:s.path("parentTaskId").asText()).put("version",version).put("attempt",1).put("invocationId",invocation).put("deadlineAt",now.plusSeconds(65).toString());
        ObjectNode context=request.putObject("context");context.put("reason",original.path("continueTaskId").isTextual()?"INPUT_PROVIDED":"USER_MESSAGE");
        if(s.has("resumeReason"))context.put("reason",s.path("resumeReason").asText());
        for(String name:List.of("businessRefs","history","completedEffects","candidateTasks","dependencyResults","confirmationResults","actionLedger","planSteps","pendingInputRequests"))context.putArray(name);
        if(original.path("context").path("businessRefs").size()>0)throw new IllegalArgumentException("Business references require registered authorization resolver");
        context.putObject("readSet").put("memoryRevision",memory.currentRevision(row.get("user_id").toString())).put("authorizationRevision",0).putArray("provenanceRefs");
        if(s.path("parentTaskId").isNull())context.set("history",json.valueToTree(conversations.history(row.get("user_id").toString(),s.path("conversationId").asText(),s.path("sourceMessageId").asText())));
        if(s.path("parentTaskId").isNull())context.set("candidateTasks",json.valueToTree(conversations.candidates(row.get("user_id").toString(),s.path("conversationId").asText(),id)));
        context.set("inputResponse",s.has("inputResponse")?s.path("inputResponse"):json.nullNode());
        context.set("pendingInputRequests",json.valueToTree(inputs.pending(inputs.root(id))));
        context.set("dependencyResults",json.valueToTree(delegations.results(id)));
        context.set("actionLedger",json.valueToTree(actions.ledger(id)));
        context.set("planSteps",json.valueToTree(actions.contextSteps(id)));
        context.set("confirmationResults",json.valueToTree(actions.decisions(id)));
        context.set("completedEffects",s.path("effects"));
        // No tools are granted by this text-only execution slice. A random non-authorizing token cannot pass the legacy tool registry.
        request.put("capabilityToken",UUID.randomUUID().toString());
        jdbc.update("UPDATE agent_task SET state='RUNNING',version=?,snapshot=?,updated_at=? WHERE id=?",version,encode(s),Timestamp.from(now),id);
        jdbc.update("INSERT INTO agent_invocation(id,task_id,task_version,agent_id,state,request_json,deadline_at,created_at,updated_at) VALUES (?,?,?,?,'RUNNING',?,?,?,?)",invocation,id,version,delegations.target(id),encode(request),Timestamp.from(now.plusSeconds(65)),Timestamp.from(now),Timestamp.from(now));
        try{memory.inherit(id,invocation,row.get("user_id").toString());conversations.inherit(id,invocation,row.get("user_id").toString(),context.path("history"));if(attachments.stale(id))throw cn.silvertravel.platform.common.api.BusinessException.conflict("附件已失效");}catch(cn.silvertravel.platform.common.api.BusinessException invalid){
            s.put("status","FAILED").put("phase","CONTEXT_INVALIDATED").put("version",version+1).putNull("reply");s.putArray("results");s.putObject("error").put("code","CONTEXT_INVALIDATED").put("message","记忆已变化，请重新提出需求").put("retryable",false);
            jdbc.update("UPDATE agent_task SET state='FAILED',version=?,snapshot=? WHERE id=?",version+1,encode(s),id);jdbc.update("UPDATE agent_invocation SET state='DISCARDED' WHERE id=?",invocation);return null;
        }
        return request;
    }
    private JsonNode call(ObjectNode r) {
        if(properties.mode()==AgentProperties.Mode.disabled)throw new IllegalStateException("Agent disabled");
        if(properties.mode()==AgentProperties.Mode.http) {
            JsonNode envelope=http.post().uri(properties.url(delegations.target(r.path("task").path("id").asText()))+"/internal/v3/messages").header("X-Agent-Key",properties.key(delegations.target(r.path("task").path("id").asText()))).header("X-Trace-Id",r.path("task").path("invocationId").asText()).body(r).retrieve().body(JsonNode.class);
            if(envelope==null || !"OK".equals(envelope.path("code").asText()))throw new IllegalStateException("Invalid response envelope");
            return envelope.path("data");
        }
        ObjectNode d=json.createObjectNode();d.put("conversationId",r.path("conversationId").asText()).put("messageId",r.path("messageId").asText()).put("taskId",r.path("task").path("id").asText()).put("baseTaskVersion",r.path("task").path("version").asLong()).put("invocationId",r.path("task").path("invocationId").asText());
        for(JsonNode image:r.path("input").path("attachmentIds"))attachments.agent(delegations.target(r.path("task").path("id").asText()),r.path("capabilityToken").asText(),r.path("task").path("id").asText(),image.asText());
        String mockDomain="a1".equals(delegations.target(r.path("task").path("id").asText()))?"tourism":("a3".equals(delegations.target(r.path("task").path("id").asText()))?"culture":"care");d.put("intent",mockDomain).putNull("handoff");d.putArray("domains").add(mockDomain);
        boolean ask="USER_MESSAGE".equals(r.path("context").path("reason").asText()) && r.path("input").path("text").asText().contains("追问")&&!r.path("input").path("text").asText().contains("协作演示");
        ObjectNode c=d.putObject("control");c.put("next",ask?"WAIT_INPUT":"COMPLETE").put("outcome",ask?null:"SUCCEEDED").putNull("inputRequest");c.putArray("dependencyTaskIds");
        if(ask){var q=c.putObject("inputRequest");q.put("inputRequestId",UUID.randomUUID().toString()).put("question","您准备去哪座城市？").put("allowFreeText",true);q.putArray("requiredFields").add("city");q.putArray("options");}
        d.putObject("reply").put("text",ask?"演示追问：您准备去哪座城市？":"模拟任务完成："+r.path("input").path("text").asText()).put("speechRate",0.8).putNull("audioUrl");
        if("CONFIRMATION_DECIDED".equals(r.path("context").path("reason").asText())){
            String state=r.path("context").path("confirmationResults").get(0).path("state").asText();
            boolean memoryChange="memory.change".equals(r.path("context").path("confirmationResults").get(0).path("tool").asText());
            d.withObject("reply").put("text","EXECUTED".equals(state)?(memoryChange?"您确认的长期偏好已保存，可随时查看和删除。":"平台已按您确认的参数调整路线，操作结果已保存。"):(memoryChange?"您未批准保存，候选未成为长期记忆。":"您已拒绝或取消该操作，路线没有因此改变。"));
            if(r.path("context").path("confirmationResults").size()>1){int executed=0,skipped=0;for(JsonNode decision:r.path("context").path("confirmationResults")){if("EXECUTED".equals(decision.path("state").asText()))executed++;else skipped++;}d.withObject("reply").put("text","本次逐项确认已处理："+executed+"项已执行，"+skipped+"项未执行；具体结果以平台记录为准。");}
        }
        for(String name:List.of("results","confirmationIds","tools","usedMemoryRefs"))d.putArray(name);
        boolean root=r.path("task").path("parentTaskId").isNull();
        if(!root){
            if(r.path("input").path("text").asText().startsWith("审核记忆:")){
                String candidate=r.path("input").path("text").asText().substring(5);
                JsonNode review=memoryTool(r,"a3","memory.candidate.review",json.valueToTree(new AgentMemoryService.Review(candidate,1,"ADD","演示审核建议，仍需老人确认")));
                ObjectNode card=d.withArray("results").addObject();card.put("resultId",UUID.randomUUID().toString()).put("type","MEMORY_REVIEW").put("schemaVersion","1.0").put("title","候选记忆审核").putNull("businessRef").put("availability","DEMO").put("generatedAt",Instant.now().toString());card.putArray("sources");card.putArray("pendingChecks");card.set("payload",review);
                c.put("next","COMPLETE").put("outcome","SUCCEEDED");return d;
            }
            if(ask)return d;
            c.put("next","COMPLETE").put("outcome","SUCCEEDED");c.putNull("inputRequest");
            d.withObject("reply").put("text","模拟子任务已完成："+r.path("input").path("text").asText());
            if(r.path("input").path("text").asText().contains("模拟失败")){c.put("outcome","FAILED");d.withObject("reply").put("text","明确标记的子任务失败演示");}
            return d;
        }
        if("CHILD_INPUT_REQUIRED".equals(r.path("context").path("reason").asText())){
            JsonNode question=r.path("context").path("pendingInputRequests").get(0);c.put("next","WAIT_INPUT").putNull("outcome");c.set("inputRequest",inputs.draft(question));d.withObject("reply").put("text","协作方需要补充信息："+question.path("question").asText());return d;
        }
        if("CHILDREN_FINISHED".equals(r.path("context").path("reason").asText())&&r.path("input").path("text").asText().contains("记忆演示")){
            JsonNode review=memory.reviews(r.path("task").path("id").asText()).getFirst();
            var change=new AgentMemoryService.Change("ADD",review.path("candidateId").asText(),1,review.path("reviewId").asText(),1);
            JsonNode confirmation=prepareConfirmation(r,"memory.change",json.valueToTree(change));c.put("next","WAIT_CONFIRMATION").putNull("outcome");d.withArray("confirmationIds").add(confirmation.path("confirmationId").asText());d.withObject("reply").put("text","演示偏好已审核，请确认是否长期保存。");
            if(r.path("input").path("text").asText().contains("双确认")){
                String user=r.path("userId").asText(),trip=jdbc.queryForObject("SELECT id FROM trip WHERE user_id=? AND status='ACTIVE'",String.class,user);
                long seq=jdbc.queryForObject("SELECT COALESCE(MAX(progress_seq),0) FROM trip_progress WHERE trip_id=?",Long.class,trip);int revision=jdbc.queryForObject("SELECT COALESCE(MAX(revision),0) FROM trip_route_adjustment WHERE trip_id=?",Integer.class,trip);
                JsonNode route=prepareConfirmation(r,AgentActionService.TOOL,json.valueToTree(new AgentActionService.Args(trip,"r2",seq,revision,"独立的路线确认演示")));d.withArray("confirmationIds").add(route.path("confirmationId").asText());d.withObject("reply").put("text","请分别决定是否保存演示偏好、是否调整路线；两项授权互不代替。");
            }return d;
        }
        if("USER_MESSAGE".equals(r.path("context").path("reason").asText())&&r.path("input").path("text").asText().contains("业务查询演示")){
            for(String tool:List.of("spot.list","facility.search")){
                JsonNode args=business.normalize(tool,json.createObjectNode());JsonNode action=prepareAction(r,"a1",tool,args);JsonNode result=business.execute("a1",r.path("capabilityToken").asText(),new AgentMemoryService.ToolRequest("3.0",r.path("task").path("id").asText(),action.path("stepId").asText(),action.path("actionId").asText(),new AgentMemoryService.ToolInput(tool,args,null))).path("result");ObjectNode trace=d.withArray("tools").addObject();trace.put("tool",tool);trace.set("args",args);trace.set("result",result);
            }
            d.withObject("reply").put("text","已通过P2真实查询景点和设施；数据来源仍以MOCK或实际资料标识为准。");return d;
        }
        if("USER_MESSAGE".equals(r.path("context").path("reason").asText())&&r.path("input").path("text").asText().contains("记忆演示")){
            var candidate=new AgentMemoryService.Candidate("LONG_TERM_PREFERENCE","demo.culturePreference","演示偏好：喜欢文化活动",json.getNodeFactory().booleanNode(true),List.of("culture"),"GENERAL",List.of(new AgentMemoryService.Source("USER_MESSAGE",r.path("messageId").asText())));
            JsonNode created=memoryTool(r,"a1","memory.candidate.create",json.valueToTree(candidate));
            var input=new AgentDelegationService.Input("a3","culture",true,"审核记忆:"+created.path("candidateId").asText(),List.of(),List.of());JsonNode action=prepareAction(r,"a1","agent.delegate",json.valueToTree(input));
            JsonNode child=delegations.delegate("a1",r.path("capabilityToken").asText(),new AgentDelegationService.Request("3.0",r.path("conversationId").asText(),r.path("task").path("id").asText(),action.path("actionId").asText(),input));
            c.put("next","WAIT_DEPENDENCIES").putNull("outcome");c.putArray("dependencyTaskIds").add(child.path("childTaskId").asText());d.withObject("reply").put("text","演示候选已交A3审核，尚未长期保存。");return d;
        }
        if("USER_MESSAGE".equals(r.path("context").path("reason").asText())&&r.path("input").path("text").asText().contains("检索记忆")){
            JsonNode searchArgs=json.valueToTree(new AgentMemoryService.Search("演示文化活动偏好检索","文化",List.of("culture"),5,2000));
            JsonNode result=memoryTool(r,"a1","memory.search",searchArgs);
            for(JsonNode item:result.path("items"))d.withArray("usedMemoryRefs").addObject().put("memoryId",item.path("memoryId").asText()).put("version",item.path("version").asInt());
            ObjectNode trace=d.withArray("tools").addObject();trace.put("tool","memory.search");trace.set("args",searchArgs);trace.set("result",result);
            d.withObject("reply").put("text","已读取 "+result.path("items").size()+" 条授权有效记忆。");return d;
        }
        if("CHILDREN_FINISHED".equals(r.path("context").path("reason").asText())){
            long failures=0;for(JsonNode n:r.path("context").path("dependencyResults"))if(!"SUCCEEDED".equals(n.path("status").asText()))failures++;
            c.put("next","COMPLETE").put("outcome",failures==0?"SUCCEEDED":"PARTIALLY_SUCCEEDED");
            d.withObject("reply").put("text",failures==0?"模拟协作完成，已整合A2和A3的保存结果。":"模拟协作部分完成，失败项已保留，未重复运行成功的子任务。");return d;
        }
        if("USER_MESSAGE".equals(r.path("context").path("reason").asText())&&r.path("input").path("text").asText().contains("协作演示")){
            var ids=c.putArray("dependencyTaskIds");
            for(String target:List.of("a2","a3")){
                var input=new AgentDelegationService.Input(target,"a2".equals(target)?"care":"culture","a2".equals(target),"a3".equals(target)&&r.path("input").path("text").asText().contains("部分失败")?"模拟失败":((r.path("input").path("text").asText().contains("子任务双追问")||(r.path("input").path("text").asText().contains("子任务追问")&&"a3".equals(target)))?"追问城市":"模拟领域查询"),List.of(),List.of());
                String task=r.path("task").path("id").asText(),token=r.path("capabilityToken").asText();JsonNode args=json.valueToTree(input);
                var step=actions.steps("a1",token,new AgentActionService.Steps("3.0",task,r.path("task").path("invocationId").asText()+target,1,List.of(new AgentActionService.Step(target,"agent.delegate",args)))).path("steps").get(0);
                var action=actions.prepare("a1",token,new AgentActionService.Prepare("3.0",task,step.path("stepId").asText(),new AgentActionService.ActionInput("agent.delegate",args)),step.path("prepareKey").asText());
                var result=delegations.delegate("a1",token,new AgentDelegationService.Request("3.0",r.path("conversationId").asText(),task,action.path("actionId").asText(),input));String child=result.path("childTaskId").asText();ids.add(child);
                // Deterministic mock race: children finish before the parent registers WAIT_DEPENDENCIES.
                if(r.path("input").path("text").asText().contains("提前完成")){ObjectNode childCall=tx.execute(status->claim(child));JsonNode childResult=call(childCall);tx.executeWithoutResult(status->finish(childCall,childResult));}
            }
            c.put("next","WAIT_DEPENDENCIES").putNull("outcome");d.withObject("reply").put("text","模拟协作已委派，等待A2/A3结果。");return d;
        }
        if("USER_MESSAGE".equals(r.path("context").path("reason").asText())&&r.path("input").path("text").asText().contains("确认改线")) {
            String user=r.path("userId").asText(), task=r.path("task").path("id").asText(), token=r.path("capabilityToken").asText();
            var trips=jdbc.queryForList("SELECT id FROM trip WHERE user_id=? AND status='ACTIVE'",String.class,user);
            if(trips.size()!=1)throw new IllegalStateException("演示改线需要一条进行中的游览");String trip=trips.getFirst();
            long seq=jdbc.queryForObject("SELECT COALESCE(MAX(progress_seq),0) FROM trip_progress WHERE trip_id=?",Long.class,trip);
            int revision=jdbc.queryForObject("SELECT COALESCE(MAX(revision),0) FROM trip_route_adjustment WHERE trip_id=?",Integer.class,trip);
            JsonNode args=json.valueToTree(new AgentActionService.Args(trip,"r2",seq,revision,"老人确认后调整演示路线"));
            JsonNode registered=actions.steps("a1",token,new AgentActionService.Steps("3.0",task,r.path("task").path("invocationId").asText(),1,List.of(new AgentActionService.Step("adjust-route",AgentActionService.TOOL,args))));
            JsonNode step=registered.path("steps").get(0);
            JsonNode action=actions.prepare("a1",token,new AgentActionService.Prepare("3.0",task,step.path("stepId").asText(),new AgentActionService.ActionInput(AgentActionService.TOOL,args)),step.path("prepareKey").asText());
            JsonNode confirmation=actions.confirm("a1",token,new AgentActionService.Confirm("3.0",task,action.path("actionId").asText()));
            c.put("next","WAIT_CONFIRMATION").putNull("outcome");d.withArray("confirmationIds").add(confirmation.path("confirmationId").asText());d.withObject("reply").put("text","演示路线调整已准备，请查看具体路线并选择同意或拒绝。");
        }
        if(r.path("input").path("text").asText().contains("收据恢复演示")){
            ObjectNode receipt=json.createObjectNode().put("invocationId",r.path("task").path("invocationId").asText()).put("status","FINISHED");receipt.putObject("result").put("code","OK").put("message","演示持久收据").set("data",d);jdbc.update("UPDATE agent_invocation SET receipt_json=? WHERE id=?",encode(receipt),r.path("task").path("invocationId").asText());throw new IllegalStateException("DEMO_RESPONSE_LOST");
        }
        if(r.path("input").path("attachmentIds").size()>0)d.withObject("reply").put("text","演示附件已关联，真实图片理解需A1模型服务接入。");
        return d;
    }
    private JsonNode prepareAction(ObjectNode r,String caller,String tool,JsonNode args){
        String task=r.path("task").path("id").asText(),token=r.path("capabilityToken").asText();
        JsonNode step=actions.steps(caller,token,new AgentActionService.Steps("3.0",task,r.path("task").path("invocationId").asText()+tool,1,List.of(new AgentActionService.Step(tool,tool,args)))).path("steps").get(0);
        ObjectNode action=(ObjectNode)actions.prepare(caller,token,new AgentActionService.Prepare("3.0",task,step.path("stepId").asText(),new AgentActionService.ActionInput(tool,args)),step.path("prepareKey").asText());action.put("stepId",step.path("stepId").asText());return action;
    }
    private JsonNode memoryTool(ObjectNode r,String caller,String tool,JsonNode args){JsonNode action=prepareAction(r,caller,tool,args);return memory.execute(caller,r.path("capabilityToken").asText(),new AgentMemoryService.ToolRequest("3.0",r.path("task").path("id").asText(),action.path("stepId").asText(),action.path("actionId").asText(),new AgentMemoryService.ToolInput(tool,args,null))).path("result");}
    private JsonNode prepareConfirmation(ObjectNode r,String tool,JsonNode args){JsonNode action=prepareAction(r,"a1",tool,args);return actions.confirm("a1",r.path("capabilityToken").asText(),new AgentActionService.Confirm("3.0",r.path("task").path("id").asText(),action.path("actionId").asText()));}
    private void finish(ObjectNode r,JsonNode d) {
        responseChecks.validate(d);
        String id=r.path("task").path("id").asText(), invoke=r.path("task").path("invocationId").asText();long version=r.path("task").path("version").asLong();
        if(!d.path("taskId").asText().equals(id)||d.path("baseTaskVersion").asLong()!=version||!d.path("invocationId").asText().equals(invoke)||!d.path("conversationId").equals(r.path("conversationId"))||!d.path("messageId").equals(r.path("messageId")))throw new IllegalStateException("Mismatched invocation");
        if(!AgentTextSafety.valid(d.path("reply").path("text").asText()))throw new IllegalStateException("无效回复文本");
        actions.verifyTools(id,d.path("tools"));memory.verifyUsed(invoke,d.path("usedMemoryRefs"));
        for(JsonNode card:d.path("results")){if(!"MEMORY_REVIEW".equals(card.path("type").asText()))throw new IllegalStateException("结果类型未注册");memory.reviewCard(id,card.path("payload"));}
        double rate=d.path("reply").path("speechRate").asDouble(Double.NaN);
        if(!Double.isFinite(rate)||rate<0.5||rate>1.5||!d.path("reply").path("audioUrl").isNull())throw new IllegalStateException("Invalid reply media");
        String next=d.path("control").path("next").asText();if(!List.of("COMPLETE","WAIT_INPUT","WAIT_CONFIRMATION","WAIT_DEPENDENCIES").contains(next))throw new IllegalStateException("Control not implemented");
        if("COMPLETE".equals(next)&&!List.of("SUCCEEDED","PARTIALLY_SUCCEEDED","FAILED").contains(d.path("control").path("outcome").asText()))throw new IllegalStateException("Unsupported outcome");
        if("COMPLETE".equals(next)){
            for(JsonNode child:delegations.results(id)){
                if(!List.of("SUCCEEDED","PARTIALLY_SUCCEEDED","FAILED","CANCELLED","EXPIRED").contains(child.path("status").asText()))throw new IllegalStateException("子任务尚未结束");
                if(child.path("required").asBoolean()&&!"SUCCEEDED".equals(child.path("status").asText())&&"SUCCEEDED".equals(d.path("control").path("outcome").asText()))throw new IllegalStateException("必需依赖失败不能标记全部成功");
            }
        }
        if(!"a1".equals(delegations.target(id))&&!List.of("COMPLETE","WAIT_INPUT").contains(next))throw new IllegalStateException("子任务确认和再次委派尚未开放");
        var rows=jdbc.queryForList("SELECT snapshot,user_id FROM agent_task WHERE id=? AND version=? AND state='RUNNING' FOR UPDATE",id,version);
        if(rows.isEmpty()){jdbc.update("UPDATE agent_invocation SET state='DISCARDED',updated_at=? WHERE id=? AND state='RUNNING'",Timestamp.from(Instant.now()),invoke);return;}
        memory.checkInvocation(invoke,rows.getFirst().get("user_id").toString());attachments.assertFresh(id);
        Set<String> valid=new HashSet<>();for(JsonNode confirmation:actions.pending(id))valid.add(confirmation.path("confirmationId").asText());
        for(JsonNode confirmation:d.path("confirmationIds"))if(!valid.contains(confirmation.asText()))throw new IllegalStateException("伪造或失效确认ID");
        if("WAIT_CONFIRMATION".equals(next)&&(d.path("confirmationIds").isEmpty()||d.path("confirmationIds").size()!=valid.size()||d.path("confirmationIds").size()!=new java.util.HashSet<>(json.convertValue(d.path("confirmationIds"),java.util.List.class)).size()))throw new IllegalStateException("必须引用全部有效确认，且不能重复");
        if(!"WAIT_CONFIRMATION".equals(next)&&(!valid.isEmpty()||d.path("confirmationIds").size()>0))throw new IllegalStateException("尚有待确认操作");
        var row=rows.getFirst();ObjectNode s=read(row.get("snapshot"));s.set("reply",d.path("reply"));s.set("results",d.path("results"));s.put("status","WAIT_INPUT".equals(next)?"WAITING_INPUT":"SUCCEEDED").put("phase","AGENT_RESULT").put("version",version+1).put("updatedAt",Instant.now().toString());
        if("COMPLETE".equals(next))s.put("status",d.path("control").path("outcome").asText());
        if("FAILED".equals(s.path("status").asText()))s.putObject("error").put("code","AGENT_TASK_FAILED").put("message","Agent报告任务未能完成").put("retryable",false);
        s.set("childTasks",json.valueToTree(delegations.summaries(id)));
        if("WAIT_DEPENDENCIES".equals(next)){delegations.validateDependencies(id,d.path("control").path("dependencyTaskIds"));s.put("status","WAITING_DEPENDENCIES");}
        if("WAIT_CONFIRMATION".equals(next)){s.put("status","WAITING_CONFIRMATION");s.set("confirmationIds",d.path("confirmationIds"));}
        if("WAIT_INPUT".equals(next)){ObjectNode q=inputs.register(id,d.path("control").path("inputRequest"));s.set("inputRequest",q);s.set("pendingInputRequests",json.valueToTree(inputs.pending(inputs.root(id))));if(s.path("parentTaskId").isNull())for(JsonNode visible:r.path("context").path("pendingInputRequests"))jdbc.update("UPDATE agent_input_request SET presented=TRUE WHERE id=? AND root_task_id=? AND state='PENDING'",visible.path("inputRequestId").asText(),id);}
        jdbc.update("UPDATE agent_task SET state=?,version=?,snapshot=?,updated_at=? WHERE id=?",s.path("status").asText(),version+1,encode(s),Timestamp.from(Instant.now()),id);
        jdbc.update("UPDATE agent_invocation SET state='FINISHED',response_json=?,updated_at=? WHERE id=?",encode(d),Timestamp.from(Instant.now()),invoke);
        if(s.path("parentTaskId").isNull())jdbc.update("INSERT INTO agent_message(id,conversation_id,task_id,user_id,role,text,created_at) VALUES (?,?,?,?,'assistant',?,?)",UUID.randomUUID().toString(),s.path("conversationId").asText(),id,row.get("user_id"),d.path("reply").path("text").asText(),Timestamp.from(Instant.now()));
    }
    private void unknown(ObjectNode r) {
        String id=r.path("task").path("id").asText();long version=r.path("task").path("version").asLong();
        var rows=jdbc.queryForList("SELECT snapshot FROM agent_task WHERE id=? AND state='RUNNING' AND version=? FOR UPDATE",id,version);
        jdbc.update("UPDATE agent_invocation SET state='UNKNOWN',updated_at=? WHERE id=? AND state='RUNNING'",Timestamp.from(Instant.now()),r.path("task").path("invocationId").asText());
        if(rows.isEmpty())return;ObjectNode s=read(rows.getFirst().get("snapshot"));s.put("status","FAILED").put("phase","RECONCILIATION_REQUIRED").put("version",version+1).put("updatedAt",Instant.now().toString());s.putObject("error").put("code","INVOCATION_UNRESOLVED").put("message","调用结果未确认或格式不受支持，请核查调用记录；未自动重试").put("retryable",false);
        jdbc.update("UPDATE agent_task SET state='FAILED',version=?,snapshot=?,updated_at=? WHERE id=?",version+1,encode(s),Timestamp.from(Instant.now()),id);
    }
    private void recoverExpired(){for(String request:jdbc.queryForList("SELECT request_json FROM agent_invocation WHERE state='RUNNING' AND deadline_at<?",String.class,Timestamp.from(Instant.now()))){ObjectNode r=read(request);if(!recoverReceipt(r))tx.executeWithoutResult(status->unknown(r));}}
    private boolean recoverReceipt(ObjectNode r){
        String id=r.path("task").path("invocationId").asText();
        if(jdbc.update("UPDATE agent_invocation SET receipt_attempts=receipt_attempts+1 WHERE id=? AND receipt_attempts=0 AND state='RUNNING'",id)!=1)return false;
        try{
            JsonNode receipt;
            if(properties.mode()==AgentProperties.Mode.mock){var saved=jdbc.queryForList("SELECT receipt_json FROM agent_invocation WHERE id=? AND receipt_json IS NOT NULL",String.class,id);if(saved.isEmpty())return false;receipt=read(saved.getFirst());}
            else if(properties.mode()==AgentProperties.Mode.http){String agent=delegations.target(r.path("task").path("id").asText());JsonNode envelope=controlHttp.get().uri(properties.url(agent)+"/internal/v3/invocations/"+id).header("X-Agent-Key",properties.key(agent)).retrieve().body(JsonNode.class);if(envelope==null||!"OK".equals(envelope.path("code").asText()))return false;receipt=envelope.path("data");}
            else return false;
            if(!id.equals(receipt.path("invocationId").asText())||!"FINISHED".equals(receipt.path("status").asText())||!"OK".equals(receipt.path("result").path("code").asText()))return false;
            jdbc.update("UPDATE agent_invocation SET receipt_json=? WHERE id=?",encode(receipt),id);JsonNode result=receipt.path("result").path("data");tx.executeWithoutResult(status->finish(r,result));return true;
        }catch(RuntimeException failure){return false;}
    }
    @Scheduled(fixedDelay=2000)
    public void cancelRemote(){
        for(var row:jdbc.queryForList("SELECT id,agent_id,cancel_request_id FROM agent_invocation WHERE state='CANCEL_REQUESTED' AND cancel_attempts<3 LIMIT 10")){
            String id=row.get("id").toString(),cancel=row.get("cancel_request_id")==null?UUID.randomUUID().toString():row.get("cancel_request_id").toString();
            if(jdbc.update("UPDATE agent_invocation SET cancel_attempts=cancel_attempts+1,cancel_request_id=COALESCE(cancel_request_id,?) WHERE id=? AND state='CANCEL_REQUESTED' AND cancel_attempts<3",cancel,id)!=1)continue;
            if(properties.mode()==AgentProperties.Mode.mock){jdbc.update("UPDATE agent_invocation SET state='CANCELLED',updated_at=? WHERE id=? AND state='CANCEL_REQUESTED'",Timestamp.from(Instant.now()),id);continue;}
            if(properties.mode()!=AgentProperties.Mode.http)continue;
            try{String agent=row.get("agent_id").toString();var body=Map.of("protocolVersion","3.0","invocationId",id,"cancelRequestId",cancel,"reason","用户已在P2取消任务");JsonNode response=controlHttp.post().uri(properties.url(agent)+"/internal/v3/invocations/"+id+"/cancel").header("X-Agent-Key",properties.key(agent)).body(body).retrieve().body(JsonNode.class);
                if(response!=null&&"OK".equals(response.path("code").asText())&&id.equals(response.path("data").path("invocationId").asText())&&cancel.equals(response.path("data").path("cancelRequestId").asText())){String state=response.path("data").path("status").asText();if(Set.of("CANCELLED","FINISHED","FAILED").contains(state))jdbc.update("UPDATE agent_invocation SET state=?,updated_at=? WHERE id=? AND state='CANCEL_REQUESTED'","CANCELLED".equals(state)?"CANCELLED":"DISCARDED",Timestamp.from(Instant.now()),id);}
            }catch(RuntimeException failure){org.slf4j.LoggerFactory.getLogger(getClass()).warn("Agent cancel pending; invocation={}",id);}
        }
    }
    private ObjectNode read(Object o){try{return (ObjectNode)json.readTree(o.toString());}catch(Exception e){throw new IllegalStateException(e);}}
    private String encode(Object o){try{return json.writeValueAsString(o);}catch(Exception e){throw new IllegalStateException(e);}}
}
