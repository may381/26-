package cn.silvertravel.platform.scenic;

import cn.silvertravel.platform.scenic.ScenicData.*;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Validator;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Set;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Component;

@Component
public class ScenicDatasetImporter {
    private static final int MAX_BYTES = 5 * 1024 * 1024;
    private final ObjectMapper json;
    private final Validator validator;

    public ScenicDatasetImporter(ObjectMapper json, Validator validator) {
        this.json =
                json.copy()
                        .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
                        .enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION);
        this.validator = validator;
    }

    public Dataset read(Resource resource) {
        try (InputStream input = resource.getInputStream()) {
            return read(input);
        } catch (IOException exception) {
            throw new IllegalArgumentException("无法读取景区数据资源", exception);
        }
    }

    public Dataset read(InputStream input) {
        try {
            byte[] bytes = input.readNBytes(MAX_BYTES + 1);
            if (bytes.length > MAX_BYTES) {
                throw invalid("文件超过 5 MiB");
            }
            Dataset dataset = json.readValue(bytes, Dataset.class);
            validate(dataset);
            return dataset;
        } catch (IOException exception) {
            throw new IllegalArgumentException("景区 JSON 无效或读取失败", exception);
        }
    }

    public String write(Dataset dataset) {
        validate(dataset);
        try {
            return json.writeValueAsString(dataset);
        } catch (JsonProcessingException exception) {
            throw new IllegalArgumentException("无法序列化景区数据", exception);
        }
    }

    public void validate(Dataset dataset) {
        if (dataset == null || !validator.validate(dataset).isEmpty()) {
            throw invalid("字段缺失或超出范围");
        }
        Set<String> spotIds = new HashSet<>();
        for (Spot spot : dataset.spots()) {
            if (!spotIds.add(spot.id())) {
                throw invalid("景点 ID 重复");
            }
            checkSource(dataset, spot.source());
        }
        var facilities = new HashMap<String, Facility>();
        for (Facility facility : dataset.facilities()) {
            if (facilities.putIfAbsent(facility.id(), facility) != null) {
                throw invalid("设施 ID 重复");
            }
            if (!spotIds.contains(facility.spotId())) {
                throw invalid("设施关联景点不存在");
            }
            checkSource(dataset, facility.source());
        }
        Set<String> routeIds = new HashSet<>();
        for (Route route : dataset.routes()) {
            if (!routeIds.add(route.id())) {
                throw invalid("路线 ID 重复");
            }
            checkSource(dataset, route.source());
            if (route.spots().stream().anyMatch(id -> !spotIds.contains(id))) {
                throw invalid("路线引用未知景点");
            }
            if (route.segments().size() != route.spots().size() - 1) {
                throw invalid("路线与分段数量不一致");
            }
            for (int i = 0; i < route.segments().size(); i++) {
                Segment segment = route.segments().get(i);
                checkSource(dataset, segment.source());
                if (!segment.fromSpotId().equals(route.spots().get(i))
                        || !segment.toSpotId().equals(route.spots().get(i + 1))
                        || segment.fromSpotId().equals(segment.toSpotId())) {
                    throw invalid("路线分段不连续");
                }
                if (new HashSet<>(segment.restFacilities()).size()
                        != segment.restFacilities().size()) {
                    throw invalid("分段休息设施重复");
                }
                for (String id : segment.restFacilities()) {
                    Facility facility = facilities.get(id);
                    if (facility == null || facility.type() != FacilityType.BENCH) {
                        throw invalid("休息设施必须引用有效座椅");
                    }
                    if (!facility.spotId().equals(segment.fromSpotId())
                            && !facility.spotId().equals(segment.toSpotId())) {
                        throw invalid("休息设施必须属于分段端点景点");
                    }
                }
            }
            if (route.totalWalkMin() > 1440) {
                throw invalid("路线总步行时长超过一天");
            }
        }
    }

    private void checkSource(Dataset dataset, Source source) {
        if (source != dataset.scenic().source()) {
            throw invalid("同一景区快照的来源必须一致");
        }
    }

    private IllegalArgumentException invalid(String reason) {
        return new IllegalArgumentException("景区数据校验失败：" + reason);
    }
}
