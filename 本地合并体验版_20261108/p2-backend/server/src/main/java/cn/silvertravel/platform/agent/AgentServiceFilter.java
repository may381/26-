package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.security.SecurityResponseWriter;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.*;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

public class AgentServiceFilter extends OncePerRequestFilter {
    private final AgentProperties properties;
    private final SecurityResponseWriter errors;

    public AgentServiceFilter(AgentProperties properties, SecurityResponseWriter errors) {
        this.properties = properties;
        this.errors = errors;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/internal/agent/");
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        var keys = Collections.list(request.getHeaders("X-Agent-Key"));
        String id = keys.size() == 1 ? properties.identify(keys.getFirst()) : null;
        if (id == null
                || request.getHeader("X-Mock-Actor-Id") != null
                || request.getHeader("X-Mock-Actor-Role") != null) {
            errors.write(response, 401, "UNAUTHORIZED", "Agent 服务身份无效");
            return;
        }
        var context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(
                UsernamePasswordAuthenticationToken.authenticated(
                        new AgentServiceIdentity(id),
                        null,
                        List.of(new SimpleGrantedAuthority("AGENT_SERVICE"))));
        SecurityContextHolder.setContext(context);
        try {
            chain.doFilter(request, response);
        } finally {
            SecurityContextHolder.clearContext();
        }
    }
}
