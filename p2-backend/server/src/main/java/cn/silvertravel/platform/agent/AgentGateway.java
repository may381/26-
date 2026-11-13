package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.agent.AgentProtocol.*;

public interface AgentGateway {
    Intent classify(Message message, String traceId);

    Reply respond(String agentId, WireMessage message);
}
