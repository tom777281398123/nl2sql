"""Command-line runner for the full NL2SQL LLM-as-Judge evaluation."""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from backend.app.constants.project_constant import PROJECT_ROOT
from backend.app.evaluation.judge import (
    JudgeAvailabilityError,
    JudgeInvocationError,
    invoke_configured_judge,
    run_judge_evaluation,
    verify_judge_availability,
    write_judge_report,
)
from backend.app.evaluation.nl2sql import load_eval_cases
from backend.app.scripts.run_nl2sql_eval import create_query_service


DEFAULT_DATASET_PATH = PROJECT_ROOT / "eval" / "nl2sql_golden.yaml"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "eval" / "reports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行完整链路的 LLM-as-Judge 评测")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--min-judge-pass-rate", type=float, default=0.8)
    args = parser.parse_args()
    if not 0 <= args.min_judge_pass_rate <= 1:
        parser.error("--min-judge-pass-rate 必须在 0 到 1 之间")
    return args


async def main() -> int:
    args = parse_args()
    cases = load_eval_cases(args.dataset)
    report_path = args.report or (
        DEFAULT_REPORT_DIR / f"llm_judge_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    print(f"加载评测集：{args.dataset}（{len(cases)} 条）")
    print("检查 LLM-as-Judge 服务可用性")
    try:
        await verify_judge_availability(invoke_configured_judge)
    except JudgeAvailabilityError as exc:
        print(exc)
        return 2
    print("LLM-as-Judge 服务可用，开始执行评测")
    try:
        async with create_query_service() as query_service:
            report = await run_judge_evaluation(
                cases,
                query_service.run_for_evaluation,
                invoke_configured_judge,
                min_judge_pass_rate=args.min_judge_pass_rate,
            )
    except JudgeInvocationError as exc:
        print(exc)
        return 2

    write_judge_report(report, report_path)
    summary = report["summary"]
    print(
        "评测完成："
        f"裁判通过 {summary['judge_passed']}/{summary['total']}，"
        f"裁判通过率 {summary['judge_pass_rate']:.1%}，"
        f"平均分 {summary['average_overall_score']:.2f}，"
        f"严重错误 {summary['critical_errors']}"
    )
    print(f"报告已写入：{report_path}")
    for case in report["cases"]:
        if case["status"] != "passed":
            reason = (
                case["judge_error"]
                or (case["judge"] or {}).get("reason")
                or case["deterministic"]["reason"]
            )
            print(f"- {case['id']} [{case['status']}] {reason}")
    return 0 if summary["passed_threshold"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
