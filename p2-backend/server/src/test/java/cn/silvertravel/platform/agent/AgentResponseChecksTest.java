package cn.silvertravel.platform.agent;
import static org.junit.jupiter.api.Assertions.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
class AgentResponseChecksTest {
    private final AgentResponseChecks checks=new AgentResponseChecks();
    private ObjectNode valid(){ObjectMapper json=new ObjectMapper();ObjectNode d=json.createObjectNode();d.put("conversationId","conversation").put("messageId","message").put("taskId","task").put("baseTaskVersion",2).put("invocationId","invocation").put("intent","tourism").putNull("handoff");d.putArray("domains").add("tourism");var c=d.putObject("control");c.put("next","COMPLETE").put("outcome","SUCCEEDED").putNull("inputRequest");c.putArray("dependencyTaskIds");d.putObject("reply").put("text","已完成演示查询").put("speechRate",0.8).putNull("audioUrl");for(String name:new String[]{"results","confirmationIds","tools","usedMemoryRefs"})d.putArray(name);return d;}
    @Test void acceptsComplete(){assertDoesNotThrow(()->checks.validate(valid()));}
    @Test void rejectsMissingAndUnknownFields(){var missing=valid();missing.remove("usedMemoryRefs");assertThrows(IllegalArgumentException.class,()->checks.validate(missing));var extra=valid();extra.put("confirmed",true);assertThrows(IllegalArgumentException.class,()->checks.validate(extra));}
    @Test void rejectsCoercedVersion(){var d=valid();d.put("baseTaskVersion","2");assertThrows(IllegalArgumentException.class,()->checks.validate(d));}
    @Test void rejectsContradictoryControl(){var d=valid();d.withObject("control").put("next","WAIT_INPUT");assertThrows(IllegalArgumentException.class,()->checks.validate(d));}
    @Test void rejectsUnboundedDomains(){var d=valid();d.withArray("domains").add("admin");assertThrows(IllegalArgumentException.class,()->checks.validate(d));}
}
