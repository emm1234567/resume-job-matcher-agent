"""简历结构化模型。

设计要点：
- 每个字段都带 description，作为 JSON Schema 的一部分注入提示词，
  让 LLM 明确每个字段的语义与取值约束，显著降低抽取歧义。
- raw_text 字段标记 exclude=True：保留原文供 RAG 召回与幻觉校验使用，
  但不参与对外序列化输出，避免泄露冗长原文。
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, ConfigDict


class PersonalInfo(BaseModel):
    """个人基本信息。"""

    model_config = ConfigDict(extra="ignore")

    name: str = Field("", description="候选人姓名")
    email: str = Field("", description="电子邮箱")
    phone: str = Field("", description="联系电话")
    location: str = Field("", description="所在城市")


class Education(BaseModel):
    school: str = Field(..., description="学校名称")
    degree: str = Field("", description="学历：大专/本科/硕士/博士")
    major: str = Field("", description="专业")
    start_date: str = Field("", description="开始时间，如 2018-09")
    end_date: str = Field("", description="结束时间，如 2022-06")


class WorkExperience(BaseModel):
    company: str = Field(..., description="公司名称")
    title: str = Field("", description="职位/职级")
    start_date: str = ""
    end_date: str = ""
    description: str = Field("", description="工作内容描述")
    achievements: List[str] = Field(default_factory=list, description="关键成果/量化指标列表")


class ProjectExperience(BaseModel):
    name: str = Field(..., description="项目名称")
    role: str = Field("", description="担任角色")
    tech_stack: List[str] = Field(default_factory=list, description="使用的技术栈")
    description: str = Field("", description="项目简介与个人职责")
    highlights: List[str] = Field(default_factory=list, description="核心亮点/难点/产出")


class Skill(BaseModel):
    name: str = Field(..., description="技能名称，如 Python")
    level: str = Field("", description="熟练度：了解/熟悉/熟练/精通")
    years: float = Field(0.0, ge=0, description="使用年限")


class LanguageSkill(BaseModel):
    name: str = Field(..., description="语言，如 英语")
    proficiency: str = Field("", description="如 CET-6 / 流利 / 母语")


class Resume(BaseModel):
    """完整简历结构。

    raw_text 保存清洗后的原始全文，供 RAG 检索与幻觉校验使用，
    通过 exclude=True 避免出现在最终 JSON 报告中。
    """

    personal_info: PersonalInfo
    educations: List[Education] = Field(default_factory=list)
    work_experiences: List[WorkExperience] = Field(default_factory=list)
    project_experiences: List[ProjectExperience] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)
    languages: List[LanguageSkill] = Field(default_factory=list)
    summary: str = Field("", description="候选人一句话自我评价/概要")
    raw_text: str = Field("", exclude=True, repr=False)
