# -*- coding: utf-8 -*-
"""capabilities 包：A2 八大业务能力的统一底座。

设计原则（在「只负责 A2、不碰 P2」前提下）：
- 每个能力是一个独立 handler，输入派活消息、输出结构化 CapabilityResult。
- 共用管线（护栏 / 缓存 / RAG / MCP / 真实大模型 / 输出护栏 / 可观测）抽到 _core.py，
  避免每个能力重复造轮子，也保证指标口径一致。
- 契约 4.1：非 tourism/help 意图「必须能被识别，并返回统一的演示占位结果」——
  因此健康生活/家庭照护/家庭协同/社区活动/志愿服务走 placeholder 处理器（真实识别 + 结构化占位）。
"""
from capabilities.base import CapabilityResult
from capabilities.router import dispatch

__all__ = ["CapabilityResult", "dispatch"]
