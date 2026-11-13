package cn.yinling.guide;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import java.io.IOException;

@Component
public class MockScenicProvider implements ScenicDataProvider {
    private final JsonNode data;
    public MockScenicProvider(ObjectMapper mapper, @Value("${data.source}") String source) throws IOException {
        if (!"mock".equals(source)) throw new IllegalStateException("真实数据 Provider 尚未接入，不能使用 data.source=" + source);
        try (var stream = new ClassPathResource("fixtures/qingfeng.json").getInputStream()) {
            data = mapper.readTree(stream);
        }
    }
    public JsonNode park() { return data.get("park").deepCopy(); }
    public JsonNode spots() { return data.get("spots").deepCopy(); }
    public JsonNode facilities() { return data.get("facilities").deepCopy(); }
    public JsonNode routes() { return data.get("routes").deepCopy(); }
}
