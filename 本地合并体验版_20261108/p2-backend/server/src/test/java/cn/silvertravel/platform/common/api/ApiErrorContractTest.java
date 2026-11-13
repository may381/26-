package cn.silvertravel.platform.common.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = "app.security.mock-enabled=true")
@AutoConfigureMockMvc
@ActiveProfiles({"bootstrap", "mock"})
class ApiErrorContractTest {

    @Autowired private MockMvc mvc;

    @Test
    void missingResourceUsesContractEnvelope() throws Exception {
        mvc.perform(
                        get("/api/v3/not-implemented")
                                .header("X-Mock-Actor-Id", "u100")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"))
                .andExpect(jsonPath("$.message").value("资源不存在"))
                .andExpect(
                        content()
                                .json(
                                        "{\"code\":\"NOT_FOUND\",\"message\":\"资源不存在\",\"data\":null}",
                                        true));
    }
}
