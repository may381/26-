package cn.silvertravel.platform.agent;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;
import java.util.Set;
import org.springframework.stereotype.Component;

/** Structural checks for the currently registered v3 response shapes; business checks remain in services. */
@Component
public class AgentResponseChecks {
    private static final Set<String> DOMAINS=Set.of("tourism","help","fraud","health","care","community","volunteer","culture","ability");
    public void validate(JsonNode d){
        fields(d,Set.of("conversationId","messageId","taskId","baseTaskVersion","invocationId","intent","domains","control","reply","results","confirmationIds","tools","handoff","usedMemoryRefs"));
        for(String k:Set.of("conversationId","messageId","taskId","invocationId"))text(d.path(k),128);
        positive(d.path("baseTaskVersion"));if(!DOMAINS.contains(d.path("intent").asText()))bad();array(d.path("domains"),9);for(JsonNode domain:d.path("domains"))if(!domain.isTextual()||!DOMAINS.contains(domain.asText()))bad();
        JsonNode c=d.path("control");fields(c,Set.of("next","outcome","dependencyTaskIds","inputRequest"));String next=c.path("next").asText();if(!Set.of("COMPLETE","WAIT_INPUT","WAIT_CONFIRMATION","WAIT_DEPENDENCIES").contains(next))bad();
        if("COMPLETE".equals(next)){if(!Set.of("SUCCEEDED","PARTIALLY_SUCCEEDED","FAILED").contains(c.path("outcome").asText()))bad();}else if(!c.path("outcome").isNull())bad();
        array(c.path("dependencyTaskIds"),6);for(JsonNode id:c.path("dependencyTaskIds"))text(id,128);if("WAIT_DEPENDENCIES".equals(next)&&c.path("dependencyTaskIds").isEmpty())bad();
        if("WAIT_INPUT".equals(next)){if(!c.path("inputRequest").isObject())bad();}else if(!c.path("inputRequest").isNull())bad();
        JsonNode reply=d.path("reply");fields(reply,Set.of("text","speechRate","audioUrl"));text(reply.path("text"),4000);if(!reply.path("speechRate").isNumber()||!reply.path("audioUrl").isNull())bad();
        array(d.path("confirmationIds"),20);for(JsonNode id:d.path("confirmationIds"))text(id,128);
        array(d.path("tools"),40);for(JsonNode tool:d.path("tools")){fields(tool,Set.of("tool","args","result"));text(tool.path("tool"),128);if(!tool.path("args").isObject())bad();}
        array(d.path("usedMemoryRefs"),20);for(JsonNode ref:d.path("usedMemoryRefs")){fields(ref,Set.of("memoryId","version"));text(ref.path("memoryId"),128);positive(ref.path("version"));}
        if(!d.path("handoff").isNull()){JsonNode h=d.path("handoff");fields(h,Set.of("type","to","reason"));if(!"human_handoff".equals(h.path("type").asText())||!Set.of("family","scenic","official").contains(h.path("to").asText()))bad();text(h.path("reason"),4000);}
        array(d.path("results"),20);for(JsonNode result:d.path("results")){fields(result,Set.of("resultId","type","schemaVersion","title","businessRef","availability","generatedAt","sources","pendingChecks","payload"));text(result.path("resultId"),128);text(result.path("type"),128);text(result.path("title"),4000);if(!"1.0".equals(result.path("schemaVersion").asText())||!Set.of("REAL","DEMO","UNAVAILABLE","NEEDS_VERIFICATION").contains(result.path("availability").asText())||!result.path("payload").isObject())bad();try{Instant.parse(result.path("generatedAt").asText());}catch(Exception invalid){bad();}array(result.path("sources"),20);for(JsonNode source:result.path("sources"))if(!source.isObject())bad();array(result.path("pendingChecks"),20);for(JsonNode check:result.path("pendingChecks"))text(check,4000);if(!result.path("businessRef").isNull())bad();}
    }
    private void fields(JsonNode node,Set<String> expected){if(!node.isObject()||node.size()!=expected.size())bad();for(String field:expected)if(!node.has(field))bad();}
    private void text(JsonNode value,int max){if(!value.isTextual()||value.asText().length()>max||!AgentTextSafety.valid(value.asText()))bad();}
    private void array(JsonNode value,int max){if(!value.isArray()||value.size()>max)bad();}
    private void positive(JsonNode value){if(!value.isIntegralNumber()||!value.canConvertToLong()||value.asLong()<1)bad();}
    private void bad(){throw new IllegalArgumentException("Agent v3 response structure rejected");}
}
