"""简历切块：将结构化简历切分为可检索的语义片段。

每个 Chunk 带有 kind 标签（work/project/education/skill/summary），
便于在召回后按维度组织证据，支撑多维度评分与幻觉校验。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from schemas.resume import Resume


@dataclass
class Chunk:
    text: str
    kind: str  # work / project / education / skill / summary
    index: int  # 原始序号

    def __post_init__(self):
        self.text = self.text.strip()


def _fmt_list(items: List[str]) -> str:
    return "；".join(i for i in items if i)


def build_resume_chunks(resume: Resume) -> List[Chunk]:
    """根据结构化简历构建检索片段列表。"""
    chunks: List[Chunk] = []

    if resume.summary:
        chunks.append(Chunk(text=resume.summary, kind="summary", index=len(chunks)))

    for we in resume.work_experiences:
        parts = [
            f"工作经历 @ {we.company} - {we.title}",
            f"时间：{we.start_date} ~ {we.end_date}" if we.start_date or we.end_date else "",
            we.description,
            _fmt_list(we.achievements),
        ]
        chunks.append(Chunk(text="\n".join(p for p in parts if p), kind="work", index=len(chunks)))

    for pe in resume.project_experiences:
        parts = [
            f"项目经历 @ {pe.name} - {pe.role}",
            f"技术栈：{', '.join(pe.tech_stack)}" if pe.tech_stack else "",
            pe.description,
            _fmt_list(pe.highlights),
        ]
        chunks.append(Chunk(text="\n".join(p for p in parts if p), kind="project", index=len(chunks)))

    for ed in resume.educations:
        parts = [
            f"教育经历 @ {ed.school} - {ed.degree} {ed.major}",
            f"时间：{ed.start_date} ~ {ed.end_date}" if ed.start_date or ed.end_date else "",
        ]
        chunks.append(Chunk(text="\n".join(p for p in parts if p), kind="education", index=len(chunks)))

    if resume.skills:
        skill_lines = [f"{s.name}({s.level},{s.years}年)" for s in resume.skills]
        chunks.append(Chunk(text="技能：" + "；".join(skill_lines), kind="skill", index=len(chunks)))

    if resume.languages:
        lang_lines = [f"{l.name}({l.proficiency})" for l in resume.languages]
        chunks.append(Chunk(text="语言：" + "；".join(lang_lines), kind="skill", index=len(chunks)))

    return chunks
