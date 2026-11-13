package cn.silvertravel.platform.agent;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class AgentProtocolHeaderFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (request.getRequestURI().equals("/api/v3/agent/messages")
                || request.getRequestURI().equals("/internal/agent/v3/tools")) {
            response.setHeader("X-Agent-Protocol-Version", "3.0");
        }
        chain.doFilter(request, response);
    }
}
