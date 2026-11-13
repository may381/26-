package cn.silvertravel.platform.security;

import cn.silvertravel.platform.agent.AgentProperties;
import cn.silvertravel.platform.agent.AgentServiceFilter;
import jakarta.servlet.DispatcherType;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration(proxyBeanMethods = false)
@EnableMethodSecurity
@EnableConfigurationProperties(AgentProperties.class)
public class SecurityConfiguration {
    @Bean
    MockIdentitySettings mockIdentitySettings(
            @Value("${app.security.mock-enabled:false}") boolean enabled, Environment environment) {
        return new MockIdentitySettings(enabled, environment);
    }

    @Bean
    SecurityFilterChain platformSecurity(
            HttpSecurity http,
            MockIdentitySettings settings,
            SecurityResponseWriter errors,
            AgentProperties agents)
            throws Exception {
        http.csrf(AbstractHttpConfigurer::disable)
                .httpBasic(AbstractHttpConfigurer::disable)
                .formLogin(AbstractHttpConfigurer::disable)
                .logout(AbstractHttpConfigurer::disable)
                .requestCache(AbstractHttpConfigurer::disable)
                .sessionManagement(
                        session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .exceptionHandling(
                        handler ->
                                handler.authenticationEntryPoint(
                                                (request, response, exception) ->
                                                        errors.write(
                                                                response,
                                                                401,
                                                                "UNAUTHORIZED",
                                                                "请提供有效的调用身份"))
                                        .accessDeniedHandler(
                                                (request, response, exception) ->
                                                        errors.write(
                                                                response,
                                                                403,
                                                                "FORBIDDEN",
                                                                "无权执行此操作")))
                .authorizeHttpRequests(
                        authorize ->
                                authorize
                                        .dispatcherTypeMatchers(DispatcherType.ERROR)
                                        .permitAll()
                                        .requestMatchers("/actuator/health")
                                        .permitAll()
                                        .requestMatchers(
                                                "/v3/api-docs/**",
                                                "/swagger-ui/**",
                                                "/swagger-ui.html")
                                        .access(
                                                (authentication, context) ->
                                                        new org.springframework.security
                                                                .authorization
                                                                .AuthorizationDecision(
                                                                settings.enabled()))
                                        .requestMatchers(
                                                HttpMethod.GET, "/api/v3/travel-record-shares/**")
                                        .permitAll()
                                        .requestMatchers(HttpMethod.GET, "/api/v3/media/signed/*")
                                        .permitAll()
                                        .requestMatchers(HttpMethod.HEAD, "/api/v3/media/signed/*")
                                        .permitAll()
                                        .requestMatchers("/internal/agent/**")
                                        .hasAuthority("AGENT_SERVICE")
                                        .requestMatchers(
                                                HttpMethod.POST,
                                                "/api/v3/help-events/*/acknowledge",
                                                "/api/v3/help-events/*/resolve")
                                        .hasAnyRole("SCENIC", "OFFICIAL", "ADMIN")
                                        .requestMatchers("/api/v3/**")
                                        .authenticated()
                                        .anyRequest()
                                        .denyAll());
        if (settings.enabled()) {
            http.addFilterBefore(
                    new MockIdentityFilter(errors), UsernamePasswordAuthenticationFilter.class);
        }
        http.addFilterBefore(
                new AgentServiceFilter(agents, errors), UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
}
