# -*- coding: utf-8 -*-
"""
cache.py —— A2 回复缓存（竞赛级：降本）
======================================
- 按 (intent + 归一化文本) 哈希做 TTL 缓存，相同问法直接命中，省去重复 LLM 调用。
- 进程内 dict + 线程锁（单实例足够；如需分布式可换 Redis，接口不变）。
- 缓存只存「回复文本 + 语速」，组装结果单时再用当前请求的 meta 回填 14 字段，
  避免缓存串用旧的 invocationId。
"""
import hashlib
import threading
import time
from typing import Optional, Tuple

from settings import settings


class CacheStore:
    def __init__(self, ttl: int = 300, enabled: bool = True):
        self.ttl = ttl
        self.enabled = enabled
        self._d: dict = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(intent: str, text: str) -> str:
        norm = (text or "").strip().lower()
        raw = "%s|%s" % (intent, norm)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, intent: str, text: str) -> Optional[Tuple[str, float]]:
        if not self.enabled:
            return None
        k = self._key(intent, text)
        with self._lock:
            v = self._d.get(k)
            if not v:
                return None
            expire, val = v
            if expire < time.time():
                self._d.pop(k, None)
                return None
            return val

    def set(self, intent: str, text: str, reply_text: str, speech_rate: float) -> None:
        if not self.enabled:
            return
        k = self._key(intent, text)
        with self._lock:
            self._d[k] = (time.time() + self.ttl, (reply_text, speech_rate))

    def clear(self) -> None:
        with self._lock:
            self._d.clear()


# 加载配置即实例化（settings 为单例，已在导入时解析 .env）
cache = CacheStore(
    ttl=int(getattr(settings, "CACHE_TTL", 300)),
    enabled=str(getattr(settings, "CACHE_ENABLED", "true")).lower() in ("1", "true", "yes", "on"),
)
