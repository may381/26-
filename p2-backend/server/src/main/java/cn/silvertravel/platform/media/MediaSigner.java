package cn.silvertravel.platform.media;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

@Component
public class MediaSigner {
    public enum Kind {
        TRIP,
        SPEECH
    }

    public record Link(String url, Instant expiresAt) {}

    private static final long TTL_SECONDS = 900;
    private final SecretKeySpec key;
    private final String origin;

    public MediaSigner(
            @Value("${media.signing-key:}") String configuredKey,
            @Value("${media.public-origin:}") String configuredOrigin,
            Environment environment) {
        boolean deployed =
                !configuredOrigin.isBlank() || environment.matchesProfiles("prod", "production");
        if (deployed && (configuredOrigin.isBlank() || configuredKey.isBlank())) {
            throw new IllegalStateException("部署签名媒体需要 HTTPS 公开域名和签名密钥");
        }
        byte[] bytes;
        if (configuredKey.isBlank()) {
            bytes = new byte[32];
            new SecureRandom().nextBytes(bytes);
        } else {
            bytes = Base64.getDecoder().decode(configuredKey);
            if (bytes.length < 32) throw new IllegalArgumentException("媒体签名密钥至少 32 字节");
        }
        key = new SecretKeySpec(bytes, "HmacSHA256");
        if (configuredOrigin.isBlank()) {
            origin = "";
        } else {
            URI uri = URI.create(configuredOrigin);
            if (!"https".equals(uri.getScheme())
                    || uri.getHost() == null
                    || uri.getUserInfo() != null
                    || uri.getQuery() != null
                    || uri.getFragment() != null
                    || !(uri.getPath().isEmpty() || "/".equals(uri.getPath()))) {
                throw new IllegalArgumentException("媒体公开地址必须是 HTTPS 根地址");
            }
            origin = "https://" + uri.getRawAuthority();
        }
    }

    public Link issue(Kind kind, String id, Instant retainUntil) {
        long expires = Instant.now().getEpochSecond() + TTL_SECONDS;
        if (retainUntil != null) expires = Math.min(expires, retainUntil.getEpochSecond());
        String signature =
                Base64.getUrlEncoder().withoutPadding().encodeToString(mac(kind, id, expires));
        return new Link(
                origin
                        + "/api/v3/media/signed/"
                        + id
                        + "?kind="
                        + kind
                        + "&exp="
                        + expires
                        + "&sig="
                        + signature,
                Instant.ofEpochSecond(expires));
    }

    public boolean valid(Kind kind, String id, long expires, String signature) {
        long now = Instant.now().getEpochSecond();
        if (expires <= now || expires > now + TTL_SECONDS || signature.length() != 43) return false;
        try {
            return MessageDigest.isEqual(
                    mac(kind, id, expires), Base64.getUrlDecoder().decode(signature));
        } catch (IllegalArgumentException exception) {
            return false;
        }
    }

    private byte[] mac(Kind kind, String id, long expires) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(key);
            return mac.doFinal(
                    ("p2-media-v1\n" + kind + "\n" + id + "\n" + expires)
                            .getBytes(StandardCharsets.UTF_8));
        } catch (GeneralSecurityException exception) {
            throw new IllegalStateException("无法签名媒体地址", exception);
        }
    }
}
