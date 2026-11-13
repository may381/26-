package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.agent.AgentProtocol.Intent;
import cn.silvertravel.platform.scenic.ScenicData.*;
import cn.silvertravel.platform.scenic.ScenicDataProvider;
import java.time.Instant;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;

@Service
@Profile("!bootstrap")
public class KnowledgeService {
    public record Entry(
            String id,
            String title,
            String content,
            Source source,
            Instant updatedAt,
            String verifiedBy) {}

    public record Result(boolean available, List<Entry> entries, String message) {}

    private final ScenicDataProvider scenic;

    public KnowledgeService(ScenicDataProvider scenic) {
        this.scenic = scenic;
    }

    public Result search(String query, Intent intent) {
        if (intent != null && intent != Intent.tourism && intent != Intent.help) {
            return new Result(
                    false,
                    List.of(
                            new Entry(
                                    "placeholder-" + intent,
                                    intent + " 服务占位",
                                    "该服务暂未开放；仅展示接入占位，不提供真实服务能力",
                                    Source.MOCK,
                                    Instant.parse("2026-10-23T00:00:00Z"),
                                    "team")),
                    "该服务暂未开放");
        }
        FacilityType type =
                query.contains("厕所")
                        ? FacilityType.TOILET
                        : (query.contains("座椅") || query.contains("休息") || query.contains("累"))
                                ? FacilityType.BENCH
                                : query.contains("医务")
                                        ? FacilityType.MEDICAL
                                        : query.contains("出口") ? FacilityType.EXIT : null;
        var entries = new ArrayList<Entry>();
        if (type != null)
            for (var site : scenic.listScenics())
                for (var facility : scenic.findById(site.id()).orElseThrow().facilities()) {
                    if (facility.type() == type)
                        entries.add(
                                new Entry(
                                        facility.id(),
                                        facility.name(),
                                        "设施关联景点：" + facility.spotId(),
                                        facility.source(),
                                        facility.updatedAt(),
                                        facility.verifiedBy()));
                }
        return new Result(
                true,
                List.copyOf(entries),
                entries.isEmpty() ? "没有对应资料，不推测距离、开放时间或讲解内容" : "请按来源标识查看设施；未计算最近距离");
    }
}
