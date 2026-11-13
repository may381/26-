package cn.silvertravel.platform.common.api;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.cfg.CoercionAction;
import com.fasterxml.jackson.databind.cfg.CoercionInputShape;
import com.fasterxml.jackson.databind.type.LogicalType;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class ContractJsonConfiguration {
    @Bean
    public Jackson2ObjectMapperBuilderCustomizer strictContractJson() {
        return builder ->
                builder.featuresToEnable(
                                DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES,
                                DeserializationFeature.FAIL_ON_NUMBERS_FOR_ENUMS)
                        .featuresToDisable(
                                MapperFeature.ALLOW_COERCION_OF_SCALARS,
                                DeserializationFeature.ACCEPT_FLOAT_AS_INT)
                        .postConfigurer(
                                mapper -> {
                                    mapper.coercionConfigFor(LogicalType.Textual)
                                            .setCoercion(
                                                    CoercionInputShape.Integer, CoercionAction.Fail)
                                            .setCoercion(
                                                    CoercionInputShape.Float, CoercionAction.Fail)
                                            .setCoercion(
                                                    CoercionInputShape.Boolean,
                                                    CoercionAction.Fail);
                                });
    }
}
