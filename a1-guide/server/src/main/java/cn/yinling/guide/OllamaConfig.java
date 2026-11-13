package cn.yinling.guide;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
import java.net.URI;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.Set;

@Configuration
public class OllamaConfig {
    RestClient ollamaRestClient(String baseUrl, int seconds) {
        return ollamaRestClient(baseUrl, seconds, "ollama");
    }
    @Bean
    RestClient ollamaRestClient(@Value("${ai.ollama.base-url}") String baseUrl,
                               @Value("${ai.ollama.timeout-seconds}") int seconds,
                               @Value("${ai.model.provider:ollama}") String provider) {
        if (!Set.of("ollama", "school").contains(provider)) throw new IllegalArgumentException("Unknown model provider");
        if ("school".equals(provider)) baseUrl = "http://10.138.50.151:8000";
        URI uri = URI.create(baseUrl);
        if (!("school".equals(provider) && "10.138.50.151".equals(uri.getHost())) && !Set.of("localhost", "127.0.0.1", "::1", "[::1]").contains(uri.getHost())
            || !"http".equals(uri.getScheme()) || uri.getUserInfo() != null
            || uri.getQuery() != null || uri.getFragment() != null
            || !(uri.getPath().isEmpty() || uri.getPath().equals("/"))) {
            throw new IllegalArgumentException("本地模型地址必须是本机 HTTP 根地址，例如 http://127.0.0.1:11434");
        }
        if (seconds < 1 || seconds > 300) throw new IllegalArgumentException("模型超时范围：1 至 300 秒");
        var factory = new JdkClientHttpRequestFactory(HttpClient.newBuilder()
            // School vLLM HTTP endpoint rejects JDK cleartext HTTP/2 upgrade bodies.
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(3)).build());
        factory.setReadTimeout(Duration.ofSeconds(seconds));
        return RestClient.builder().baseUrl(baseUrl).requestFactory(factory).build();
    }
}
