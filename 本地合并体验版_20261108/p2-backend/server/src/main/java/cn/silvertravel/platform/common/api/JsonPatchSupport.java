package cn.silvertravel.platform.common.api;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.validation.Validator;
import java.util.Set;
import org.springframework.stereotype.Component;

@Component
public class JsonPatchSupport {
    private final ObjectMapper json;
    private final Validator validator;

    public JsonPatchSupport(ObjectMapper json, Validator validator) {
        this.json = json;
        this.validator = validator;
    }

    /** Only supplied fields replace existing values; null is never silently ignored. */
    public <T> T merge(JsonNode patch, T existing, Class<T> type, Set<String> allowed) {
        if (patch == null || !patch.isObject() || patch.isEmpty()) {
            throw BusinessException.invalid("请提供非空的字段对象");
        }
        ObjectNode merged = existing == null ? json.createObjectNode() : json.valueToTree(existing);
        var fields = patch.fields();
        while (fields.hasNext()) {
            var field = fields.next();
            if (!allowed.contains(field.getKey()) || field.getValue().isNull()) {
                throw BusinessException.invalid("包含不允许修改或为空的字段");
            }
            merged.set(field.getKey(), field.getValue());
        }
        try {
            T value = json.treeToValue(merged, type);
            if (!validator.validate(value).isEmpty()) {
                throw BusinessException.invalid("字段不完整或格式不正确");
            }
            return value;
        } catch (JsonProcessingException exception) {
            throw BusinessException.invalid("字段类型或枚举值不正确");
        }
    }
}
