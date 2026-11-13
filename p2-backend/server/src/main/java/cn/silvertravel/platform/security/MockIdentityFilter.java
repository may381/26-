package cn.silvertravel.platform.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Collections;
import java.util.List;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

/** Registered only inside the Spring Security chain, not as a servlet filter bean. */
public final class MockIdentityFilter extends OncePerRequestFilter {
    public static final String ACTOR_ID_HEADER = "X-Mock-Actor-Id";
    public static final String ACTOR_ROLE_HEADER = "X-Mock-Actor-Role";
    private final SecurityResponseWriter errors;

    public MockIdentityFilter(SecurityResponseWriter errors) {
        this.errors = errors;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return request.getRequestURI().startsWith("/internal/agent/");
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        List<String> ids = Collections.list(request.getHeaders(ACTOR_ID_HEADER));
        List<String> roles = Collections.list(request.getHeaders(ACTOR_ROLE_HEADER));
        if (ids.isEmpty() && roles.isEmpty()) {
            chain.doFilter(request, response);
            return;
        }
        if (ids.size() != 1 || roles.size() != 1) {
            reject(response);
            return;
        }
        CurrentActor actor = MockIdentityDirectory.find(ids.getFirst()).orElse(null);
        if (actor == null || !actor.role().name().equals(roles.getFirst())) {
            reject(response);
            return;
        }
        var authentication =
                UsernamePasswordAuthenticationToken.authenticated(
                        actor,
                        null,
                        List.of(new SimpleGrantedAuthority("ROLE_" + actor.role().name())));
        var context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        try {
            chain.doFilter(request, response);
        } finally {
            SecurityContextHolder.clearContext();
        }
    }

    private void reject(HttpServletResponse response) throws IOException {
        errors.write(response, 401, "UNAUTHORIZED", "mock 身份无效");
    }
}
