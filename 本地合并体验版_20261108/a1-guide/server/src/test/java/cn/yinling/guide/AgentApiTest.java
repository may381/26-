package cn.yinling.guide;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import java.util.Map;
import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(properties = "ai.ollama.enabled=false")
@AutoConfigureMockMvc
class AgentApiTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired ScenicDataProvider provider;
    private org.springframework.test.web.servlet.ResultActions ask(String text, String location) throws Exception {
        return mvc.perform(post("/api/agent/messages").contentType("application/json")
            .content(mapper.writeValueAsString(Map.of("userId","u100","text",text,"context",Map.of("location",location)))));
    }
    @Test void narrationIsGroundedAndAudioIsNull() throws Exception {
        ask("讲讲这里的故事", "spot-002").andExpect(status().isOk()).andExpect(jsonPath("$.code").value("OK"))
            .andExpect(jsonPath("$.data.text",containsString("演示讲解")))
            .andExpect(jsonPath("$.data.speechRate").value(.8)).andExpect(jsonPath("$.data.audioUrl").value(nullValue()))
            .andExpect(jsonPath("$.data.tools[0].result.source").value("MOCK"))
            .andExpect(jsonPath("$.data.tools[0].result.records[0].id").value("spot-002"));
    }
    @Test void facilitiesDoNotInventDistances() throws Exception {
        ask("厕所在哪", "spot-003").andExpect(jsonPath("$.data.text",containsString("荷香池卫生间")))
            .andExpect(jsonPath("$.data.text",not(containsString("50米"))));
    }
    @Test void unknownLocationAsksInsteadOfGuessing() throws Exception {
        ask("哪里能休息", "missing").andExpect(jsonPath("$.data.text",containsString("还不知道您的位置")))
            .andExpect(jsonPath("$.data.tools",hasSize(0)));
    }
    @Test void fatigueDoesNotClaimRouteMutation() throws Exception {
        ask("累了", "spot-003").andExpect(jsonPath("$.data.text",not(containsString("已为您缩短路线"))))
            .andExpect(jsonPath("$.data.tools[0].tool").value("knowledge.search"));
    }
    @Test void openingHoursAreNotLive() throws Exception {
        ask("几点关门", "").andExpect(jsonPath("$.data.text",containsString("不是实时营业状态")));
    }
    @Test void helpOverridesHintAndDoesNotSendNotifications() throws Exception {
        mvc.perform(post("/api/agent/messages").contentType("application/json").content("""
            {"userId":"u100","text":"求助，联系家属","intent":"tourism"}
            """)).andExpect(jsonPath("$.data.intent").value("help"))
            .andExpect(jsonPath("$.data.handoff.to").value("family"))
            .andExpect(jsonPath("$.data.text",containsString("没有通知")))
            .andExpect(jsonPath("$.data.tools",hasSize(0)));
    }
    @Test void routeQuestionReturnsFactsWithoutChangingRoute() throws Exception {
        ask("哪条路线省力", "").andExpect(status().isOk()).andExpect(jsonPath("$.code").value("OK"))
            .andExpect(jsonPath("$.data.tools[0].tool").value("route.recommend"))
            .andExpect(jsonPath("$.data.tools[0].result.source").value("MOCK"))
            .andExpect(jsonPath("$.data.tools[0].result.routes",hasSize(3)))
            .andExpect(jsonPath("$.data.text",containsString("省力线约 20 级台阶")))
            .andExpect(jsonPath("$.data.text",containsString("当前没有更改您的路线")))
            .andExpect(jsonPath("$.data.text",not(containsString("已为您缩短路线"))))
            .andExpect(jsonPath("$.data.audioUrl").value(nullValue()));
    }
    @Test void routeAnswerDoesNotNeedModel() throws Exception {
        mvc.perform(post("/api/agent/messages").contentType("application/json")
            .content("{\"userId\":\"u100\",\"text\":\"有几条路线\"}"))
            .andExpect(jsonPath("$.data.tools[0].tool").value("route.recommend"))
            .andExpect(jsonPath("$.data.text",containsString("演示路线共 3 条")));
    }
    @Test void unavailableAgentIsHonest() throws Exception {
        ask("想学剪纸", "").andExpect(jsonPath("$.data.intent").value("culture"))
            .andExpect(jsonPath("$.data.text",containsString("暂未开放")));
    }
    @Test void blankAndOversizedInputsRejected() throws Exception {
        ask(" ", "").andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_ARGUMENT"));
        ask("字".repeat(2001), "").andExpect(status().isBadRequest());
    }
    @Test void malformedOrUnsupportedInputRejected() throws Exception {
        mvc.perform(post("/api/agent/messages").contentType("application/json").content("{"))
            .andExpect(status().isBadRequest()).andExpect(jsonPath("$.data").value(nullValue()));
        mvc.perform(post("/api/agent/messages").contentType("application/json")
            .content("{\"userId\":\"u100\",\"text\":\"你好\",\"intent\":\"wrong\"}"))
            .andExpect(status().isBadRequest());
    }
    @Test void realProviderCannotSilentlyUseMock() {
        assertThrows(IllegalStateException.class, () -> new MockScenicProvider(mapper, "real"));
    }
    @Test void fixtureShapeAndMetadata() throws Exception {
        try(var stream=getClass().getResourceAsStream("/fixtures/qingfeng.json")) {
            var data=mapper.readTree(stream);
            assertEquals(6,data.get("spots").size());assertEquals(10,data.get("facilities").size());assertEquals(3,data.get("routes").size());
            for(String key:new String[]{"spots","facilities","routes"}) for(var row:data.get(key)) {
                assertEquals("MOCK",row.path("source").asText());assertFalse(row.path("updatedAt").asText().isBlank());
            }
            // Each spot carries a real narration, not a one-line placeholder.
            for(var spot:data.get("spots")) assertTrue(spot.path("narration").asText().length()>=30,
                spot.path("name").asText()+" narration is too short to demonstrate a guide answer");
        }
    }
    @Test void testPageServed() throws Exception {mvc.perform(get("/index.html")).andExpect(status().isOk()).andExpect(content().string(containsString("问问导游")));}
}
