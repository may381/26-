package cn.silvertravel.platform.speech;

import cn.silvertravel.platform.common.api.BusinessException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
import java.util.Map;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

final class HttpSpeechProvider implements SpeechProvider {
    private static final int MAX_WAV_BYTES = 10 * 1024 * 1024;
    private final RestClient http;
    private final ObjectMapper json;

    HttpSpeechProvider(String serviceUrl, ObjectMapper json) {
        URI uri = URI.create(serviceUrl);
        if (!("http".equals(uri.getScheme()) || "https".equals(uri.getScheme()))
                || uri.getHost() == null
                || uri.getUserInfo() != null
                || uri.getQuery() != null
                || uri.getFragment() != null
                || !(uri.getPath().isEmpty() || "/".equals(uri.getPath()))) {
            throw new IllegalArgumentException("语音服务地址必须是 HTTP(S) 根地址");
        }
        var factory =
                new JdkClientHttpRequestFactory(
                        HttpClient.newBuilder()
                                .connectTimeout(Duration.ofSeconds(2))
                                .followRedirects(HttpClient.Redirect.NEVER)
                                .build());
        factory.setReadTimeout(Duration.ofSeconds(60));
        http =
                RestClient.builder()
                        .baseUrl(uri.getScheme() + "://" + uri.getRawAuthority())
                        .requestFactory(factory)
                        .build();
        this.json = json;
    }

    @Override
    public String transcribe(byte[] audio, String contentType) {
        var headers = new HttpHeaders();
        headers.setContentDispositionFormData("audio", "recording");
        headers.setContentType(MediaType.APPLICATION_OCTET_STREAM);
        var body = new LinkedMultiValueMap<String, HttpEntity<ByteArrayResource>>();
        body.add("audio", new HttpEntity<>(new ByteArrayResource(audio), headers));
        byte[] result = send("/transcriptions", MediaType.MULTIPART_FORM_DATA, body, 32_768);
        try {
            var response = json.readTree(result);
            var text = response == null ? null : response.get("text");
            if (text != null && text.isTextual() && !text.asText().isBlank()) return text.asText();
        } catch (java.io.IOException exception) {
            throw BusinessException.upstream("语音识别返回格式错误");
        }
        throw BusinessException.upstream("语音识别未返回文本");
    }

    @Override
    public byte[] synthesize(String text, double speechRate) {
        byte[] audio =
                send(
                        "/syntheses",
                        MediaType.APPLICATION_JSON,
                        Map.of("text", text, "speechRate", speechRate),
                        MAX_WAV_BYTES);
        if (!SpeechController.supported(audio, "audio/wav")) {
            throw BusinessException.upstream("语音服务未返回有效 WAV");
        }
        return audio;
    }

    private byte[] send(String path, MediaType contentType, Object body, int maxBytes) {
        try {
            return http.post()
                    .uri(path)
                    .contentType(contentType)
                    .body(body)
                    .exchange(
                            (request, response) -> {
                                int status = response.getStatusCode().value();
                                if (status == 400 || status == 422) {
                                    throw BusinessException.invalid("语音服务无法处理输入，请检查音频或文本");
                                }
                                if (status == 429) throw BusinessException.upstream("语音服务繁忙，请稍后重试");
                                if (status != 200) throw BusinessException.upstream("语音服务暂不可用");
                                byte[] bytes = response.getBody().readNBytes(maxBytes + 1);
                                if (bytes.length == 0 || bytes.length > maxBytes) {
                                    throw BusinessException.upstream("语音服务返回大小无效");
                                }
                                return bytes;
                            });
        } catch (ResourceAccessException exception) {
            if (exception.getCause() instanceof HttpTimeoutException) {
                throw new BusinessException(HttpStatus.GATEWAY_TIMEOUT, "语音服务响应超时");
            }
            throw BusinessException.upstream("无法连接语音服务");
        }
    }

    @Override
    public boolean simulated() {
        return false;
    }
}
