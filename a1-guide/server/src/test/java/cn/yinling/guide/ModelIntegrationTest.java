package cn.yinling.guide;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.mock.web.MockHttpSession;
import org.mockito.ArgumentCaptor;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.hamcrest.Matchers.containsString;

@SpringBootTest
@AutoConfigureMockMvc
class ModelIntegrationTest {
    @Test void capabilityIntroductionDoesNotBecomeMockScenicNarration() throws Exception {
        mvc.perform(post("/api/agent/messages").contentType("application/json")
            .content("{\"userId\":\"u100\",\"text\":\"你好，请介绍一下你能帮我做什么\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.text",containsString("出游草案")))
            .andExpect(jsonPath("$.data.text",org.hamcrest.Matchers.not(containsString("清风园"))));
        verifyNoInteractions(model);
    }
    @Autowired MockMvc mvc;
    @MockBean OllamaClient model;
    @Test void retainsEvidenceAndMandatoryOpeningStatusNotice() throws Exception {
        when(model.enabled()).thenReturn(true);
        when(model.generate(anyString(),any(),anyString(),anyString())).thenReturn("可以先看看演示开放时间。");
        mvc.perform(post("/api/agent/messages").contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"几点关门\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data.text",containsString("本地 AI")))
            .andExpect(jsonPath("$.data.text",containsString("不是实时营业状态")))
            .andExpect(jsonPath("$.data.tools[0].result.source").value("MOCK"));
    }
    @Test void modelFailureReturns502() throws Exception {
        when(model.enabled()).thenReturn(true);
        when(model.generate(anyString(),any(),anyString(),anyString())).thenThrow(new OllamaClient.Unavailable("模型不可用"));
        mvc.perform(post("/api/agent/messages").contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"几点关门\"}"))
            .andExpect(status().isBadGateway()).andExpect(jsonPath("$.code").value("UPSTREAM_ERROR"));
    }
    @Test void helpNeverWaitsForModel() throws Exception {
        mvc.perform(post("/api/agent/messages").contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"求助\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data.intent").value("help"));
        verify(model,never()).generate(anyString(),any(),anyString(),anyString());
    }
    @Test void detailedAndBriefFollowupsReachModelWithoutChangingSpot() throws Exception {
        when(model.enabled()).thenReturn(true);
        when(model.generate(anyString(),any(),anyString(),anyString())).thenReturn("根据资料回答。");
        var s=new MockHttpSession();
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"介绍清风亭\"}"));
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"详细讲讲\"}"))
            .andExpect(jsonPath("$.data.tools[0].result.records[0].id").value("spot-002"));
        verify(model).generate(contains("详细讲讲"),any(),anyString(),eq("DETAILED"));
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"简单点\"}"));
        verify(model).generate(contains("简单点"),any(),anyString(),eq("BRIEF"));
    }
    @Test void failedModelTurnDoesNotRememberUnansweredPlace() throws Exception {
        when(model.enabled()).thenReturn(true);
        when(model.generate(anyString(),any(),anyString(),anyString())).thenThrow(new OllamaClient.Unavailable("模型不可用"));
        var s=new MockHttpSession();
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"介绍清风亭\"}"))
            .andExpect(status().isBadGateway());
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"那里能坐吗\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data.text",containsString("还不知道您的位置")));
    }
    @Test void identityQuestionReachesModelAndReceivesShortHistory() throws Exception {
        when(model.enabled()).thenReturn(true);
        when(model.chat(anyString(),anyList())).thenReturn("您好，您希望我怎么称呼您？");
        var s=new MockHttpSession();
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"我叫王阿姨\"}"))
            .andExpect(status().isOk());
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"你好，你知道我是谁吗\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data.text",org.hamcrest.Matchers.not(containsString("没有可靠资料支持"))));
        @SuppressWarnings("unchecked") ArgumentCaptor<List<ConversationBook.ChatLine>> history=ArgumentCaptor.forClass(List.class);
        verify(model).chat(eq("你好，你知道我是谁吗"),history.capture());
        assertTrue(history.getValue().stream().anyMatch(m->m.role().equals("user") && m.content().equals("我叫王阿姨")));
    }
    @Test void shortHistoryDoesNotLeakToDifferentUserOrSurviveReset() throws Exception {
        when(model.enabled()).thenReturn(true);
        when(model.chat(anyString(),anyList())).thenReturn("您好。");
        var s=new MockHttpSession();
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u1\",\"text\":\"我叫王阿姨\"}"));
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u2\",\"text\":\"我是谁\"}"));
        verify(model).chat(eq("我是谁"),argThat(List::isEmpty));
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u1\",\"text\":\"重新开始对话\"}"));
        mvc.perform(post("/api/agent/messages").session(s).contentType("application/json").content("{\"userId\":\"u1\",\"text\":\"你记得我叫什么吗\"}"));
        verify(model).chat(eq("你记得我叫什么吗"),argThat(List::isEmpty));
    }
    @Test void generatedLabelsAndRepeatedTechnicalNoticesAreRemoved() throws Exception {
        when(model.enabled()).thenReturn(true);
        when(model.generate(anyString(),any(),anyString(),anyString())).thenReturn("【清风园演示数据】荷香池边有长椅。未接入实时定位，不提供距离或导航承诺。当前没有更改您的路线。");
        var result=mvc.perform(post("/api/agent/messages").contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"哪里能休息\",\"context\":{\"location\":\"spot-003\"}}"))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        assertFalse(result.contains("未接入实时定位"));
        assertFalse(result.contains("当前没有更改您的路线"));
        assertFalse(result.contains("【清风园演示数据】"));
        assertTrue(result.contains("荷香池边有长椅"));
    }
}
