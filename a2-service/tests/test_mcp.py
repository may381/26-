# -*- coding: utf-8 -*-
"""A2 侧 MCP 工具调用测试（连本地 mock 工单 server，不依赖 P2）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_client import MCPClient  # noqa: E402


def test_mcp_list_tools():
    c = MCPClient()
    c.start()
    try:
        tools = c.list_tools()
        assert any(t["name"] == "create_ticket" for t in tools), "应暴露 create_ticket 工具"
    finally:
        c.stop()


def test_mcp_create_ticket():
    c = MCPClient()
    c.start()
    try:
        res = c.create_ticket("老人迷路求助", "南门附近走失", "HIGH")
        assert res is not None, "应返回工单结果"
        assert "ticketId" in res and res["ticketId"].startswith("TKT-"), "应返回工单编号"
        assert res["status"] == "OPEN"
    finally:
        c.stop()
