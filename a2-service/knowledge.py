"""A2 本地知识库（RAG 检索，不依赖 P2）。

设计目标（在「只负责 A2、不碰 P2」前提下）：
- 让 A2 的回复能「按知识库回答」，而不是只靠大模型凭记忆瞎编。
- 使用 sklearn 的 TF-IDF（项目已装）做中文友好的向量检索，零额外依赖。
- 知识源放在 knowledge_base/ 目录下的 .txt 文件；当前为占位示例，
  后续由业务方替换为真实「品牌规则 / 景区无障碍资料」。

注意：这是本地轻量 RAG，不是向量数据库级别的语义检索；
竞赛演示足够，若需更强语义可后续换 sentence-transformers + FAISS。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional

import numpy as np

logger = logging.getLogger("a2")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    _SKLEARN_OK = True
except Exception as exc:  # pragma: no cover - 依赖缺失时优雅降级
    logger.warning("sklearn 不可用，RAG 检索降级为关键词匹配：%s", exc)
    _SKLEARN_OK = False


def _split_chunks(text: str) -> List[str]:
    """按空行分段，去掉过短片段，保留可读的知识块。"""
    chunks: List[str] = []
    for part in re.split(r"\n\s*\n", text):
        clean = re.sub(r"\s+", " ", part).strip()
        if len(clean) >= 8:
            chunks.append(clean)
    return chunks


class KnowledgeBase:
    """本地知识检索（TF-IDF + 余弦相似度）。"""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or (Path(__file__).parent / "knowledge_base"))
        self._docs: List[str] = []
        self._src: List[str] = []  # 来源文件名，便于溯源
        self._vec = None
        self._matrix = None
        self._ready = False
        self._load()

    def _load(self) -> None:
        if not self.base_dir.exists():
            logger.warning("知识库目录不存在：%s，RAG 将无结果", self.base_dir)
            return
        for path in sorted(self.base_dir.glob("*.txt")):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("读取知识文件失败 %s：%s", path, exc)
                continue
            for chunk in _split_chunks(text):
                self._docs.append(chunk)
                self._src.append(path.name)
        if not self._docs:
            logger.warning("知识库为空（目录 %s 下无可用 .txt）", self.base_dir)
            return
        if _SKLEARN_OK:
            # char_wb + (1,2) n-gram 对中文友好，无需分词库
            self._vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 2))
            self._matrix = self._vec.fit_transform(self._docs)
        self._ready = True
        logger.info("知识库加载完成：%d 个知识块，来源 %s", len(self._docs), sorted(set(self._src)))

    @property
    def ready(self) -> bool:
        return self._ready

    def search(self, query: str, top_k: int = 3) -> List[dict]:
        """返回与 query 最相关的知识块列表（含来源与得分）。"""
        if not self._ready or not query or not query.strip():
            return []
        if _SKLEARN_OK and self._vec is not None:
            q = self._vec.transform([query])
            sims = cosine_similarity(q, self._matrix).flatten()
            idx = np.argsort(-sims)[:top_k]
            return [
                {"text": self._docs[i], "source": self._src[i], "score": float(sims[i])}
                for i in idx
                if sims[i] > 0.05
            ]
        # 降级：关键词包含匹配
        hits = [d for d in self._docs if query in d]
        return [{"text": h, "source": self._src[i], "score": 1.0}
                for i, h in enumerate(hits)][:top_k]


# 全局单例（进程内只加载一次，等价于缓存）
_kb_instance: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase()
    return _kb_instance


def retrieve(query: str, top_k: int = 3) -> List[dict]:
    """便捷函数：检索知识库。"""
    return get_knowledge_base().search(query, top_k=top_k)
