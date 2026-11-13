package cn.silvertravel.platform.common.idempotency;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.security.CurrentActor;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.HexFormat;
import java.util.function.Function;
import java.util.function.Supplier;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class IdempotencyService {
    private record Entry(String hash, String response, Instant expiresAt) {}

    private final JdbcTemplate jdbc;
    private final ObjectMapper json;

    public IdempotencyService(JdbcTemplate jdbc, ObjectMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public <T> T execute(
            CurrentActor actor,
            String operation,
            String key,
            Object request,
            Class<T> responseType,
            Function<T, String> resourceId,
            Supplier<T> action) {
        if (key == null) {
            return action.get();
        }
        if (!key.matches("[A-Za-z0-9._:-]{1,128}")) {
            throw BusinessException.invalid("Idempotency-Key 必须为 1～128 位字母、数字或 . _ : -");
        }
        String requestHash = hash(encode(request));
        Instant now = Instant.now().truncatedTo(ChronoUnit.MICROS);
        jdbc.update(
                """
                INSERT INTO idempotency_request(actor_id,operation,request_key,request_hash,created_at,expires_at)
                VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE request_key=request_key
                """,
                actor.id(),
                operation,
                key,
                requestHash,
                Timestamp.from(now),
                Timestamp.from(now.plus(Duration.ofHours(24))));
        Entry entry =
                jdbc.queryForObject(
                        """
                SELECT request_hash,response_json,expires_at FROM idempotency_request
                WHERE actor_id=? AND operation=? AND request_key=? FOR UPDATE
                """,
                        (row, index) ->
                                new Entry(
                                        row.getString("request_hash"),
                                        row.getString("response_json"),
                                        row.getTimestamp("expires_at").toInstant()),
                        actor.id(),
                        operation,
                        key);
        if (entry == null) {
            throw new IllegalStateException("幂等记录不存在");
        }
        boolean expired = !entry.expiresAt().isAfter(now);
        if (!expired && !entry.hash().equals(requestHash)) {
            throw BusinessException.conflict("同一 Idempotency-Key 不能用于不同请求");
        }
        if (!expired && entry.response() != null) {
            try {
                return json.readValue(entry.response(), responseType);
            } catch (JsonProcessingException exception) {
                throw new IllegalStateException("幂等响应无效", exception);
            }
        }
        T result = action.get();
        jdbc.update(
                """
                UPDATE idempotency_request SET request_hash=?,resource_id=?,response_json=?,created_at=?,expires_at=?
                WHERE actor_id=? AND operation=? AND request_key=?
                """,
                requestHash,
                resourceId.apply(result),
                encode(result),
                Timestamp.from(now),
                Timestamp.from(now.plus(Duration.ofHours(24))),
                actor.id(),
                operation,
                key);
        return result;
    }

    private String encode(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("无法序列化幂等数据", exception);
        }
    }

    private String hash(String value) {
        try {
            return HexFormat.of()
                    .formatHex(
                            MessageDigest.getInstance("SHA-256")
                                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(exception);
        }
    }
}
