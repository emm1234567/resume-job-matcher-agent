"""幻觉校验器：核对匹配报告中的结论是否有简历原文支撑。

机制（企业级关键点）：
1. 从 MatchResult 中抽取“可证伪断言”（技能 evidence、优势、总结性结论）。
2. 对每个断言，用关键词从简历原文检索候选证据片段。
3. 让 LLM 在“仅依据给定证据”的前提下判定：
   - supported：证据足以支撑断言；
   - unsupported：简历中找不到对应证据；
   - fabricated：断言明显超出/违背简历内容（疑似夸大或捏造）。
4. 将校验问题回填到 MatchResult.verification_issues，供用户复核。

这有效约束了模型“凭空夸大”的倾向，是简历场景下的可信度保障。
"""
from __future__ import annotations

import json
from typing import List

from llm.client import LLMClient
from rag.tokenizer import tokenize
from schemas.match import MatchResult, VerificationIssue
from schemas.resume import Resume


_VERIFY_SYSTEM = """你是一名严格的简历事实核查员。给定【待核查断言】与【简历证据片段】，
请判断断言是否被证据支撑。规则：
- 只能依据给出的证据片段判断，不得引入外部知识；
- status 取值：supported（证据充分支撑）/ unsupported（证据不足或未提及）/ fabricated（断言明显夸大、与简历矛盾或疑似捏造）；
- note 简述判定理由；evidence_found 引用证据原文关键句，无则留空。"""


def _retrieve_evidence(resume: Resume, claim: str, window: int = 120) -> str:
    """基于断言关键词，在简历原文中检索包含命中词的句子片段。"""
    raw = resume.raw_text or ""
    if not raw or not claim:
        return ""
    tokens = [t for t in tokenize(claim) if len(t) > 1]
    if not tokens:
        return ""

    sentences = [s.strip() for s in raw.replace("\n", "。").split("。") if s.strip()]
    scored: List[tuple[float, str]] = []
    for sent in sentences:
        hits = sum(1 for t in tokens if t in sent.lower())
        if hits > 0:
            scored.append((hits, sent))
    scored.sort(key=lambda x: x[0], reverse=True)
    # 取前 3 条最相关句子作为证据
    return " | ".join(s for _, s in scored[:3])


def _extract_claims(result: MatchResult) -> List[str]:
    """从匹配报告中抽取需要核查的断言。"""
    claims: List[str] = []
    for sm in result.skill_matches:
        if sm.candidate_years and sm.candidate_years > 0 or sm.status.value == "met":
            claims.append(f"具备 {sm.skill} 能力，年限约 {sm.candidate_years} 年")
    for st in result.strengths:
        claims.append(st)
    if result.summary:
        claims.append(result.summary)
    return claims


class Verifier:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def verify(self, result: MatchResult, resume: Resume) -> List[VerificationIssue]:
        """对匹配报告中的断言逐条核查，返回校验问题列表。"""
        claims = _extract_claims(result)
        if not claims:
            return []

        issues: List[VerificationIssue] = []
        for claim in claims:
            evidence = _retrieve_evidence(resume, claim)
            payload = {
                "claim": claim,
                "evidence": evidence or "(简历中未检索到相关内容)",
            }
            user = (
                "请核查以下断言是否被简历证据支撑：\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            )
            try:
                issue = self.llm.chat_structured(_VERIFY_SYSTEM, user, VerificationIssue)
                # 强制以本地检索结果覆盖模型自填证据，避免模型自行编造证据
                issue.evidence_found = evidence
                issues.append(issue)
            except Exception:
                # 单条校验失败不阻断整体流程，标记为 unsupported
                issues.append(VerificationIssue(
                    claim=claim,
                    evidence_found=evidence,
                    status="unsupported",
                    note="校验调用失败，默认标记为无据",
                ))
        return issues
