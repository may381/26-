package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.agent.AgentProtocol.*;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.security.CurrentActor;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Semaphore;
import java.util.function.Function;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Component;

@Component
public class AgentInvocationRegistry {
    private final Map<String, Grant> grants = new ConcurrentHashMap<>();
    private final Semaphore capacity = new Semaphore(256);

    public final class Grant implements AutoCloseable {
        private final String token = UUID.randomUUID() + "-" + UUID.randomUUID();
        final CurrentActor actor;
        final String agentId;
        final Message message;
        final String writeKey;
        final String traceId;
        private final Instant expiresAt = Instant.now().plusSeconds(15);
        private final List<ToolCall> results = new ArrayList<>();
        private boolean closed;

        private Grant(
                CurrentActor actor,
                String agentId,
                Message message,
                String writeKey,
                String traceId) {
            this.actor = actor;
            this.agentId = agentId;
            this.message = message;
            this.writeKey = writeKey;
            this.traceId = traceId;
        }

        public String token() {
            return token;
        }

        public synchronized List<ToolCall> finish() {
            close();
            return List.copyOf(results);
        }

        @Override
        public synchronized void close() {
            if (!closed) {
                closed = true;
                grants.remove(token, this);
                capacity.release();
            }
        }

        void record(ToolCall result) {
            results.add(result);
        }
    }

    public Grant open(
            CurrentActor actor, String agentId, Message message, String writeKey, String traceId) {
        if (actor.role() != cn.silvertravel.platform.security.ActorRole.ELDER
                || !Objects.equals(actor.elderUserId(), message.userId()))
            throw new AccessDeniedException("对话上下文必须属于当前老人");
        for (var grant : grants.values())
            if (!grant.expiresAt.isAfter(Instant.now())) grant.close();
        if (!capacity.tryAcquire()) throw BusinessException.upstream("Agent 请求繁忙，请稍后重试");
        Grant grant = new Grant(actor, agentId, message, writeKey, traceId);
        grants.put(grant.token, grant);
        return grant;
    }

    public <T> T use(String agentId, String token, String tool, Function<Grant, T> action) {
        Grant grant = token == null ? null : grants.get(token);
        if (grant == null) throw new AccessDeniedException("无有效对话上下文");
        synchronized (grant) {
            Set<String> allowed =
                    switch (agentId) {
                        case "a1" -> Set.of("route.recommend", "knowledge.search");
                        case "a2" -> Set.of("help.create", "help.get", "knowledge.search");
                        case "a3" -> Set.of("memory.read", "memory.write");
                        default -> Set.of();
                    };
            if (grant.closed
                    || !grant.expiresAt.isAfter(Instant.now())
                    || !grant.agentId.equals(agentId)
                    || !allowed.contains(tool)) throw new AccessDeniedException("工具超出调用范围或上下文已失效");
            if (grant.results.size() >= 10) throw new AccessDeniedException("单次对话工具调用次数已达上限");
            return action.apply(grant);
        }
    }
}
