package cn.silvertravel.platform.route;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.scenic.ScenicData.*;
import cn.silvertravel.platform.scenic.ScenicDataProvider;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;

@Service
@Profile("!bootstrap")
public class RouteCatalog {
    public record Entry(Dataset dataset, Route route) {}

    private final ScenicDataProvider provider;

    public RouteCatalog(ScenicDataProvider provider) {
        this.provider = provider;
    }

    public List<Entry> all() {
        var entries = new ArrayList<Entry>();
        var ids = new HashSet<String>();
        for (Scenic scenic : provider.listScenics()) {
            Dataset dataset =
                    provider.findById(scenic.id())
                            .orElseThrow(() -> new IllegalStateException("景区快照在读取期间不可用"));
            for (Route route : dataset.routes()) {
                if (!ids.add(route.id())) {
                    throw new IllegalStateException("不同景区的路线 ID 不得重复");
                }
                entries.add(new Entry(dataset, route));
            }
        }
        return List.copyOf(entries);
    }

    public Entry require(String routeId) {
        return all().stream()
                .filter(entry -> entry.route().id().equals(routeId))
                .findFirst()
                .orElseThrow(() -> BusinessException.notFound("路线不存在或当前数据源不可用"));
    }
}
