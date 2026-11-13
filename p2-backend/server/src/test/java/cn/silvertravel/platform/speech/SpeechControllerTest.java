package cn.silvertravel.platform.speech;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import cn.silvertravel.platform.common.api.ContractJsonConfiguration;
import cn.silvertravel.platform.security.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(
        controllers = SpeechController.class,
        excludeAutoConfiguration =
                org.springframework.boot.autoconfigure.security.servlet
                        .UserDetailsServiceAutoConfiguration.class,
        properties = {"app.security.mock-enabled=true", "speech.mode=mock"})
@ActiveProfiles("mock")
@Import({
    SpeechConfiguration.class,
    SecurityConfiguration.class,
    SecurityResponseWriter.class,
    BusinessAccessPolicy.class,
    ContractJsonConfiguration.class
})
class SpeechControllerTest {
    @Autowired MockMvc mvc;

    @Test
    void mockTranscriptionExplicitlyDoesNotClaimRecognition() throws Exception {
        byte[] wav =
                "RIFF0000WAVEsynthetic-test-only"
                        .getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        mvc.perform(
                        multipart("/api/v3/speech/transcriptions")
                                .file(new MockMultipartFile("audio", "demo.wav", "audio/wav", wav))
                                .header("X-Mock-Actor-Id", "u100")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.text").value("【演示转写，未识别音频内容】厕所在哪"))
                .andExpect(jsonPath("$.message").value("语音演示占位：未识别或生成真实音频"));
    }

    @Test
    void rejectsEmptyUnsupportedMissingAndCrossUserAudio() throws Exception {
        for (byte[] bytes :
                new byte[][] {
                    new byte[0], "not-an-audio-file".getBytes(), new byte[10 * 1024 * 1024 + 1]
                }) {
            mvc.perform(
                            multipart("/api/v3/speech/transcriptions")
                                    .file(
                                            new MockMultipartFile(
                                                    "audio", "demo.wav", "audio/wav", bytes))
                                    .header("X-Mock-Actor-Id", "u100")
                                    .header("X-Mock-Actor-Role", "ELDER"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.code").value("INVALID_ARGUMENT"));
        }
        mvc.perform(
                        multipart("/api/v3/speech/transcriptions")
                                .header("X-Mock-Actor-Id", "u100")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isBadRequest());
        mvc.perform(
                        multipart("/api/v3/speech/transcriptions")
                                .file(new MockMultipartFile("audio", new byte[0]))
                                .param("userId", "u101")
                                .header("X-Mock-Actor-Id", "u100")
                                .header("X-Mock-Actor-Role", "ELDER"))
                .andExpect(status().isForbidden());
    }

    @Test
    void synthesisRequiresOwnerAndContractValues() throws Exception {
        mvc.perform(
                        post("/api/v3/speech/syntheses")
                                .contentType("application/json")
                                .content("{\"text\":\"你好\",\"speechRate\":0.8}"))
                .andExpect(status().isUnauthorized());
        mvc.perform(
                        post("/api/v3/speech/syntheses")
                                .contentType("application/json")
                                .header("X-Mock-Actor-Id", "u100")
                                .header("X-Mock-Actor-Role", "ELDER")
                                .content("{\"text\":\"你好\",\"speechRate\":0.8}"))
                .andExpect(status().isOk())
                .andExpect(
                        content()
                                .json(
                                        "{\"code\":\"OK\",\"message\":\"语音演示占位：未识别或生成真实音频\",\"data\":{\"audioUrl\":null}}"));
        for (String body :
                new String[] {
                    "{\"text\":\"你好\"}",
                    "{\"text\":\" \",\"speechRate\":1}",
                    "{\"text\":\"你好\",\"speechRate\":2}",
                    "{\"text\":\"你好\",\"speechRate\":1,\"userId\":\"u101\"}"
                }) {
            mvc.perform(
                            post("/api/v3/speech/syntheses")
                                    .contentType("application/json")
                                    .header("X-Mock-Actor-Id", "u100")
                                    .header("X-Mock-Actor-Role", "ELDER")
                                    .content(body))
                    .andExpect(status().isBadRequest());
        }
        mvc.perform(
                        post("/api/v3/speech/syntheses")
                                .contentType("application/json")
                                .header("X-Mock-Actor-Id", "family-operator-001")
                                .header("X-Mock-Actor-Role", "FAMILY")
                                .content("{\"text\":\"你好\",\"speechRate\":1}"))
                .andExpect(status().isForbidden());
    }

    @Test
    void fileHeadersAreMatchedToMimeInsteadOfFilename() {
        assertThat(SpeechController.supported("RIFF0000WAVEfake".getBytes(), "audio/wav")).isTrue();
        assertThat(SpeechController.supported("RIFF0000WAVEfake".getBytes(), "audio/mpeg"))
                .isFalse();
        assertThat(SpeechController.supported(new byte[1], null)).isFalse();
    }
}
