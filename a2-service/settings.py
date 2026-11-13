# -*- coding: utf-8 -*-
"""
settings.py —— A2 服务配置层（方案 B：配置与代码分离）
====================================================
所有密钥 / 超时 / 地址 / 模型名都从这里读取，支持「环境变量 > .env 文件 > 内置默认」。
这样切换「真实 LLM / mock」、改端口、改密钥都不需要动业务代码，只改 .env 或环境变量。

.env 文件路径优先级：
  1. 环境变量 P2_ENV_FILE 显式指定的路径
  2. 同目录下的 .env
  3. 向上两级找到「后端代码/silver-travel-avatar/p2-backend/.env」（借用 P2 已配好的 AGENT_A2_API_KEY）
"""
import os
from pathlib import Path

_BASE = Path(__file__).resolve().parent


def load_env_file(path: Path) -> dict:
    """极简 .env 解析：key=value，忽略空行与 # 注释。"""
    env = {}
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if sep and key.strip():
                env.setdefault(key.strip(), value.strip())
    return env


# 1) 显式 P2_ENV_FILE > 2) 同目录 .env > 3) P2 仓库里的 .env
_env_path = os.environ.get("P2_ENV_FILE")
if _env_path:
    ENV = load_env_file(Path(_env_path))
elif (_BASE / ".env").exists():
    ENV = load_env_file(_BASE / ".env")
else:
    _p2_env = _BASE.parents[1] / "后端代码" / "silver-travel-avatar" / "p2-backend" / ".env"
    ENV = load_env_file(_p2_env)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key) or ENV.get(key, default)


class Settings:
    """集中配置对象。业务代码统一从 settings.xxx 读取。"""

    # ---- 身份与回调 ----
    A2_API_KEY: str = _get("A2_API_KEY") or _get("AGENT_A2_API_KEY", "")
    LISTEN_HOST: str = _get("A2_HOST", "127.0.0.1")
    LISTEN_PORT: int = int(_get("A2_PORT", "18002"))

    # P2 内部回调基地址（A2 调 P2 工具时用）
    P2_BASE_URL: str = _get("P2_BASE_URL", _get("AGENT_CALLBACK_BASE_URL", "http://127.0.0.1:8080")).rstrip("/")

    # ---- 领域标识（与 P2 调度一致，a2 固定 care 域）----
    A2_INTENT: str = _get("A2_INTENT", "care")
    A2_DOMAINS: list = [s.strip() for s in _get("A2_DOMAINS", "care").split(",") if s.strip()]

    # ---- 统一大模型（校内 qwen，免 Key）----
    LLM_BASE_URL: str = _get("A2_LLM_BASE_URL", "http://10.138.50.151:8000").rstrip("/")
    LLM_API_KEY: str = _get("A2_LLM_API_KEY", "")
    LLM_MODEL: str = _get("A2_LLM_MODEL", "qwen3.8-27b")
    LLM_TIMEOUT: float = float(_get("A2_LLM_TIMEOUT", "20"))
    # 设为 false 可强制走规则兜底（调试 / 离线演示）
    LLM_ENABLED: bool = _get("A2_LLM_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    # 竞赛级韧性：外部大模型是抖动依赖，瞬时网络错误最多重试次数与退避秒数
    LLM_MAX_RETRIES: int = int(_get("A2_LLM_MAX_RETRIES", "2"))
    LLM_RETRY_BACKOFF: float = float(_get("A2_LLM_RETRY_BACKOFF", "1.0"))
    # ⑦ 模型路由：主模型失败后（重试耗尽）可切到的备用模型（同基地址，不同 model 名）；留空则不切换
    LLM_MODEL_SECONDARY: str = _get("A2_LLM_MODEL_SECONDARY", "")
    # ⑦ 缓存降本：相同 (intent+文本) 命中则直接返回，省 LLM 调用
    CACHE_ENABLED: bool = _get("A2_CACHE_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    CACHE_TTL: int = int(_get("A2_CACHE_TTL", "300"))

    # ---- 回执持久化（sqlite，重启不丢）----
    DB_PATH: str = _get("A2_DB_PATH", str(_BASE / "a2_receipts.db"))

    # ---- 日志（竞赛级：结构化，替代散落的 print）----
    LOG_LEVEL: str = _get("A2_LOG_LEVEL", "INFO")
    LOG_FILE: str = _get("A2_LOG_FILE", str(_BASE / "a2_service.log"))

    # ---- system prompt 外部文件（可改，不必动代码）----
    PROMPT_FILE: Path = Path(_get("A2_SYSTEM_PROMPT_FILE", str(_BASE / "prompts" / "system_prompt.txt")))

    def require_key(self) -> None:
        if len(self.A2_API_KEY) < 16:
            raise SystemExit("缺少有效的 A2_API_KEY / AGENT_A2_API_KEY（长度需 >= 16）。")

    def setup_logging(self) -> None:
        """结构化日志：控制台 + 文件（utf-8），统一格式。替代散落的 print。"""
        import logging
        handlers = [logging.StreamHandler()]
        try:
            handlers.append(logging.FileHandler(self.LOG_FILE, encoding="utf-8"))
        except Exception:
            pass
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=handlers,
            force=True,
        )


settings = Settings()
