package cn.silvertravel.platform.scenic.persistence;

import cn.silvertravel.platform.scenic.ScenicData.*;
import cn.silvertravel.platform.scenic.ScenicDatasetImporter;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** One atomic validated snapshot per scenic/source; no partial route/spot imports. */
@Repository
@Profile("!bootstrap")
public class ScenicDatasetRepository {
    private final JdbcTemplate jdbc;
    private final ScenicDatasetImporter importer;

    public ScenicDatasetRepository(JdbcTemplate jdbc, ScenicDatasetImporter importer) {
        this.jdbc = jdbc;
        this.importer = importer;
    }

    public void save(Dataset dataset) {
        String document = importer.write(dataset);
        Scenic scenic = dataset.scenic();
        jdbc.update(
                """
                INSERT INTO scenic_dataset(scenic_id, source, dataset_json, updated_at, verified_by)
                VALUES (?, ?, ?, ?, ?) AS incoming
                ON DUPLICATE KEY UPDATE dataset_json = incoming.dataset_json,
                    updated_at = incoming.updated_at, verified_by = incoming.verified_by
                """,
                scenic.id(),
                scenic.source().name(),
                document,
                Timestamp.from(scenic.updatedAt()),
                scenic.verifiedBy());
    }

    public List<Dataset> findReal(String scenicId) {
        String filter = scenicId == null ? "" : " AND scenic_id = ?";
        return jdbc.query(
                "SELECT scenic_id, source, dataset_json FROM scenic_dataset "
                        + "WHERE source IN ('OPEN_DATA', 'FIELD')"
                        + filter
                        + " ORDER BY scenic_id, updated_at DESC, CASE source WHEN 'FIELD' THEN 0 ELSE 1 END",
                (row, index) -> {
                    Dataset dataset =
                            importer.read(
                                    new ByteArrayInputStream(
                                            row.getString("dataset_json")
                                                    .getBytes(StandardCharsets.UTF_8)));
                    if (!dataset.scenic().id().equals(row.getString("scenic_id"))
                            || !dataset.scenic().source().name().equals(row.getString("source"))) {
                        throw new IllegalStateException("景区索引与快照来源不一致");
                    }
                    return dataset;
                },
                scenicId == null ? new Object[0] : new Object[] {scenicId});
    }
}
