package cn.silvertravel.platform.speech;

import cn.silvertravel.platform.common.api.BusinessException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Arrays;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;

@Configuration(proxyBeanMethods = false)
public class SpeechConfiguration {
    @Bean
    SpeechProvider speechProvider(
            @Value("${speech.mode:disabled}") String mode,
            @Value("${speech.service-url:http://127.0.0.1:18010}") String serviceUrl,
            Environment env,
            ObjectMapper json) {
        if (mode.equals("http")) return new HttpSpeechProvider(serviceUrl, json);
        boolean local =
                Arrays.stream(
                                env.getActiveProfiles().length == 0
                                        ? env.getDefaultProfiles()
                                        : env.getActiveProfiles())
                        .anyMatch(p -> p.equals("local") || p.equals("mock"));
        boolean prod =
                Arrays.stream(env.getActiveProfiles())
                        .anyMatch(p -> p.equals("prod") || p.equals("production"));
        if (!mode.equals("mock") && !mode.equals("disabled"))
            throw new IllegalStateException("Unsupported speech mode");
        if (mode.equals("mock") && (!local || prod))
            throw new IllegalStateException("Mock speech requires local/mock profile");
        return new SpeechProvider() {
            public String transcribe(byte[] audio, String contentType) {
                requireEnabled();
                return "【演示转写，未识别音频内容】厕所在哪";
            }

            public byte[] synthesize(String text, double rate) {
                requireEnabled();
                return null;
            }

            public boolean simulated() {
                return mode.equals("mock");
            }

            private void requireEnabled() {
                if (!simulated()) throw BusinessException.conflict("语音服务尚未配置");
            }
        };
    }
}
