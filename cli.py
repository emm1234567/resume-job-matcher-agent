"""命令行入口。

用法:
    python cli.py --resume <简历路径> --jd <JD路径> [--output report.json] [--verbose]

示例:
    python cli.py --resume sample_data/sample_resume.txt --jd sample_data/sample_jd.txt -v
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent import ResumeJobMatcherAgent


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="简历解析与岗配评估 Agent：结构化抽取 + 多维度 RAG + 幻觉校验"
    )
    parser.add_argument("--resume", required=True, help="简历文件路径（PDF/Word/TXT）")
    parser.add_argument("--jd", required=True, help="岗位描述文件路径（PDF/Word/TXT）")
    parser.add_argument("--output", "-o", default=None, help="评估报告输出 JSON 路径；不填则仅打印")
    parser.add_argument("--verbose", "-v", action="store_true", help="打印阶段进度到 stderr")
    return parser


def main(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        agent = ResumeJobMatcherAgent()
        report = agent.run(args.resume, args.jd, verbose=args.verbose)
    except Exception as e:
        print(f"[错误] 评估失败：{e}", file=sys.stderr)
        return 2

    # 人类可读摘要
    r = report.result
    print("=" * 60)
    print(f"候选人：{report.resume.personal_info.name or '未知'}")
    print(f"目标岗位：{report.job.title}")
    print(f"匹配总分：{r.overall_score:.1f} / 100")
    print("-" * 60)
    print("维度评分：")
    for d in r.dimension_scores:
        print(f"  - {d.dimension:<10}: {d.score:>5.1f} (权重 {d.weight})  {d.detail}")
    print("-" * 60)
    print("技能匹配：")
    for s in r.skill_matches:
        flag = "✓" if s.status.value == "met" else ("△" if s.status.value == "partial" else "✗")
        print(f"  {flag} {s.skill:<20} 要求{s.required_years}年 / 候选{s.candidate_years}年 [{s.status.value}]")
    print("-" * 60)
    print(f"幻觉校验：{len(r.verification_issues)} 条断言已核查，"
          f"其中 {sum(1 for i in r.verification_issues if i.status=='fabricated')} 条疑似捏造")
    print("-" * 60)
    print("改进建议：")
    for s in r.improvement_suggestions:
        print(f"  [{s.priority}] {s.area}：{s.suggested}")
    print("-" * 60)
    print(f"定制面试题（共 {len(r.interview_questions)} 道）：")
    for i, q in enumerate(r.interview_questions, 1):
        print(f"  {i}. [{q.category}/{q.difficulty}] {q.question}")
        if q.rationale:
            print(f"     出题依据：{q.rationale}")
    print("=" * 60)

    # 结构化 JSON 输出
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(report.to_json(), encoding="utf-8")
        print(f"\n结构化报告已写入：{out_path}", file=sys.stderr)

    # 同时输出纯 JSON 到 stdout 便于管道处理（可选）
    return 0


if __name__ == "__main__":
    sys.exit(main())
