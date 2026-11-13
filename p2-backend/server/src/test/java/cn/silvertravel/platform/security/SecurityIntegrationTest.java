package cn.silvertravel.platform.security;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import cn.silvertravel.platform.common.api.ApiResponse;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@SpringBootTest(properties = "app.security.mock-enabled=true")
@AutoConfigureMockMvc
@ActiveProfiles({"bootstrap", "mock"})
@Import(SecurityIntegrationTest.Endpoints.class)
class SecurityIntegrationTest {
    @Autowired MockMvc mvc;

    @Test
    void callerIsRequiredAndIdentityDoesNotLeakToNextRequest() throws Exception {
        mvc.perform(
                        get("/api/v3/__security-test/identity")
                                .header("X-Mock-Actor-Id", "u100")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value("u100"))
                .andExpect(cookie().doesNotExist("JSESSIONID"));
        mvc.perform(get("/api/v3/__security-test/identity").param("userId", "u100"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("UNAUTHORIZED"))
                .andExpect(jsonPath("$.success").doesNotExist());
    }

    @ParameterizedTest
    @CsvSource({"unknown,ELDER", "u100,ADMIN", "u100,elder", "u100,ELDER FAMILY"})
    void rejectsInvalidOrForgedIdentity(String id, String role) throws Exception {
        mvc.perform(
                        get("/api/v3/__security-test/identity")
                                .header("X-Mock-Actor-Id", id)
                                .header("X-Mock-Actor-Role", role))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("UNAUTHORIZED"));
    }

    @Test
    void contractHelpPathsApplyRoleGateBeforeBusinessHandlers() throws Exception {
        for (String action : new String[] {"acknowledge", "resolve"}) {
            mvc.perform(
                            post("/api/v3/help-events/example/" + action)
                                    .header("X-Mock-Actor-Id", "u100")
                                    .header("X-Mock-Actor-Role", "ELDER"))
                    .andExpect(status().isForbidden())
                    .andExpect(jsonPath("$.code").value("FORBIDDEN"));
            mvc.perform(
                            post("/api/v3/help-events/example/" + action)
                                    .header("X-Mock-Actor-Id", "scenic-operator-001")
                                    .header("X-Mock-Actor-Role", "SCENIC"))
                    .andExpect(status().isNotFound());
        }
    }

    @Test
    void rejectsPartialAndDuplicateHeaders() throws Exception {
        mvc.perform(get("/api/v3/__security-test/identity").header("X-Mock-Actor-Id", "u100"))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v3/__security-test/identity").header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isUnauthorized());
        mvc.perform(
                        get("/api/v3/__security-test/identity")
                                .header("X-Mock-Actor-Id", "u100", "admin-operator-001")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isUnauthorized());
    }

    @ParameterizedTest
    @CsvSource({
        "u100,ELDER,u100,200",
        "u100,ELDER,u101,403",
        "family-operator-001,FAMILY,u100,403",
        "admin-operator-001,ADMIN,u100,403"
    })
    void ownerPolicyDoesNotTreatUserIdAsAuthentication(
            String id, String role, String target, int status) throws Exception {
        mvc.perform(
                        get("/api/v3/__security-test/owner")
                                .param("userId", target)
                                .header("X-Mock-Actor-Id", id)
                                .header("X-Mock-Actor-Role", role))
                .andExpect(status().is(status));
    }

    @ParameterizedTest
    @CsvSource({
        "u100,ELDER,403",
        "family-operator-001,FAMILY,403",
        "scenic-operator-001,SCENIC,200",
        "official-operator-001,OFFICIAL,200",
        "admin-operator-001,ADMIN,200"
    })
    void onlyHandlerRolesCanAcknowledge(String id, String role, int status) throws Exception {
        mvc.perform(
                        post("/api/v3/__security-test/acknowledge")
                                .header("X-Mock-Actor-Id", id)
                                .header("X-Mock-Actor-Role", role))
                .andExpect(status().is(status));
    }

    @ParameterizedTest
    @CsvSource({
        "u100,ELDER,403",
        "family-operator-001,FAMILY,403",
        "scenic-operator-001,SCENIC,200",
        "scenic-operator-002,SCENIC,403",
        "official-operator-001,OFFICIAL,403",
        "admin-operator-001,ADMIN,200"
    })
    void onlyActualHandlerOrAdminCanResolve(String id, String role, int status) throws Exception {
        var response =
                mvc.perform(
                                post("/api/v3/__security-test/resolve")
                                        .header("X-Mock-Actor-Id", id)
                                        .header("X-Mock-Actor-Role", role))
                        .andExpect(status().is(status));
        if (status == 403) {
            response.andExpect(jsonPath("$.code").value("FORBIDDEN"));
        }
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class Endpoints {
        @Bean
        ProbeController probeController(BusinessAccessPolicy policy) {
            return new ProbeController(policy);
        }
    }

    // Test-only routes are not packaged in the application artifact.
    @RestController
    static class ProbeController {
        private final BusinessAccessPolicy policy;

        ProbeController(BusinessAccessPolicy policy) {
            this.policy = policy;
        }

        @GetMapping("/api/v3/__security-test/identity")
        ApiResponse<CurrentActor> identity() {
            return ApiResponse.ok(policy.currentActor());
        }

        @GetMapping("/api/v3/__security-test/owner")
        ApiResponse<String> owner(@RequestParam String userId) {
            return ApiResponse.ok(policy.requireElderOwner(userId).id());
        }

        @PostMapping("/api/v3/__security-test/acknowledge")
        ApiResponse<String> acknowledge() {
            return ApiResponse.ok(policy.requireHelpAcknowledge().id());
        }

        @PostMapping("/api/v3/__security-test/resolve")
        ApiResponse<String> resolve() {
            return ApiResponse.ok(policy.requireHelpResolve("scenic-operator-001").id());
        }
    }
}
