"""Agent 编排层：串联解析 -> 抽取 -> RAG -> 匹配 -> 校验 -> 面试准备的完整流水线。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.extractor import Extractor
from core.interview import InterviewPrep
from core.matcher import Matcher
from core.verifier import Verifier
from llm.client import LLMClient
from parsers.base import parse_document
from schemas.job import JobDescription
from schemas.match import MatchResult
from schemas.resume import Resume


@dataclass
class AgentReport:
    """Agent 最终产出：包含结构化简历、JD、匹配报告。"""

    resume: Resume
    job: JobDescription
    result: MatchResult

    def to_json(self, indent: int = 2) -> str:
        """序列化为对外 JSON（raw_text 已通过 exclude=True 自动排除）。"""
        import json
        return json.dumps(
            {
                "resume": self.resume.model_dump(),
                "job": self.job.model_dump(),
                "match": self.result.model_dump(),
            },
            ensure_ascii=False,
            indent=indent,
        )


class ResumeJobMatcherAgent:
    """简历-岗位匹配 Agent。"""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()
        self.extractor = Extractor(self.llm)
        self.matcher = Matcher(self.llm)
        self.verifier = Verifier(self.llm)
        self.interview = InterviewPrep(self.llm)

    def run(self, resume_path: str, jd_path: str, verbose: bool = False) -> AgentReport:
        """执行完整评估流水线。

        参数:
            resume_path: 简历文件路径（PDF/Word/TXT）
            jd_path: JD 文件路径（PDF/Word/TXT）
            verbose: 是否在 stderr 打印阶段进度
        """
        import sys

        def _log(msg: str):
            if verbose:
                print(f"[Agent] {msg}", file=sys.stderr)

        # 1. 文档解析
        _log("解析简历文档...")
        resume_text = parse_document(resume_path)
        _log("解析 JD 文档...")
        jd_text = parse_document(jd_path)

        # 2. 结构化抽取
        _log("结构化抽取简历...")
        resume = self.extractor.extract_resume(resume_text)
        _log(f"抽取完成：{resume.personal_info.name or '未知候选人'}，"
             f"{len(resume.work_experiences)} 段工作经历，{len(resume.skills)} 项技能")

        _log("结构化抽取 JD...")
        jd = self.extractor.extract_jd(jd_text)
        _log(f"JD 抽取完成：{jd.title}，{len(jd.hard_requirements)} 项硬性要求")

        # 3. RAG + 匹配评分
        _log("多路 RAG 召回与匹配评分...")
        result = self.matcher.match(resume, jd)
        _log(f"匹配评分完成：总分 {result.overall_score:.1f}")

        # 4. 幻觉校验
        _log("幻觉校验中...")
        result.verification_issues = self.verifier.verify(result, resume)
        fabricated = sum(1 for i in result.verification_issues if i.status == "fabricated")
        if fabricated:
            _log(f"警告：检测到 {fabricated} 条疑似捏造结论，请人工复核")

        # 5. 面试准备
        _log("生成定制面试题...")
        result.interview_questions = self.interview.generate(resume, jd, result)
        _log(f"生成 {len(result.interview_questions)} 道面试题")

        return AgentReport(resume=resume, job=jd, result=result)
