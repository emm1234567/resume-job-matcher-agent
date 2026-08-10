"""简历检索器：支持 Embedding 语义召回与 BM25 关键词召回，并提供多路召回接口。"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from llm.client import LLMClient
from .indexer import Chunk
from .tokenizer import tokenize


class ResumeRetriever:
    """对简历片段建立索引，按 Query 召回相关片段。

    优先使用 Embedding 余弦相似度；若 Embedding 不可用则自动降级为 BM25。
    """

    def __init__(self, chunks: List[Chunk], llm: LLMClient):
        self.chunks = chunks
        self.llm = llm
        self._embeddings: Optional[np.ndarray] = None
        self._bm25 = None
        self._mode = "none"

        if not chunks:
            return

        # 尝试 Embedding
        embeddings = llm.embed([c.text for c in chunks])
        if embeddings:
            arr = np.array(embeddings, dtype=float)
            # 行归一化，便于用内积直接算余弦
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._embeddings = arr / norms
            self._mode = "embedding"
        else:
            # 降级到 BM25
            from rank_bm25 import BM25Okapi

            tokenized = [tokenize(c.text) for c in chunks]
            self._bm25 = BM25Okapi(tokenized)
            self._mode = "bm25"

    @property
    def mode(self) -> str:
        return self._mode

    def retrieve(self, query: str, top_k: int = 5) -> List[Chunk]:
        """单路召回：返回与 query 最相关的 top_k 个片段。"""
        if not self.chunks:
            return []
        top_k = min(top_k, len(self.chunks))

        if self._mode == "embedding":
            return self._retrieve_embedding(query, top_k)
        if self._mode == "bm25":
            return self._retrieve_bm25(query, top_k)
        return []

    def _retrieve_embedding(self, query: str, top_k: int) -> List[Chunk]:
        q_emb = self.llm.embed([query])
        if not q_emb:
            # Embedding 调用失败，回退 BM25
            if self._bm25 is None:
                from rank_bm25 import BM25Okapi
                tokenized = [tokenize(c.text) for c in self.chunks]
                self._bm25 = BM25Okapi(tokenized)
                self._mode = "bm25"
            return self._retrieve_bm25(query, top_k)

        q = np.array(q_emb[0], dtype=float)
        norm = np.linalg.norm(q) or 1.0
        q = q / norm
        scores = self._embeddings @ q  # 余弦相似度
        idx = np.argsort(-scores)[:top_k]
        return [self.chunks[i] for i in idx]

    def _retrieve_bm25(self, query: str, top_k: int) -> List[Chunk]:
        scores = self._bm25.get_scores(tokenize(query))
        # argsort 降序取前 top_k
        idx = np.argsort(-scores)[:top_k]
        # 过滤得分为 0 的无效结果
        return [self.chunks[i] for i in idx if scores[i] > 0]

    def multi_retrieve(self, queries: List[str], top_k: int = 3) -> List[Chunk]:
        """多路召回：对多个 query 分别召回，去重并按出现频次+来源数排序。

        这是本项目的核心 RAG 亮点——以 JD 的每个维度（技能/职责）作为独立 query，
        汇总相关经验，避免单次检索只能覆盖单一维度的信息损失。
        """
        if not self.chunks or not queries:
            return []

        score_map: dict[int, float] = {}
        for q in queries:
            hits = self.retrieve(q, top_k=top_k)
            for rank, chunk in enumerate(hits):
                # 命中越靠前权重越高；多次命中累加
                bonus = (top_k - rank)
                score_map[chunk.index] = score_map.get(chunk.index, 0.0) + bonus

        # 按累计分数降序
        ordered_idx = sorted(score_map.keys(), key=lambda i: score_map[i], reverse=True)
        return [self.chunks[i] for i in ordered_idx]
