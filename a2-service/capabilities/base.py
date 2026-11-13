# -*- coding: utf-8 -*-
"""capabilities/base.py —— 能力统一返回结构。"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from schemas import build_result_sheet


@dataclass
class CapabilityResult:
    """一个能力 handler 的统一产出。router 负责把它转成模板 D 结果单。"""
    intent: str
    domains: List[str]
    reply_text: str
    speech_rate: float = 0.8
    tools: List[Dict[str, Any]] = field(default_factory=list)          # build_tool(...) 产物
    handoff: Optional[Dict[str, Any]] = None                           # build_handoff(...)
    results: List[Dict[str, Any]] = field(default_factory=list)        # build_result_item(...)
    used_memory_refs: List[Dict[str, Any]] = field(default_factory=list)  # build_memory_ref(...)
    confirmation_ids: List[str] = field(default_factory=list)
    input_request: Optional[Dict[str, Any]] = None
    control_next: str = "COMPLETE"
    control_outcome: str = "SUCCEEDED"
    dependency_task_ids: List[str] = field(default_factory=list)
    # 演示/调试用的非协议字段（不进 14 字段结果单）
    debug: Dict[str, Any] = field(default_factory=dict)

    def to_sheet(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        return build_result_sheet(
            meta=meta,
            reply_text=self.reply_text,
            speech_rate=self.speech_rate,
            intent=self.intent,
            domains=self.domains,
            tools=self.tools,
            handoff=self.handoff,
            results=self.results,
            used_memory_refs=self.used_memory_refs,
            confirmation_ids=self.confirmation_ids,
            input_request=self.input_request,
            control_next=self.control_next,
            control_outcome=self.control_outcome,
            dependency_task_ids=self.dependency_task_ids,
        )
