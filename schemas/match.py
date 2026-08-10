"""岗位匹配结果模型。

包含：维度评分、技能匹配明细、差距分析、改进建议、定制面试题、幻觉校验问题。
这是整个 Agent 对外输出的最终标准结构。
"""
from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class MatchStatus(str, Enum):
    """单项技能匹配状态。使用 str+Enum 便于 JSON 序列化。"""

    MET = "met"            # 满足要求
    PARTIAL = "partial"    # 部分满足（年限不足或有技能但深度不够）
    MISSING = "missing"    # 完全缺失
    EXCEEDED = "exceeded"  # 超出要求


class SkillMatch(BaseModel):
    skill: str
    required: bool = Field(..., description="是否为必须项")
    required_years: float = 0.0
    candidate_years: float = 0.0
    candidate_level: str = ""
    status: MatchStatus = MatchStatus.MISSING
    evidence: str = Field("", description="简历中支撑该判断的原文片段；空表示无证据")


class DimensionScore(BaseModel):
    """单维度评分。维度如：技能契合、经验年限、项目相关性、学历、语言。"""

    dimension: str
    score: float = Field(..., ge=0, le=100, description="0~100")
    weight: float = Field(1.0, ge=0, le=1)
    detail: str = Field("", description="评分依据说明")


class ImprovementSuggestion(BaseModel):
    area: str = Field(..., description="建议改进的方面，如 简历表达/技能补充")
    current: str = Field("", description="当前问题")
    suggested: str = Field("", description="具体建议")
    priority: str = Field("medium", description="high/medium/low")


class InterviewQuestion(BaseModel):
    question: str
    category: str = Field("technical", description="technical/behavioral/system_design")
    difficulty: str = Field("medium", description="easy/medium/hard")
    expected_topics: List[str] = Field(default_factory=list, description="期望覆盖的知识点")
    rationale: str = Field("", description="为什么问这道题（结合 JD/简历）")


class VerificationIssue(BaseModel):
    """幻觉校验条目：检查匹配报告中每条结论是否有简历原文支撑。"""

    claim: str = Field(..., description="被校验的断言，如 '熟练使用 Kafka'")
    evidence_found: str = Field("", description="在简历中检索到的证据原文；无则填空")
    status: str = Field(..., description="supported（有据）/ unsupported（无据）/ fabricated（疑似捏造）")
    note: str = ""


class MatchResult(BaseModel):
    """最终匹配报告。"""

    overall_score: float = Field(..., ge=0, le=100)
    dimension_scores: List[DimensionScore] = Field(default_factory=list)
    skill_matches: List[SkillMatch] = Field(default_factory=list)
    gap_analysis: str = Field("", description="整体差距分析")
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    improvement_suggestions: List[ImprovementSuggestion] = Field(default_factory=list)
    interview_questions: List[InterviewQuestion] = Field(default_factory=list)
    verification_issues: List[VerificationIssue] = Field(default_factory=list)
    summary: str = Field("", description="一句话总体结论")
