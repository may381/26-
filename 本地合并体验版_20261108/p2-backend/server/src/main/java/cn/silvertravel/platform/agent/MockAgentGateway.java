package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.agent.AgentProtocol.*;
import cn.silvertravel.platform.common.api.BusinessException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;

/** Explicit Java mock adapter; not an LLM or a real Python Agent. */
public class MockAgentGateway implements AgentGateway {
    private final AgentToolService tools;
    private final ObjectMapper json;

    public MockAgentGateway(AgentToolService tools, ObjectMapper json) {
        this.tools = tools;
        this.json = json;
    }

    @Override
    public Intent classify(Message message, String traceId) {
        String text = message.text();
        if (contains(text, "求助", "迷路", "不舒服", "帮忙", "找人")) return Intent.help;
        if (contains(text, "诈骗", "转账")) return Intent.fraud;
        if (contains(text, "健康", "饮食")) return Intent.health;
        if (contains(text, "照护", "陪诊")) return Intent.care;
        if (contains(text, "非遗", "文化课")) return Intent.culture;
        if (contains(text, "志愿")) return Intent.volunteer;
        if (contains(text, "技能", "教人")) return Intent.ability;
        if (contains(text, "社区", "活动")) return Intent.community;
        return Intent.tourism;
    }

    @Override
    public Reply respond(String agentId, WireMessage message) {
        if (message.intent() == Intent.help) {
            if (message.context() != null && message.context().location() != null) {
                try {
                    var args = json.createObjectNode().put("type", "GENERAL");
                    args.putObject("location").put("spotId", message.context().location());
                    var call =
                            tools.execute(
                                    agentId,
                                    message.toolContextToken(),
                                    new ToolRequest("help.create", args));
                    return reply(
                            message,
                            "【演示】求助已记录，通知仅为模拟；请查看求助状态。",
                            List.of(call),
                            new Handoff("human_handoff", HandoffTarget.scenic, "演示求助记录已建立"));
                } catch (BusinessException exception) {
                    if (exception.status().value() != 409
                            || !exception.getMessage().startsWith("求助工具需要")) throw exception;
                }
            }
            return reply(
                    message,
                    "【演示】请使用求助按钮并提供位置；当前没有创建求助或实际通知任何人。",
                    List.of(),
                    new Handoff("human_handoff", HandoffTarget.scenic, "老人请求人工帮助，尚未创建求助"));
        }
        if (message.text().contains("路线")) {
            try {
                var call =
                        tools.execute(
                                agentId,
                                message.toolContextToken(),
                                new ToolRequest("route.recommend", json.createObjectNode()));
                return reply(message, "【演示】已按档案查询候选路线，请确认后开始游览。", List.of(call), null);
            } catch (BusinessException exception) {
                if (exception.status().value() != 404) throw exception;
                return reply(message, "【演示】请先填写档案，再查询个性化路线。", List.of(), null);
            }
        }
        var args = json.createObjectNode().put("query", message.text()).put("intent", "tourism");
        var call =
                tools.execute(
                        agentId,
                        message.toolContextToken(),
                        new ToolRequest("knowledge.search", args));
        var entries = call.result().path("entries");
        String answer =
                entries.isEmpty()
                        ? call.result().path("message").asText()
                        : String.join(
                                        "、",
                                        java.util.stream.StreamSupport.stream(
                                                        entries.spliterator(), false)
                                                .map(e -> e.path("title").asText())
                                                .toList())
                                + "；请按演示/真实来源标识查看，未计算最近距离。";
        return reply(message, "【演示】" + answer, List.of(call), null);
    }

    private Reply reply(WireMessage message, String text, List<ToolCall> tools, Handoff handoff) {
        return new Reply(message.intent(), text, 0.8, null, tools, handoff);
    }

    private boolean contains(String text, String... terms) {
        return Arrays.stream(terms).anyMatch(text::contains);
    }
}
