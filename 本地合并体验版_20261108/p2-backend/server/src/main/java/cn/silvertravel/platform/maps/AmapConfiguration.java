package cn.silvertravel.platform.maps;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.http.HttpClient;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.*;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration(proxyBeanMethods = false)
@Profile("!bootstrap")
@EnableConfigurationProperties(AmapProperties.class)
public class AmapConfiguration {
    @Bean
    AmapClient amapClient(AmapProperties properties, ObjectMapper json) {
        var client =
                HttpClient.newBuilder()
                        .connectTimeout(properties.connectTimeout())
                        .followRedirects(HttpClient.Redirect.NEVER)
                        .build();
        var factory = new JdkClientHttpRequestFactory(client);
        factory.setReadTimeout(properties.readTimeout());
        return new AmapClient(
                RestClient.builder().requestFactory(factory).build(), properties, json);
    }
}
