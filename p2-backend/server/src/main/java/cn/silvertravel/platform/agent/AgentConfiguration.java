package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.common.api.BusinessException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.http.HttpClient;
import java.time.Duration;
import org.springframework.context.annotation.*;
import org.springframework.core.env.Environment;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration(proxyBeanMethods = false)
@Profile("!bootstrap")
public class AgentConfiguration {
    @Bean
    org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler taskScheduler(){
        var scheduler=new org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler();scheduler.setPoolSize(4);scheduler.setThreadNamePrefix("p2-control-");scheduler.setWaitForTasksToCompleteOnShutdown(false);return scheduler;
    }
    @Bean
    AgentGateway agentGateway(
            AgentProperties properties,
            AgentToolService tools,
            ObjectMapper json,
            Environment environment) {
        if (properties.mode() == AgentProperties.Mode.mock) {
            if (!environment.matchesProfiles("local", "mock")
                    || environment.matchesProfiles("prod", "production"))
                throw new IllegalStateException("Agent mock 仅允许开发环境");
            return new MockAgentGateway(tools, json);
        }
        if (properties.mode() == AgentProperties.Mode.disabled)
            return new AgentGateway() {
                public AgentProtocol.Intent classify(AgentProtocol.Message message, String trace) {
                    throw BusinessException.upstream("Agent 服务未启用");
                }

                public AgentProtocol.Reply respond(String id, AgentProtocol.WireMessage message) {
                    throw BusinessException.upstream("Agent 服务未启用");
                }
            };
        var client =
                HttpClient.newBuilder()
                        .connectTimeout(Duration.ofSeconds(2))
                        .followRedirects(HttpClient.Redirect.NEVER)
                        .build();
        var factory = new JdkClientHttpRequestFactory(client);
        factory.setReadTimeout(Duration.ofSeconds(5));
        return new HttpAgentGateway(
                RestClient.builder().requestFactory(factory).build(), properties, json);
    }
}
