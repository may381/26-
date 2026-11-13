#!/usr/bin/env python3
"""学校模型客户端（qwen3.8-27b）—— 标准库实现，零第三方依赖。

用途：A3 需要模型能力时统一走这里，不要在业务代码里各处拼 HTTP。
实测（2026-10-29）：`10.138.50.151:8000` TCP 可通，`/v1/chat/completions` 返回 200。

启动自检：
    python model_client.py

在代码里用：
    from model_client import ModelClient, ModelError
    client = ModelClient()
    text = client.chat([{"role": "user", "content": "把这句话改短：我走四十分钟就累了"}])

环境变量（都有默认值，不配也能跑）：
    MODEL_BASE_URL   默认 http://10.138.50.151:8000
    MODEL_NAME       默认 qwen3.8-27b
    MODEL_TIMEOUT    默认 20 秒
    MODEL_API_KEY    默认空（学校文档说当前不需要）
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE = "http://10.138.50.151:8000"
DEFAULT_MODEL = "qwen3.8-27b"


class ModelError(Exception):
    """模型调用失败。带 kind，方便上层决定怎么跟用户说。"""

    def __init__(self, kind: str, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.kind = kind          # timeout / connect / http / format
        self.status = status
        self.message = message


class ModelClient:
    def __init__(self, base_url: str | None = None, model: str | None = None,
                 timeout: float | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("MODEL_BASE_URL") or DEFAULT_BASE).rstrip("/")
        self.model = model or os.environ.get("MODEL_NAME") or DEFAULT_MODEL
        self.timeout = float(timeout if timeout is not None
                             else os.environ.get("MODEL_TIMEOUT") or 20)
        self.api_key = api_key if api_key is not None else os.environ.get("MODEL_API_KEY", "")

    # ---------- 对外 ----------
    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.3,
             max_tokens: int | None = None) -> str:
        """发一轮对话，返回 choices[0].message.content。

        失败一律抛 ModelError，**不返回假内容、不返回空字符串冒充成功**。
        上层要做的就是如实告诉用户「模型暂时用不了」，而不是编一段话。
        """
        if not messages or not isinstance(messages, list):
            raise ModelError("format", "messages 必须是非空列表")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except TimeoutError as error:
            raise ModelError("timeout", f"模型响应超时（{self.timeout}s）：{error}") from error
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:200]
            raise ModelError("http", f"模型返回 HTTP {error.code}：{detail}", error.code) from error
        except urllib.error.URLError as error:
            raise ModelError("connect", f"连不上模型服务 {self.base_url}：{error.reason}") from error
        except OSError as error:
            raise ModelError("connect", f"网络异常：{error}") from error

        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise ModelError("format", f"模型返回结构不对（前 200 字）：{raw[:200]}") from error

        if not isinstance(content, str) or not content.strip():
            raise ModelError("format", "模型返回了空内容")
        return content.strip()

    def health(self) -> dict[str, Any]:
        """自检：发一个最小请求，返回耗时与模型原话。"""
        started = time.time()
        text = self.chat([{"role": "user", "content": "回复两个字：收到"}], temperature=0)
        return {"ok": True, "endpoint": self.endpoint, "model": self.model,
                "elapsedMs": int((time.time() - started) * 1000), "reply": text}


def _selftest() -> int:
    client = ModelClient()
    print(f"目标：{client.endpoint}")
    print(f"模型：{client.model}   超时：{client.timeout}s")
    print("-" * 46)
    try:
        result = client.health()
    except ModelError as error:
        print(f"[FAIL] {error.kind}：{error.message}")
        print()
        print("排查顺序：")
        print("  1) 是不是在校内网 / 连没连学校 VPN（10.138.x.x 是内网地址）")
        print("  2) 换一台机器试，确认是网络问题还是本机问题")
        print("  3) 端口 8000 单独测：Test-NetConnection 10.138.50.151 -Port 8000")
        return 1

    print(f"[PASS] HTTP 通，耗时 {result['elapsedMs']} ms，模型回了：{result['reply']}")
    print()
    print("再做一次真实用途的调用（把口语变短）：")
    try:
        text = client.chat([
            {"role": "system", "content": "你是给老人播报的助手，回答不超过30个字，口语化。"},
            {"role": "user", "content": "我走四十分钟就累了，最好别走台阶"},
        ])
        print(f"  → {text}")
    except ModelError as error:
        print(f"  [FAIL] {error.kind}：{error.message}")
        return 1

    print()
    print("结论：模型可用。业务里请把异常翻译成「模型暂时用不了」，不要编内容。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
