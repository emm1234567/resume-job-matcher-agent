"""结构化抽取器：把简历/JD 原文转为 Pydantic 对象。

通过 LLMClient.chat_structured 强制结构化输出，并保留 raw_text 供后续 RAG 与校验。
"""
from __future__ import annotations

from llm.client import LLMClient
from schemas.resume import Resume
from schemas.job import JobDescription


_RESUME_SYSTEM = """你是一名严谨的简历解析专家。请从用户提供的简历文本中抽取结构化信息：
- 只能基于文本中真实存在的内容抽取，不可臆测或补全；
- 缺失字段留空字符串或空数组，不要编造；
- 技能年限尽量根据经历时间合理推断并填入 years；
- achievements/highlights 提取为简洁的字符串列表，保留量化指标。"""

_JD_SYSTEM = """你是一名招聘需求解析专家。请从用户提供的岗位描述文本中抽取结构化信息：
- 区分硬性要求（hard_requirements，技能/工具/语言，标 must 或 nice_to_have）与软性要求（soft_requirements）；
- min_years 体现最低年限要求，无则填 0；
- responsibilities 抽取为简洁列表；
- 只基于文本内容，不要编造未提及的要求。"""


class Extractor:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def extract_resume(self, text: str) -> Resume:
        """解析简历文本为 Resume 结构。"""
        user = f"请解析以下简历文本：\n\n{text}"
        resume = self.llm.chat_structured(_RESUME_SYSTEM, user, Resume)
        # 保留清洗后原文，供 RAG 检索与幻觉校验
        resume.raw_text = text
        return resume

    def extract_jd(self, text: str) -> JobDescription:
        """解析 JD 文本为 JobDescription 结构。"""
        user = f"请解析以下岗位描述文本：\n\n{text}"
        jd = self.llm.chat_structured(_JD_SYSTEM, user, JobDescription)
        jd.raw_text = text
        return jd
