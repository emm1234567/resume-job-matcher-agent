"""分词工具：优先使用 jieba（中文效果好），不可用时降级为正则切分。"""
from __future__ import annotations

import re
from typing import List

try:
    import jieba  # type: ignore

    _HAS_JIEBA = True
except Exception:  # pragma: no cover - 仅在缺失依赖时触发
    _HAS_JIEBA = False

# 降级方案：按中英文词边界与单字切分
_FALLBACK_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fa5]")

def tokenize(text: str) -> List[str]:
    """对文本分词，返回 token 列表（已去空白、转小写）。"""
    if not text:
        return []
    if _HAS_JIEBA:
        return [t.strip().lower() for t in jieba.cut(text) if t.strip()]
    return [t.lower() for t in _FALLBACK_RE.findall(text)]
