"""岗位描述（JD）结构化模型。"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class JobRequirement(BaseModel):
    """单项硬性要求（技能/工具/语言等）。"""

    skill: str = Field(..., description="要求的技能/工具/语言，如 Python")
    requirement_type: str = Field("must", description="must（必须）/ nice_to_have（加分）")
    min_years: float = Field(0.0, ge=0, description="最低使用年限要求，无要求填 0")
    importance: float = Field(1.0, ge=0, le=1, description="该项权重 0~1")


class JobDescription(BaseModel):
    title: str = Field(..., description="岗位名称")
    company: str = Field("", description="公司名称（如 JD 中给出）")
    location: str = Field("", description="工作地点")
    responsibilities: List[str] = Field(default_factory=list, description="岗位职责列表")
    hard_requirements: List[JobRequirement] = Field(default_factory=list, description="硬性技能要求")
    soft_requirements: List[str] = Field(default_factory=list, description="软性要求/加分项")
    min_experience_years: float = Field(0.0, ge=0, description="最低总工作年限")
    language_requirements: List[str] = Field(default_factory=list, description="语言要求")
    seniority: str = Field("", description="资历层级：junior/mid/senior/lead")
    raw_text: str = Field("", exclude=True, repr=False)
