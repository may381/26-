#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地 Mock 工单 MCP Server（仅用于 A2 自控验证「MCP 工具调用」协议）。

这是一个最小可用的 MCP（Model Context Protocol）server 实现：
- 通过 stdio 收发 JSON-RPC 2.0 消息（每行一个 JSON 对象）
- 实现 initialize / tools/list / tools/call / ping 的最小子集
- 暴露一个工具：create_ticket（创建工单，返回 mock 工单号）

真实环境中，工单系统由 P2 后端提供 MCP server；A2 只需把这里的
server_cmd 指向真实 server 即可，client 侧代码无需改动。
"""
import json
import sys
import uuid


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def create_ticket(arguments: dict) -> dict:
    tid = "TKT-%s" % uuid.uuid4().hex[:8].upper()
    return {
        "ticketId": tid,
        "status": "OPEN",
        "title": arguments.get("title", "未命名工单"),
        "priority": arguments.get("priority", "NORMAL"),
    }


TOOLS = [
    {
        "name": "create_ticket",
        "description": "为老人/家属创建一条求助或报修工单，返回工单编号。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "工单标题"},
                "description": {"type": "string", "description": "工单详情"},
                "priority": {"type": "string", "enum": ["LOW", "NORMAL", "HIGH", "URGENT"]},
            },
            "required": ["title"],
        },
    }
]


def handle(line: str) -> None:
    try:
        req = json.loads(line)
    except Exception:
        return
    method = req.get("method")
    params = req.get("params") or {}
    rid = req.get("id")

    if method == "initialize":
        send({
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ticket-mock", "version": "1.0.0"},
            },
        })
    elif method == "notifications/initialized":
        pass  # 通知类，无需响应
    elif method == "ping":
        send({"jsonrpc": "2.0", "id": rid, "result": {}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "create_ticket":
            result = create_ticket(args)
            send({
                "jsonrpc": "2.0", "id": rid,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                    "isError": False,
                },
            })
        else:
            send({
                "jsonrpc": "2.0", "id": rid,
                "result": {"content": [{"type": "text", "text": "未知工具: %s" % name}], "isError": True},
            })


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        handle(line)


if __name__ == "__main__":
    main()
