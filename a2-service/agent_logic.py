# -*- coding: utf-8 -*-
"""
agent_logic.py —— A2 业务编排入口（保持对外接口稳定，内部委托 capabilities 路由）
====================================================================
历史：早期版本把「护栏→缓存→RAG→MCP→LLM→输出护栏→14字段」全部写在本文件。
重构后，八大业务能力的真实逻辑拆分到 capabilities/ 包（每个能力一个 handler），
本模块只负责两件事：

1. 暴露 build_reply(message) 供 main.py 调用，返回模板 D 结果单（恰好 14 字段）。
2. 保留 call_llm / call_p2_tool 两个模块级引用，供测试 monkeypatch
   （test_service.py / tests/eval/run_eval.py 用 `agent_logic.call_llm = fake` 注入确定性依赖）。

能力路由、结构化字段填充（handoff/results/usedMemoryRefs/inputRequest）均在 capabilities/ 内完成。
"""
from llm_client import call_llm
from p2_client import call_p2_tool
from capabilities import dispatch


async def build_reply(message: dict) -> dict:
    """根据派活消息生成结果单（dict，模板 D）。异步：handler 内 LLM/工具调用均不阻塞事件循环。"""
    return await dispatch(message)
