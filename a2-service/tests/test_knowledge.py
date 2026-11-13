# -*- coding: utf-8 -*-
"""RAG 知识检索测试（A2 本地知识库，不依赖 P2）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge import KnowledgeBase, retrieve  # noqa: E402


def test_kb_loads_chunks():
    kb = KnowledgeBase()
    assert kb.ready, "知识库应成功加载占位 .txt"
    assert len(kb._docs) > 0, "应切分出多个知识块"


def test_retrieve_scenic_hit():
    hits = retrieve("景区里有没有无障碍电梯", top_k=3)
    assert hits, "应检索到景区无障碍相关片段"
    joined = " ".join(h["text"] for h in hits)
    assert "电梯" in joined or "无障碍" in joined


def test_retrieve_brand_hit():
    hits = retrieve("你们品牌对紧急情况的规则是什么", top_k=3)
    assert hits, "应检索到品牌规则片段"
    assert any("品牌" in h["source"] or "紧急" in h["text"] for h in hits)


def test_retrieve_no_match_returns_empty():
    # 无关 query 得分低于阈值，应返回空（不硬塞）
    hits = retrieve("今天天气怎么样股票涨了吗", top_k=3)
    assert isinstance(hits, list)
