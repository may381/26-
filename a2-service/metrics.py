# -*- coding: utf-8 -*-
"""
metrics.py —— A2 可观测性指标（竞赛级：留痕）
============================================
- 线程安全计数器 + 延迟累计 + 按 intent 维度拆分。
- 不依赖外部采集组件：暴露 /metrics 端点 + 结构化日志即可对接 Prometheus/ELK。
- 指标在 agent_logic 各关键节点埋点，main.py 每次派活后记录结构化日志并供 /metrics 查询。
"""
import threading
from typing import Any, Dict


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.counters = {
            "requests_total": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "llm_calls": 0,
            "llm_ok": 0,
            "llm_fail": 0,
            "guardrail_input_flagged": 0,
            "guardrail_output_flagged": 0,
            "tool_calls": 0,
            "refusals": 0,
        }
        self.latency_ms_total = 0.0
        self.by_intent: Dict[str, int] = {}

    def inc(self, key: str, n: int = 1) -> None:
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + n

    def add_latency(self, ms: float) -> None:
        with self._lock:
            self.latency_ms_total += ms

    def record_intent(self, intent: str) -> None:
        with self._lock:
            self.by_intent[intent] = self.by_intent.get(intent, 0) + 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            out = dict(self.counters)
            out["latency_ms_total"] = round(self.latency_ms_total, 1)
            out["requests_handled"] = self.counters["requests_total"]
            out["by_intent"] = dict(self.by_intent)
            # 派生指标：缓存命中率、LLM 成功率
            hits = self.counters["cache_hits"]
            misses = self.counters["cache_misses"]
            out["cache_hit_rate"] = round(hits / (hits + misses), 3) if (hits + misses) else 0.0
            ok = self.counters["llm_ok"]
            tot = self.counters["llm_calls"]
            out["llm_success_rate"] = round(ok / tot, 3) if tot else 0.0
            return out

    def reset(self) -> None:
        with self._lock:
            for k in self.counters:
                self.counters[k] = 0
            self.latency_ms_total = 0.0
            self.by_intent.clear()


metrics = Metrics()
