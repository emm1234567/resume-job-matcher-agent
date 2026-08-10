"""解析器统一入口与工具函数。

安全说明：
- 对上传文件路径做扩展名白名单校验，限制可解析类型，避免任意文件读取。
- 仅读取本地文件系统；如需接入对象存储，应在此层之上做鉴权。
"""
from __future__ import annotations

from pathlib import Path

# 允许解析的扩展名白名单
_ALLOWED_SUFFIXES = {".pdf", ".docx", ".doc", ".txt"}


def _clean_text(text: str) -> str:
    """清洗文本：去除多余空白行，规范化空白字符。"""
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines()]
    # 合并连续空行为单个空行
    cleaned: list[str] = []
    blank = False
    for line in lines:
        if line:
            cleaned.append(line)
            blank = False
        elif not blank:
            cleaned.append("")
            blank = True
    return "\n".join(cleaned).strip()


def parse_document(path: str) -> str:
    """根据扩展名分发到对应解析器，返回清洗后的纯文本。

    参数:
        path: 文件绝对或相对路径
    返回:
        解析后的纯文本
    异常:
        FileNotFoundError: 文件不存在
        ValueError: 不支持的文件类型
    """
    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"文件不存在或不是普通文件: {path}")

    suffix = p.suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise ValueError(
            f"不支持的文件类型: {suffix}，仅支持 {sorted(_ALLOWED_SUFFIXES)}"
        )

    if suffix == ".pdf":
        from .pdf_parser import PdfParser
        text = PdfParser().parse(str(p))
    elif suffix in (".docx", ".doc"):
        from .docx_parser import DocxParser
        text = DocxParser().parse(str(p))
    else:  # .txt
        # errors="ignore" 容忍少量非法字节；优先按 utf-8 解码
        text = p.read_text(encoding="utf-8", errors="ignore")

    return _clean_text(text)
