package cn.silvertravel.platform.agent;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashSet;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("agents")
public record AgentProperties(
        @DefaultValue("disabled") Mode mode,
        @DefaultValue("http://127.0.0.1:18001") String a1Url,
        @DefaultValue("http://127.0.0.1:18002") String a2Url,
        @DefaultValue("http://127.0.0.1:18003") String a3Url,
        @DefaultValue("") String a1ApiKey,
        @DefaultValue("") String a2ApiKey,
        @DefaultValue("") String a3ApiKey) {
    public enum Mode {
        disabled,
        mock,
        http
    }

    public AgentProperties {
        var keys = new HashSet<String>();
        for (String key : new String[] {a1ApiKey, a2ApiKey, a3ApiKey}) {
            if (key != null
                    && !key.isBlank()
                    && (!key.matches("[A-Za-z0-9_-]{16,128}") || !keys.add(key))) {
                throw new IllegalArgumentException("Agent Key 格式无效或服务间重复");
            }
        }
        if (mode == Mode.http && keys.size() != 3) {
            throw new IllegalArgumentException("HTTP 模式需配置三个独立 Agent Key");
        }
        for (String url : new String[] {a1Url, a2Url, a3Url}) {
            URI uri;
            try {
                uri = URI.create(url);
            } catch (RuntimeException exception) {
                throw new IllegalArgumentException("Agent 地址无效");
            }
            boolean local = "127.0.0.1".equals(uri.getHost()) || "localhost".equals(uri.getHost());
            if (uri.getHost() == null
                    || uri.getUserInfo() != null
                    || uri.getQuery() != null
                    || uri.getFragment() != null
                    || !(uri.getPath().isEmpty() || "/".equals(uri.getPath()))
                    || !("https".equals(uri.getScheme())
                            || (local && "http".equals(uri.getScheme())))) {
                throw new IllegalArgumentException("Agent 地址需为无凭据的 HTTPS 根地址或本机 HTTP 根地址");
            }
        }
    }

    public String url(String id) {
        return switch (id) {
            case "a1" -> a1Url;
            case "a2" -> a2Url;
            case "a3" -> a3Url;
            default -> throw new IllegalArgumentException("Unknown Agent");
        };
    }

    public String key(String id) {
        return switch (id) {
            case "a1" -> a1ApiKey;
            case "a2" -> a2ApiKey;
            case "a3" -> a3ApiKey;
            default -> "";
        };
    }

    public String identify(String presented) {
        if (presented == null || presented.length() > 128) return null;
        for (String id : new String[] {"a1", "a2", "a3"}) {
            String configured = key(id);
            if (configured != null
                    && !configured.isBlank()
                    && MessageDigest.isEqual(
                            configured.getBytes(StandardCharsets.UTF_8),
                            presented.getBytes(StandardCharsets.UTF_8))) return id;
        }
        return null;
    }

    @Override
    public String toString() {
        return "AgentProperties[mode=" + mode + ",credentials=redacted]";
    }
}
