"""匹配器：综合规则计算 + LLM 判断 + RAG 证据，输出 MatchResult。

三段式设计（企业级要点）：
1. 规则基线：对技能名/年限做确定性比对，给出客观的 SkillMatch 状态，
   避免完全依赖 LLM 导致结果漂移。
2. 多路 RAG 召回：以 JD 每项技能要求与每条职责作为 Query，从简历中
   召回相关经验片段，作为评分与证据原文。
3. LLM 综合评分：把规则基线 + 召回证据 + 简历/JD 结构喂给模型，
   让其在“有据可依”的前提下输出维度评分、差距分析、改进建议。
"""
from __future__ import annotations

import json
from typing import List

from llm.client import LLMClient
from rag.indexer import build_resume_chunks, Chunk
from rag.retriever import ResumeRetriever
from schemas.resume import Resume
from schemas.job import JobDescription
from schemas.match import (
    MatchResult,
    SkillMatch,
    DimensionScore,
    ImprovementSuggestion,
    MatchStatus,
)


def _norm(s: str) -> str:
    """技能名归一化：去空白、转小写，便于粗匹配。"""
    return (s or "").strip().lower().replace(" ", "")


def _skill_lookup(resume: Resume) -> dict:
    """构建 简历技能名->Skill 的查找表（归一化键）。"""
    table = {}
    for s in resume.skills:
        table[_norm(s.name)] = s
    return table


def _rule_match_skills(resume: Resume, jd: JobDescription) -> List[SkillMatch]:
    """规则化的技能匹配基线。"""
    table = _skill_lookup(resume)
    matches: List[SkillMatch] = []
    for req in jd.hard_requirements:
        key = _norm(req.skill)
        skill = table.get(key)
        if skill is None:
            # 模糊匹配：JD 技能名是否包含于简历某技能名（或反之）
            for k, v in table.items():
                if key and (key in k or k in key):
                    skill = v
                    break
        if skill is None:
            matches.append(SkillMatch(
                skill=req.skill,
                required=(req.requirement_type == "must"),
                required_years=req.min_years,
                candidate_years=0.0,
                candidate_level="",
                status=MatchStatus.MISSING,
                evidence="",
            ))
        else:
            cand_years = skill.years or 0.0
            if req.min_years > 0 and cand_years + 1e-6 < req.min_years:
                status = MatchStatus.PARTIAL
            else:
                status = MatchStatus.MET
            matches.append(SkillMatch(
                skill=req.skill,
                required=(req.requirement_type == "must"),
                required_years=req.min_years,
                candidate_years=cand_years,
                candidate_level=skill.level,
                status=status,
                evidence="",
            ))
    return matches


_MATCH_SYSTEM = """你是一名资深技术招聘评估官。请基于【候选人简历】【岗位要求】【规则匹配基线】【召回证据】
综合给出岗位匹配评估。

硬性要求：
- 评分必须有据可依：技能/经验判断须能在召回证据或简历结构中找到对应支撑；
- 不得夸大候选人能力，不得捏造简历中不存在的经历；
- overall_score 为各维度加权综合，0~100；
- skill_matches 须基于给定的 rule_baseline 补充 evidence（来自召回证据原文片段），状态可校正；
- improvement_suggestions 针对 JD 差距给出可执行建议；
- dimension_scores 至少包含：技能契合、经验年限、项目相关性、学历、语言 五个维度。"""


class Matcher:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def _build_context(self, resume: Resume, jd: JobDescription) -> tuple[ResumeRetriever, List[Chunk], List[SkillMatch]]:
        """构建 RAG 检索器并完成多路召回，返回 (retriever, evidence_chunks, rule_baseline)。"""
        chunks = build_resume_chunks(resume)
        retriever = ResumeRetriever(chunks, self.llm)

        # 多路召回：每项技能要求 + 每条职责 各作为一个 Query
        queries: List[str] = []
        for req in jd.hard_requirements:
            queries.append(f"{req.skill} {req.min_years}年 {' '.join(jd.responsibilities[:2])}")
        for resp in jd.responsibilities:
            queries.append(resp)

        evidence_chunks = retriever.multi_retrieve(queries, top_k=3)
        rule_baseline = _rule_match_skills(resume, jd)
        return retriever, evidence_chunks, rule_baseline

    def match(self, resume: Resume, jd: JobDescription) -> MatchResult:
        retriever, evidence_chunks, rule_baseline = self._build_context(resume, jd)

        evidence_text = "\n---\n".join(
            f"[{c.kind}] {c.text}" for c in evidence_chunks
        ) or "(未召回到相关经验)"

        context = {
            "candidate_summary": {
                "name": resume.personal_info.name,
                "skills": [s.model_dump() for s in resume.skills],
                "work_count": len(resume.work_experiences),
                "project_count": len(resume.project_experiences),
                "total_work_years": _approx_total_years(resume),
                "education": [e.model_dump() for e in resume.educations],
                "languages": [l.model_dump() for l in resume.languages],
            },
            "job": {
                "title": jd.title,
                "seniority": jd.seniority,
                "min_experience_years": jd.min_experience_years,
                "hard_requirements": [r.model_dump() for r in jd.hard_requirements],
                "responsibilities": jd.responsibilities,
                "language_requirements": jd.language_requirements,
            },
            "rule_baseline": [m.model_dump() for m in rule_baseline],
            "rag_evidence": evidence_text,
        }

        user = (
            "请基于以下上下文给出结构化匹配评估（evidence 字段必须引用召回证据或简历中真实内容）：\n\n"
            + json.dumps(context, ensure_ascii=False, indent=2)
        )

        result = self.llm.chat_structured(_MATCH_SYSTEM, user, MatchResult)
        # 若 LLM 未填充 skill_matches，则回填规则基线，保证结果非空
        if not result.skill_matches:
            result.skill_matches = rule_baseline
        return result


def _approx_total_years(resume: Resume) -> float:
    """粗略估算总工作年限（取所有工作经历 years 之和或技能最大年限）。"""
    total = 0.0
    for s in resume.skills:
        if s.years:
            total = max(total, s.years)
    return total
