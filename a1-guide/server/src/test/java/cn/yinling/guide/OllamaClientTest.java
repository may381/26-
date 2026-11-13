package cn.yinling.guide;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class OllamaClientTest {
    @Test void schoolProtocolAndTruncation() throws Exception {
        var builder=RestClient.builder().baseUrl("http://10.138.50.151:8000");
        var mock=MockRestServiceServer.bindTo(builder).build();
        var school=new OllamaClient(builder.build(),new ObjectMapper(),true,"qwen3.8-27b","30m");
        org.springframework.test.util.ReflectionTestUtils.setField(school,"provider","school");
        String content=new ObjectMapper().writeValueAsString(Map.of("choices",java.util.List.of(Map.of("finish_reason","stop","message",Map.of("content","{\"answer\":\"您好\"}")))));
        mock.expect(requestTo("http://10.138.50.151:8000/v1/chat/completions"))
            .andExpect(jsonPath("$.model").value("qwen3.8-27b"))
            .andExpect(jsonPath("$.chat_template_kwargs.enable_thinking").value(false))
            .andExpect(jsonPath("$.options").doesNotExist())
            .andRespond(withSuccess(content,MediaType.APPLICATION_JSON));
        mock.expect(anything()).andRespond(withSuccess("{\"choices\":[{\"finish_reason\":\"length\"}]}",MediaType.APPLICATION_JSON));
        assertEquals("您好",school.chat("你好",java.util.List.of()));
        assertThrows(OllamaClient.Unavailable.class,()->school.chat("你好",java.util.List.of()));
        mock.verify();
    }
    MockRestServiceServer server;
    OllamaClient client;
    ObjectMapper mapper = new ObjectMapper();
    @BeforeEach void setup() {
        var builder=RestClient.builder().baseUrl("http://localhost:11434");
        server=MockRestServiceServer.bindTo(builder).build();
        client=new OllamaClient(builder.build(),mapper,true,"qwen3.5:4b","30m");
    }
    @Test void sendsGroundedPromptAndExtractsAnswer() throws Exception {
        String response=mapper.writeValueAsString(Map.of("done",true,"message",Map.of("content","{\"answer\":\"可以在池边长椅歇一歇。\"}")));
        server.expect(requestTo("http://localhost:11434/api/chat"))
            .andExpect(jsonPath("$.model").value("qwen3.5:4b"))
            .andExpect(jsonPath("$.stream").value(false))
            .andExpect(jsonPath("$.think").value(false))
            .andExpect(jsonPath("$.messages[1].content").value(org.hamcrest.Matchers.containsString("MOCK")))
            .andRespond(withSuccess(response,MediaType.APPLICATION_JSON));
        assertEquals("可以在池边长椅歇一歇。",client.generate("休息",Map.of("source","MOCK"),"池边长椅"));
        server.verify();
    }
    @Test void extractsStructuredGuideWithoutNestedAnswerWrapper() throws Exception {
        String extracted="{\"destination\":\"阳江\",\"places\":[\"海陵岛\"]}";
        server.expect(requestTo("http://localhost:11434/api/chat"))
            .andExpect(jsonPath("$.options.temperature").value(0))
            .andRespond(withSuccess(mapper.writeValueAsString(Map.of("done",true,"message",Map.of("content",extracted))),MediaType.APPLICATION_JSON));
        assertEquals(extracted,client.extractTravel("阳江海陵岛旅游攻略"));server.verify();
    }
    @Test void upstreamErrorIsNotPresentedAsGeneratedAnswer() {
        server.expect(anything()).andRespond(withStatus(HttpStatus.NOT_FOUND));
        assertThrows(OllamaClient.Unavailable.class,()->client.generate("故事",Map.of(),"演示资料"));
    }
    @Test void malformedAndTruncatedOutputsRejected() {
        server.expect(anything()).andRespond(withSuccess("{\"done\":true,\"message\":{\"content\":\"bad json\"}}",MediaType.APPLICATION_JSON));
        server.expect(anything()).andRespond(withSuccess("{\"done\":true,\"done_reason\":\"length\"}",MediaType.APPLICATION_JSON));
        assertThrows(OllamaClient.Unavailable.class,()->client.generate("故事",Map.of(),"演示资料"));
        assertThrows(OllamaClient.Unavailable.class,()->client.generate("故事",Map.of(),"演示资料"));
    }
    @Test void warmupPreloadsModelWithConfiguredKeepAlive() {
        server.expect(requestTo("http://localhost:11434/api/chat"))
            .andExpect(jsonPath("$.model").value("qwen3.5:4b"))
            .andExpect(jsonPath("$.keep_alive").value("30m"))
            .andExpect(jsonPath("$.options.num_predict").value(1))
            .andRespond(withSuccess("{\"done\":true,\"message\":{\"content\":\"你好\"}}",MediaType.APPLICATION_JSON));
        client.warmup();
        server.verify();
    }
    @Test void disabledClientNeverWarmsUp() {
        // No expectation registered: any request would fail the strict mock server.
        var builder=RestClient.builder().baseUrl("http://localhost:11434");
        MockRestServiceServer.bindTo(builder).build();
        var off=new OllamaClient(builder.build(),mapper,false,"qwen3.5:4b","30m");
        assertDoesNotThrow(off::warmupOnStartup);
    }
    @Test void remoteModelAddressRejected() {
        assertThrows(IllegalArgumentException.class,()->new OllamaConfig().ollamaRestClient("https://example.com",90));
    }
    @Test void detailedStyleChangesInstructionsButKeepsGroundingRules() throws Exception {
        String response=mapper.writeValueAsString(Map.of("done",true,"message",Map.of("content","{\"answer\":\"资料有限，可以看看亭边风景。\"}")));
        server.expect(anything()).andExpect(jsonPath("$.messages[0].content").value(org.hamcrest.Matchers.containsString("详细讲解")))
            .andExpect(jsonPath("$.messages[0].content").value(org.hamcrest.Matchers.containsString("不得声称已经通知")))
            .andRespond(withSuccess(response,MediaType.APPLICATION_JSON));
        assertFalse(client.generate("详细讲讲",Map.of("source","MOCK"),"清风亭","DETAILED").isBlank());
    }
    @Test void chatSendsRecentConversationWithoutInventedUserProfile() throws Exception {
        String response=mapper.writeValueAsString(Map.of("done",true,"message",Map.of("content","{\"answer\":\"还不知道怎么称呼您呢。\"}")));
        server.expect(anything()).andExpect(jsonPath("$.messages[0].content").value(org.hamcrest.Matchers.containsString("没有读取个人档案")))
            .andExpect(jsonPath("$.messages[1].content").value(org.hamcrest.Matchers.containsString("recentConversation")))
            .andExpect(jsonPath("$.messages[1].content").value(org.hamcrest.Matchers.containsString("我叫王阿姨")))
            .andRespond(withSuccess(response,MediaType.APPLICATION_JSON));
        assertEquals("您刚才告诉我，叫您王阿姨就好。我记着呢。",client.chat("我是谁",java.util.List.of(new ConversationBook.ChatLine("user","我叫王阿姨"))));
    }
    @Test void nicknameOnlyComesFromExplicitUserIntroduction() {
        assertEquals("",OllamaClient.selfIntroducedName(java.util.List.of(new ConversationBook.ChatLine("assistant","我叫王阿姨"))));
        assertEquals("李阿姨",OllamaClient.selfIntroducedName(java.util.List.of(new ConversationBook.ChatLine("user","我叫王阿姨"),new ConversationBook.ChatLine("user","我不叫王阿姨，我叫李阿姨"))));
        assertEquals("",OllamaClient.selfIntroducedName(java.util.List.of(new ConversationBook.ChatLine("user","我叫王阿姨"),new ConversationBook.ChatLine("user","我不叫王阿姨"))));
    }
}
