package cn.silvertravel.platform.scenic;

import cn.silvertravel.platform.scenic.ScenicData.*;
import java.util.List;
import java.util.Optional;
import org.springframework.core.io.Resource;

public final class MockScenicProvider implements ScenicDataProvider {
    private final Dataset dataset;

    public MockScenicProvider(ScenicDatasetImporter importer, Resource fixture) {
        dataset = importer.read(fixture);
        if (dataset.scenic().source() != Source.MOCK) {
            throw new IllegalArgumentException("mock Provider 只能加载 MOCK 数据");
        }
    }

    @Override
    public List<Scenic> listScenics() {
        return List.of(dataset.scenic());
    }

    @Override
    public Optional<Dataset> findById(String scenicId) {
        return dataset.scenic().id().equals(scenicId) ? Optional.of(dataset) : Optional.empty();
    }
}
