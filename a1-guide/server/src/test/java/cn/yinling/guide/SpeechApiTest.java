package cn.yinling.guide;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import org.springframework.mock.web.MockMultipartFile;
@SpringBootTest
@AutoConfigureMockMvc
class SpeechApiTest {
 @Autowired MockMvc mvc;
 @Test void invalidRateRejected()throws Exception{mvc.perform(post("/api/speech/syntheses").contentType("application/json").content("{\"text\":\"hello\",\"speechRate\":8}")).andExpect(status().isBadRequest());}
 @Test void expiredOrUnknownClipIsNotFound()throws Exception{mvc.perform(get("/api/speech/audio/unknown")).andExpect(status().isNotFound());}
 @Test void emptyTextRejected()throws Exception{mvc.perform(post("/api/speech/syntheses").contentType("application/json").content("{\"text\":\"\",\"speechRate\":0.8}")).andExpect(status().isBadRequest());}
 @Test void malformedHintsAreRejectedBeforeDecoding()throws Exception{mvc.perform(multipart("/api/speech/transcriptions").file(new MockMultipartFile("file","clip.wav","audio/wav",new byte[]{1,2})).param("hints","not json")).andExpect(status().isBadRequest());}
 @Test void excessiveHintsAreRejectedBeforeDecoding()throws Exception{mvc.perform(multipart("/api/speech/transcriptions").file(new MockMultipartFile("file","clip.wav","audio/wav",new byte[]{1,2})).param("hints","["+"\"地点\",".repeat(12)+"\"地点\"]")).andExpect(status().isBadRequest());}
 @Test void unknownVoiceIsRejectedBeforeSynthesis()throws Exception{mvc.perform(post("/api/speech/syntheses").contentType("application/json").content("{\"text\":\"你好\",\"speechRate\":1,\"voice\":\"unknown\"}")).andExpect(status().isBadRequest());}
 @Test void voiceCatalogAlwaysProvidesAnAvailableDefault()throws Exception{mvc.perform(get("/api/speech/voices")).andExpect(status().isOk()).andExpect(jsonPath("$.data.defaultVoice").isNotEmpty()).andExpect(jsonPath("$.data.voices[0].id").isNotEmpty());}
}
