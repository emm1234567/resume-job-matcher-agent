"""面试准备生成器：基于 JD 差距与候选人经验，定制面试问题。

策略：
- 针对 JD 必须项且候选人存在差距/部分满足的技能 -> technical 题；
- 针对候选人亮点项目 -> system_design / 深挖题；
- 针对资历与软性要求 -> behavioral 题；
- 每题给出 rationale 与 expected_topics，便于候选人定向复习。
"""
from __future__ import annotations

import json
from typing import List

from llm.client import LLMClient
from schemas.match import MatchResult, InterviewQuestion
from schemas.resume import Resume
from schemas.job import JobDescription


_INTERVIEW_SYSTEM = """你是一名资深面试官。请结合【岗位要求】与【候选人匹配情况】，生成 6~8 道定制化面试题。
要求：
- technical 题优先覆盖 JD 必须、但候选人部分满足/缺失的技能；
- 至少 1 道 system_design 题（若岗位偏 senior/lead）；
- 至少 1 道 behavioral 题，结合候选人项目亮点或差距；
- difficulty 合理分布；
- rationale 必须说明出题依据（对应 JD 哪条要求或候选人哪段经历）；
- 不得询问简历中完全不存在的细节。"""


class InterviewPrep:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate(
        self, resume: Resume, jd: JobDescription, result: MatchResult
    ) -> List[InterviewQuestion]:
        context = {
            "job": {
                "title": jd.title,
                "seniority": jd.seniority,
                "hard_requirements": [r.model_dump() for r in jd.hard_requirements],
                "responsibilities": jd.responsibilities,
            },
            "candidate_highlights": [
                p.name + ": " + p.description for p in resume.project_experiences
            ][:5],
            "match_summary": {
                "overall_score": result.overall_score,
                "strengths": result.strengths,
                "weaknesses": result.weaknesses,
                "skill_status": [
                    {"skill": s.skill, "status": s.status.value, "years": s.candidate_years}
                    for s in result.skill_matches
                ],
            },
        }
        user = (
            "请基于以下上下文生成定制化面试题：\n\n"
            + json.dumps(context, ensure_ascii=False, indent=2)
        )

        # 复用一个轻量包装模型以承接 list 输出
        from pydantic import BaseModel, Field

        class _Questions(BaseModel):
            questions: List[InterviewQuestion] = Field(default_factory=list)

        wrapped = self.llm.chat_structured(_INTERVIEW_SYSTEM, user, _Questions)
        return wrapped.questions
