package cn.silvertravel.platform.scenic;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("data")
public record ScenicDataProperties(
        @DefaultValue("mock") @Pattern(regexp = "mock|real") String source,
        @DefaultValue("classpath:fixtures/qingfeng.json") @NotBlank String fixture) {}
