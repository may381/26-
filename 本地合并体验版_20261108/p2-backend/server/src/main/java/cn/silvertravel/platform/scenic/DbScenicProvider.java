package cn.silvertravel.platform.scenic;

import cn.silvertravel.platform.scenic.ScenicData.*;
import cn.silvertravel.platform.scenic.persistence.ScenicDatasetRepository;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Optional;

public final class DbScenicProvider implements ScenicDataProvider {
    private final ScenicDatasetRepository repository;

    public DbScenicProvider(ScenicDatasetRepository repository) {
        this.repository = repository;
    }

    @Override
    public List<Scenic> listScenics() {
        var selected = new LinkedHashMap<String, Scenic>();
        for (Dataset dataset : repository.findReal(null)) {
            selected.putIfAbsent(dataset.scenic().id(), dataset.scenic());
        }
        return List.copyOf(selected.values());
    }

    @Override
    public Optional<Dataset> findById(String scenicId) {
        if (scenicId == null || scenicId.isBlank()) {
            return Optional.empty();
        }
        return repository.findReal(scenicId).stream().findFirst();
    }
}
