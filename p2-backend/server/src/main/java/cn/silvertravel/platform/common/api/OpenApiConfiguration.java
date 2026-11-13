package cn.silvertravel.platform.common.api;

import cn.silvertravel.platform.profile.ProfileFields;
import io.swagger.v3.core.converter.AnnotatedType;
import io.swagger.v3.core.converter.ModelConverters;
import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.media.BooleanSchema;
import io.swagger.v3.oas.models.media.ObjectSchema;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springdoc.core.customizers.GlobalOpenApiCustomizer;
import org.springdoc.core.models.GroupedOpenApi;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class OpenApiConfiguration {
    @Bean
    GlobalOpenApiCustomizer patchDocumentation() {
        return api -> {
            if (api.getPaths() == null) return;
            var profile = api.getPaths().get("/api/v3/profile");
            if (profile != null && profile.getPatch() != null) {
                var resolved =
                        ModelConverters.getInstance()
                                .resolveAsResolvedSchema(
                                        new AnnotatedType(ProfileFields.class).resolveAsRef(false));
                api.getComponents().getSchemas().putAll(resolved.referencedSchemas);
                var patch = resolved.schema;
                patch.setRequired(null);
                patch.setMinProperties(1);
                patch.setAdditionalProperties(false);
                patch.setDescription(
                        "首次建档必须提供全部十项档案字段；已有档案可只传要修改的字段。未传保留，null 拒绝，数组整体替换。id 只读，不能提交。");
                profile.getPatch()
                        .getRequestBody()
                        .getContent()
                        .get("application/json")
                        .setSchema(patch);
            }
            var family = api.getPaths().get("/api/v3/family-relations/{id}/permissions");
            if (family != null && family.getPatch() != null) {
                var permissions = new ObjectSchema();
                for (String name :
                        java.util.List.of(
                                "shareLocation", "shareProgress", "shareAlert", "remotePlanning")) {
                    permissions.addProperty(name, new BooleanSchema());
                }
                permissions.setMinProperties(1);
                permissions.setAdditionalProperties(false);
                permissions.setDescription(
                        "ACTIVE 关系的独立权限部分更新；至少一项布尔值，未传保留，null 拒绝。正文直接传开关，不包 permissions 外层。");
                family.getPatch()
                        .getRequestBody()
                        .getContent()
                        .get("application/json")
                        .setSchema(permissions);
            }
        };
    }

    @Bean
    GroupedOpenApi platformApi() {
        return GroupedOpenApi.builder().group("p2").pathsToMatch("/api/v3/**").build();
    }

    @Bean
    OpenAPI platformDocumentation() {
        return new OpenAPI()
                .info(
                        new Info()
                                .title("银龄智游 P2 本地联调 API")
                                .version("3.0")
                                .description(
                                        "本地身份为 mock；Authorize 同时填写 actorId=u100、actorRole=ELDER。语音、Agent、通知均有模拟实现；高德地图需独立配置后端 Key。内部 Agent 工具协议见项目文档。"))
                .components(
                        new Components()
                                .addSecuritySchemes("actorId", header("X-Mock-Actor-Id"))
                                .addSecuritySchemes("actorRole", header("X-Mock-Actor-Role")))
                .addSecurityItem(new SecurityRequirement().addList("actorId").addList("actorRole"));
    }

    private SecurityScheme header(String name) {
        return new SecurityScheme()
                .type(SecurityScheme.Type.APIKEY)
                .in(SecurityScheme.In.HEADER)
                .name(name);
    }
}
