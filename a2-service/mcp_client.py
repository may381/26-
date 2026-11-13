# -*- coding: utf-8 -*-
"""
A2 侧 MCP 客户端（最小 JSON-RPC 2.0 over stdio 实现，零额外依赖）。

目标：在「只负责 A2、不碰 P2」前提下，让 A2 具备「通过 MCP 协议调用外部
工具（如创建工单）」的企业级能力。当前连接本地 mock 工单 server 验证协议；
接入真实环境时，只需把 server_cmd 指向 P2 提供的 MCP server 即可。

线程模型：MCP 通信是同步阻塞的，A2 在 agent_logic 里用 asyncio.to_thread
包裹调用，避免阻塞 FastAPI 事件循环。
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("a2.mcp")


class MCPClient:
    """最小 MCP client：initialize 握手 + tools/list + tools/call。"""

    def __init__(self, server_cmd: Optional[List[str]] = None):
        if server_cmd is None:
            server_script = Path(__file__).parent / "servers" / "ticket_server.py"
            server_cmd = [sys.executable, str(server_script)]
        self.server_cmd = server_cmd
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._req_id = 0
        self._tools_cache: Optional[List[dict]] = None

    def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            self.server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8",
        )
        # 握手
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "a2-agent", "version": "1.0.0"},
        })
        # 通知 server 初始化完成
        self._notify("notifications/initialized", {})
        logger.info("MCP server 已启动：%s", " ".join(self.server_cmd))

    def stop(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _notify(self, method: str, params: dict) -> None:
        if self._proc is None:
            self.start()
        self._proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n")
        self._proc.stdin.flush()

    def _rpc(self, method: str, params: dict) -> Any:
        with self._lock:
            if self._proc is None:
                self.start()
            rid = self._next_id()
            self._proc.stdin.write(
                json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n"
            )
            self._proc.stdin.flush()
            # 读取直到匹配当前 rid 的响应（忽略通知/其它消息）
            while True:
                line = self._proc.stdout.readline()
                if not line:
                    raise RuntimeError("MCP server 连接断开")
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                if msg.get("id") == rid:
                    if "error" in msg:
                        raise RuntimeError("MCP error: %s" % msg["error"])
                    return msg.get("result")

    def list_tools(self) -> List[dict]:
        if self._tools_cache is None:
            res = self._rpc("tools/list", {})
            self._tools_cache = (res or {}).get("tools", [])
        return self._tools_cache

    def call_tool(self, name: str, arguments: dict) -> Any:
        res = self._rpc("tools/call", {"name": name, "arguments": arguments})
        return res

    def create_ticket(self, title: str, description: str = "", priority: str = "NORMAL") -> Optional[dict]:
        """便捷方法：创建工单，返回解析后的结果 dict（含 ticketId）。"""
        res = self.call_tool("create_ticket", {
            "title": title, "description": description, "priority": priority,
        })
        try:
            text = res["content"][0]["text"]
            return json.loads(text)
        except Exception as exc:
            logger.warning("解析 MCP 工单结果失败：%s", exc)
            return None


_client_instance: Optional[MCPClient] = None


def get_client() -> MCPClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = MCPClient()
        _client_instance.start()
    return _client_instance
