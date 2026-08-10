"""多维度 RAG 模块。

设计思路（企业级要点）：
- 多路召回：以 JD 的不同维度（每项技能要求、每条职责）作为 Query，
  分别从简历中召回相关片段，避免单次检索信息丢失。
- 双引擎：优先使用 Embedding 语义召回；当 Embedding 服务不可用时自动降级到 BM25，
  保证离线/无 Key 环境下仍可运行。
- 简历切块：按工作经历、项目经历、教育、技能等结构化切分，保留语义完整性，
  提升召回片段的可解释性（每个片段可直接作为证据原文）。
"""
from .tokenizer import tokenize
from .indexer import build_resume_chunks, Chunk
from .retriever import ResumeRetriever

__all__ = ["tokenize", "build_resume_chunks", "Chunk", "ResumeRetriever"]
