import asyncio
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from backend.app.evaluation.judge import (
    JudgeAvailabilityError,
    JudgeInvocationError,
    JudgeResponseError,
    assess_hard_failure,
    judge_trace,
    parse_judge_response,
    run_judge_evaluation,
    verify_judge_availability,
    write_judge_report,
)
from backend.app.evaluation.nl2sql import NL2SQLEvalCase


def _case() -> NL2SQLEvalCase:
    return NL2SQLEvalCase(
        id="judge_case",
        category="aggregate",
        difficulty="easy",
        query="查询销售额",
        expected_rows=[{"sales_amount": 10}],
    )


def _trace() -> dict:
    return {
        "query": "查询销售额",
        "resolved_query": "查询销售额",
        "sql": "SELECT SUM(order_amount) AS sales_amount FROM fact_order",
        "table_infos": [{"name": "fact_order", "columns": [{"name": "order_amount"}]}],
        "metric_infos": [],
        "date_info": {"date": "2026-08-02"},
        "db_info": {"dialect": "mysql"},
        "actual_rows": [{"sales_amount": 10}],
    }


def _valid_response(verdict: str = "pass", score: int = 5) -> str:
    return (
        '{"verdict": "' + verdict + '", '
        '"overall_score": ' + str(score) + ', '
        '"dimensions": {"intent_correctness": 5, "sql_grounding": 5, "result_correctness": 5}, '
        '"critical_error": false, "reason": "口径和结果一致", '
        '"evidence": ["实际销售额为 10，与黄金结果一致"]}'
    )


class JudgeResponseTestCase(unittest.TestCase):
    def test_parses_json_wrapped_by_markdown(self):
        assessment = parse_judge_response(f"```json\n{_valid_response()}\n```")

        self.assertEqual(assessment.verdict, "pass")
        self.assertEqual(assessment.overall_score, 5)

    def test_rejects_inconsistent_verdict_and_score(self):
        with self.assertRaisesRegex(JudgeResponseError, "pass"):
            parse_judge_response(_valid_response("pass", 2))

    def test_non_read_only_sql_is_hard_failure(self):
        assessment = assess_hard_failure({**_trace(), "sql": "DELETE FROM fact_order"})

        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.verdict, "major_error")
        self.assertTrue(assessment.critical_error)


class JudgeExecutionTestCase(unittest.TestCase):
    def test_availability_check_fails_before_evaluation_starts(self):
        async def unavailable_judge(_: str) -> str:
            raise RuntimeError("账户余额不足")

        with self.assertRaisesRegex(JudgeAvailabilityError, "评测未启动"):
            asyncio.run(verify_judge_availability(unavailable_judge))

    def test_retries_once_when_first_response_is_not_json(self):
        responses = iter(["我认为正确", _valid_response()])
        prompts: list[str] = []

        async def fake_judge(prompt: str) -> str:
            prompts.append(prompt)
            return next(responses)

        assessment = asyncio.run(judge_trace(_case(), _trace(), fake_judge))

        self.assertTrue(assessment.retried_for_format)
        self.assertEqual(len(assessment.raw_responses), 2)
        self.assertEqual(len(prompts), 2)

    def test_report_keeps_deterministic_and_judge_results_separate(self):
        passing_case = _case()
        failed_case = NL2SQLEvalCase(
            id="different_result",
            category="aggregate",
            difficulty="easy",
            query="查询失败结果",
            expected_rows=[{"sales_amount": 99}],
        )

        async def fake_agent(query: str) -> dict:
            return _trace()

        async def fake_judge(_: str) -> str:
            return _valid_response()

        report = asyncio.run(
            run_judge_evaluation(
                [passing_case, failed_case],
                fake_agent,
                fake_judge,
                min_judge_pass_rate=0.8,
            )
        )

        self.assertEqual(report["summary"]["judge_passed"], 2)
        self.assertEqual(report["summary"]["deterministic_passed"], 1)
        self.assertEqual(report["summary"]["combined_passed"], 1)
        self.assertEqual(report["cases"][1]["status"], "failed")

    def test_judge_failure_stops_without_running_later_cases(self):
        first_case = _case()
        second_case = NL2SQLEvalCase(
            id="must_not_run",
            category="aggregate",
            difficulty="easy",
            query="第二条",
            expected_rows=[{"sales_amount": 10}],
        )
        agent_queries: list[str] = []

        async def fake_agent(query: str) -> dict:
            agent_queries.append(query)
            return _trace()

        async def unavailable_judge(_: str) -> str:
            raise RuntimeError("账户余额不足")

        with self.assertRaisesRegex(JudgeInvocationError, "judge_case"):
            asyncio.run(
                run_judge_evaluation(
                    [first_case, second_case],
                    fake_agent,
                    unavailable_judge,
                    min_judge_pass_rate=0.8,
                )
            )

        self.assertEqual(agent_queries, [first_case.query])

    def test_report_serializes_decimal_without_losing_precision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            write_judge_report(
                {"trace": {"actual_rows": [{"sales_amount": Decimal("10.20")}]}},
                report_path,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["trace"]["actual_rows"][0]["sales_amount"], "10.20")


if __name__ == "__main__":
    unittest.main()
