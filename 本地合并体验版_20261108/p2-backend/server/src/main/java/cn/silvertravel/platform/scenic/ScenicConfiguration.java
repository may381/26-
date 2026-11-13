package cn.silvertravel.platform.scenic;

import cn.silvertravel.platform.scenic.persistence.ScenicDatasetRepository;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.*;
import org.springframework.core.io.ResourceLoader;

@Configuration(proxyBeanMethods = false)
@Profile("!bootstrap")
@EnableConfigurationProperties(ScenicDataProperties.class)
public class ScenicConfiguration {
    @Bean
    ScenicDataProvider scenicDataProvider(
            ScenicDataProperties properties,
            ScenicDatasetImporter importer,
            ResourceLoader resources,
            ScenicDatasetRepository repository) {
        return switch (properties.source()) {
            case "mock" ->
                    new MockScenicProvider(importer, resources.getResource(properties.fixture()));
            case "real" -> new DbScenicProvider(repository);
            default -> throw new IllegalArgumentException("data.source 只能为 mock 或 real");
        };
    }

    @Bean
    @ConditionalOnProperty(name = "data.import-location")
    ApplicationRunner importScenicDataset(
            @Value("${data.import-location}") String location,
            ResourceLoader resources,
            ScenicDatasetImportService service) {
        if (!location.startsWith("file:") && !location.startsWith("classpath:")) {
            throw new IllegalArgumentException("景区导入仅支持本地 file: 或 classpath: 资源");
        }
        return args -> {
            var dataset = service.importResource(resources.getResource(location));
            LoggerFactory.getLogger(ScenicConfiguration.class)
                    .info(
                            "Scenic dataset imported: scenicId={}, source={}, routes={}, spots={}, facilities={}",
                            dataset.scenic().id(),
                            dataset.scenic().source(),
                            dataset.routes().size(),
                            dataset.spots().size(),
                            dataset.facilities().size());
        };
    }
}
