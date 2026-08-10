"""PDF 解析器，基于 pdfplumber。

选择 pdfplumber 而非 PyPDF2：对中文 PDF 与表格布局的文本抽取质量更稳定。
"""
from __future__ import annotations

import pdfplumber

class PdfParser:
    def parse(self, path: str) -> str:
        pages_text: list[str] = []
        # 使用上下文管理器确保文件句柄及时释放
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                # extract_text 对扫描件（无文字层）返回 None
                page_text = page.extract_text() or ""
                pages_text.append(page_text)
        return "\n".join(pages_text)
