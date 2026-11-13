package cn.silvertravel.platform.agent;

import static org.assertj.core.api.Assertions.*;

import cn.silvertravel.platform.agent.AgentProtocol.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import org.junit.jupiter.api.Test;

class AgentProtocolV2Test {
    private final ObjectMapper json = new ObjectMapper();

    @Test
    void wireOnlyContainsNestedInputAndNeverExposesTraceInBody() throws Exception {
        var wire =
                json.valueToTree(
                        new WireMessage("u100", "你好", Intent.tourism, null, "token", "trace"));
        assertThat(wire.path("input").path("text").asText()).isEqualTo("你好");
        assertThat(wire.has("text")).isFalse();
        assertThat(wire.has("traceId")).isFalse();
        assertThat(wire.path("protocolVersion").asText()).isEqualTo("3.0");
        var tool =
                json.valueToTree(
                        new ToolRequest(
                                "knowledge.search", json.createObjectNode().put("query", "厕所")));
        assertThat(tool.has("tool")).isFalse();
        assertThat(tool.has("args")).isFalse();
        assertThat(tool.path("input").path("tool").asText()).isEqualTo("knowledge.search");
    }

    @Test
    void replySerializesOnlyNestedContentAndOldReplyHasNoValidContent() throws Exception {
        var reply = json.valueToTree(new Reply(Intent.tourism, "你好", 0.8, null, List.of(), null));
        assertThat(reply.path("reply").path("text").asText()).isEqualTo("你好");
        for (String field : List.of("text", "audioUrl", "speechRate"))
            assertThat(reply.has(field)).isFalse();
        var old =
                json.readValue(
                        """
            {"intent":"tourism","text":"旧回复","speechRate":0.8,"audioUrl":null,"tools":[],"handoff":null}
            """,
                        Reply.class);
        assertThat(old.reply()).isNull();
    }
}
