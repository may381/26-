package cn.silvertravel.platform.maps;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("amap")
public record AmapProperties(
        @DefaultValue("") String webServiceKey,
        @DefaultValue("PT2S") Duration connectTimeout,
        @DefaultValue("PT5S") Duration readTimeout) {
    public AmapProperties {
        webServiceKey = webServiceKey == null ? "" : webServiceKey.strip();
        if (connectTimeout == null
                || readTimeout == null
                || connectTimeout.isZero()
                || connectTimeout.isNegative()
                || readTimeout.isZero()
                || readTimeout.isNegative()
                || connectTimeout.compareTo(Duration.ofSeconds(10)) > 0
                || readTimeout.compareTo(Duration.ofSeconds(10)) > 0) {
            throw new IllegalArgumentException("高德连接与读取超时必须为 0～10 秒之间的正值");
        }
    }

    @Override
    public String toString() {
        return "AmapProperties[keyConfigured=" + !webServiceKey.isBlank() + "]";
    }
}
