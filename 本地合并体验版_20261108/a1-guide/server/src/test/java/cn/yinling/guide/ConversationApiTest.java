package cn.yinling.guide;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import java.util.Map;
import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties="ai.ollama.enabled=false")
@AutoConfigureMockMvc
class ConversationApiTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    ResultActions ask(MockHttpSession session,String user,String trip,String location,String text) throws Exception {
        return mvc.perform(post("/api/agent/messages").session(session).contentType("application/json")
            .content(mapper.writeValueAsString(new AgentApi.Message(user,text,null,new AgentApi.Context(trip,location)))));
    }
    @Test void colloquialFatigueThenPlaceCompletesRestQuestion() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1",null,null,"我腿走酸了").andExpect(jsonPath("$.data.text",containsString("想找休息处")));
        ask(s,"u1",null,null,"荷香池").andExpect(jsonPath("$.data.text",containsString("池边长椅")))
            .andExpect(jsonPath("$.data.tools[0].result.records[0].type").value("rest"));
    }
    @Test void colloquialToiletQuestionCompletesAfterPlaceOnlyReply() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1",null,null,"我想方便一下");
        ask(s,"u1",null,null,"游客中心").andExpect(jsonPath("$.data.text",containsString("游客中心卫生间")));
    }
    @Test void thereRefersToDiscussedPlaceAndHereToProvidedLocation() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1","t1","spot-003","介绍一下清风亭");
        ask(s,"u1","t1","spot-003","那里能坐吗").andExpect(jsonPath("$.data.text",containsString("亭内座椅")));
        ask(s,"u1","t1","spot-003","这里能坐吗").andExpect(jsonPath("$.data.text",containsString("池边长椅")));
    }
    @Test void usersInSameBrowserDoNotShareContext() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1",null,null,"介绍清风亭");
        ask(s,"u2",null,null,"那里能坐吗").andExpect(jsonPath("$.data.text",containsString("还不知道您的位置")));
    }
    @Test void browsersDoNotShareContextEvenForSameMockUser() throws Exception {
        ask(new MockHttpSession(),"u1",null,null,"介绍清风亭");
        ask(new MockHttpSession(),"u1",null,null,"那里能坐吗").andExpect(jsonPath("$.data.text",containsString("还不知道您的位置")));
    }
    @Test void tripsDoNotShareContext() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1","t1",null,"介绍清风亭");
        ask(s,"u1","t2",null,"那里能坐吗").andExpect(jsonPath("$.data.text",containsString("还不知道您的位置")));
    }
    @Test void changedUnknownLocationDoesNotReuseOldPlace() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1",null,"spot-002","介绍这里的故事");
        ask(s,"u1",null,"invalid","那里能坐吗").andExpect(jsonPath("$.data.tools",hasSize(0)));
    }
    @Test void explicitlyRemovingProvidedLocationClearsOldPlace() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1",null,"spot-002","介绍这里的故事");
        ask(s,"u1",null,null,"那里能坐吗").andExpect(jsonPath("$.data.text",containsString("还不知道您的位置")));
    }
    @Test void clearResetsPendingQuestionAndRate() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1",null,null,"说慢一点").andExpect(jsonPath("$.data.speechRate").value(.65));
        ask(s,"u1",null,null,"我想方便一下");
        ask(s,"u1",null,null,"重新开始对话").andExpect(jsonPath("$.data.speechRate").value(.8));
        ask(s,"u1",null,null,"荷香池").andExpect(jsonPath("$.data.tools[0].result.records[0].id").value("spot-003"))
            .andExpect(jsonPath("$.data.text",containsString("演示讲解")));
    }
    @Test void topicSwitchCancelsOldPendingQuestion() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1",null,null,"找厕所");
        ask(s,"u1",null,null,"讲个故事");
        ask(s,"u1",null,null,"荷香池").andExpect(jsonPath("$.data.text",containsString("演示讲解")));
    }
    @Test void negatedRestAndHelpDoNotTriggerActions() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1",null,"spot-003","我不累，不想休息").andExpect(jsonPath("$.data.tools",hasSize(0)));
        ask(s,"u1",null,null,"我没有迷路，不需要求助").andExpect(jsonPath("$.data.handoff").value(nullValue()));
    }
    @Test void multiplePlacesRequireDisambiguationAndKeepQuestion() throws Exception {
        var s=new MockHttpSession();
        ask(s,"u1",null,null,"清风亭和荷香池哪里能坐").andExpect(jsonPath("$.data.text",containsString("多个景点")));
        ask(s,"u1",null,null,"清风亭").andExpect(jsonPath("$.data.text",containsString("亭内座椅")));
    }
    @Test void noFacilityRecordDoesNotClaimItDoesNotExist() throws Exception {
        ask(new MockHttpSession(),"u1",null,"spot-002","厕所在哪")
            .andExpect(jsonPath("$.data.text",containsString("不能据此判断现实中没有设施")));
    }
}
