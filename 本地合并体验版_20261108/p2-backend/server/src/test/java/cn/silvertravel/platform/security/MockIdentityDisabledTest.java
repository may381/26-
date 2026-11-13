package cn.silvertravel.platform.security;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("bootstrap")
class MockIdentityDisabledTest {
    @Autowired MockMvc mvc;

    @Test
    void knownMockHeadersCannotAuthenticateWhenDisabled() throws Exception {
        mvc.perform(
                        get("/api/not-implemented")
                                .header("X-Mock-Actor-Id", "admin-operator-001")
                                .header("X-Mock-Actor-Role", "ADMIN"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("UNAUTHORIZED"));
    }
}
