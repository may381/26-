package cn.silvertravel.platform.scenic;

import cn.silvertravel.platform.scenic.ScenicData.Dataset;
import cn.silvertravel.platform.scenic.persistence.ScenicDatasetRepository;
import org.springframework.context.annotation.Profile;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class ScenicDatasetImportService {
    private final ScenicDatasetImporter importer;
    private final ScenicDatasetRepository repository;

    public ScenicDatasetImportService(
            ScenicDatasetImporter importer, ScenicDatasetRepository repository) {
        this.importer = importer;
        this.repository = repository;
    }

    @Transactional
    public Dataset importResource(Resource resource) {
        Dataset dataset = importer.read(resource);
        repository.save(dataset);
        return dataset;
    }
}
