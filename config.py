"""全局配置模块。

安全说明：
- 所有敏感信息（API Key）仅从环境变量读取，绝不硬编码。
- 通过 python-dotenv 加载项目根目录下的 .env 文件（该文件不应提交到版本库）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env（若存在）。注意：.env 通常应加入 .gitignore，避免泄露密钥
load_dotenv(Path(__file__).resolve().parent / ".env")


def _get_bool(key: str, default: bool) -> bool:
    """安全解析布尔型环境变量。"""
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """应用配置集合。frozen=True 保证运行期不可变，避免被意外篡改。"""

    # 对话模型
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    llm_temperature: float = field(default_factory=lambda: _get_float("LLM_TEMPERATURE", 0.2))

    # Embedding 模型（留空则降级为 BM25）
    embedding_api_key: str = field(default_factory=lambda: os.getenv("EMBEDDING_API_KEY", ""))
    embedding_base_url: str = field(default_factory=lambda: os.getenv("EMBEDDING_BASE_URL", ""))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    enable_embedding_rag: bool = field(default_factory=lambda: _get_bool("ENABLE_EMBEDDING_RAG", True))

    # RAG 召回参数
    retrieval_top_k: int = 5
    # 结构化输出解析失败时的最大重试次数
    structured_max_retries: int = 3

    @property
    def has_llm_key(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def has_embedding_key(self) -> bool:
        return bool(self.embedding_api_key)


settings = Settings()
