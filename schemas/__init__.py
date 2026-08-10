"""结构化数据模型包。

利用 Pydantic v2 强制 LLM 输出标准结构，避免自由文本带来的解析不确定性与幻觉。
"""
from .resume import Resume, PersonalInfo, Education, WorkExperience, ProjectExperience, Skill, LanguageSkill
from .job import JobDescription, JobRequirement
from .match import (
    MatchResult,
    SkillMatch,
    DimensionScore,
    ImprovementSuggestion,
    InterviewQuestion,
    VerificationIssue,
    MatchStatus,
)

__all__ = [
    "Resume", "PersonalInfo", "Education", "WorkExperience", "ProjectExperience",
    "Skill", "LanguageSkill",
    "JobDescription", "JobRequirement",
    "MatchResult", "SkillMatch", "DimensionScore", "ImprovementSuggestion",
    "InterviewQuestion", "VerificationIssue", "MatchStatus",
]
