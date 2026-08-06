import asyncio
import tempfile
import unittest
from pathlib import Path

from backend.app.evaluation.nl2sql import (
    NL2SQLEvalCase,
    compare_rows,
    load_eval_cases,
    run_evaluation,
)


class CompareRowsTestCase(unittest.TestCase):
    def test_numbers_within_tolerance_match(self):
        matched, reason = compare_rows(
            [{"sales_amount": 10.004}],
            [{"sales_amount": 10.0}],
            ordered=True,
        )

        self.assertTrue(matched)
        self.assertIsNone(reason)

    def test_order_is_checked_only_for_ordered_case(self):
        actual = [{"region": "华东"}, {"region": "华南"}]
        expected = [{"region": "华南"}, {"region": "华东"}]

        self.assertTrue(compare_rows(actual, expected, ordered=False)[0])
        self.assertFalse(compare_rows(actual, expected, ordered=True)[0])

    def test_column_mismatch_fails(self):
        matched, reason = compare_rows(
            [{"total": 10}],
            [{"sales_amount": 10}],
            ordered=True,
        )

        self.assertFalse(matched)
        self.assertIn("缺少业务列", reason)

    def test_declared_alias_and_extra_columns_can_match(self):
        matched, reason = compare_rows(
            [{"地区": "华东", "销售额": 10, "region_id": "R002"}],
            [{"region_name": "华东", "sales_amount": 10}],
            ordered=True,
            column_aliases={
                "region_name": ["地区"],
                "sales_amount": ["销售额"],
            },
            allow_extra_columns=True,
        )

        self.assertTrue(matched)
        self.assertIsNone(reason)


class DatasetLoadingTestCase(unittest.TestCase):
    def test_repository_golden_set_has_100_contiguous_cases(self):
        dataset = Path(__file__).parents[1] / "eval" / "nl2sql_golden.yaml"

        cases = load_eval_cases(dataset)

        self.assertEqual(len(cases), 100)
        self.assertEqual(
            [case.id.split("_", 1)[0] for case in cases],
            [f"g{index:03d}" for index in range(1, 101)],
        )
        self.assertEqual(len({case.query for case in cases}), 100)

    def test_loads_valid_cases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset = Path(temp_dir) / "cases.yaml"
            dataset.write_text(
                "cases:\n"
                "  - id: case_1\n"
                "    category: aggregate\n"
                "    difficulty: easy\n"
                "    query: 查询销售额\n"
                "    expected_rows:\n"
                "      - sales_amount: 1\n",
                encoding="utf-8",
            )

            cases = load_eval_cases(dataset)

        self.assertEqual(cases[0].id, "case_1")
        self.assertEqual(cases[0].expected_rows, [{"sales_amount": 1}])

    def test_rejects_duplicate_case_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset = Path(temp_dir) / "cases.yaml"
            dataset.write_text(
                "cases:\n"
                "  - id: duplicate\n"
                "    category: aggregate\n"
                "    difficulty: easy\n"
                "    query: 查询一\n"
                "    expected_rows: []\n"
                "  - id: duplicate\n"
                "    category: aggregate\n"
                "    difficulty: easy\n"
                "    query: 查询二\n"
                "    expected_rows: []\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "重复"):
                load_eval_cases(dataset)


class EvaluationRunTestCase(unittest.TestCase):
    def test_report_includes_pass_and_error_cases(self):
        cases = [
            NL2SQLEvalCase(
                id="pass",
                category="aggregate",
                difficulty="easy",
                query="查询销售额",
                expected_rows=[{"sales_amount": 1}],
            ),
            NL2SQLEvalCase(
                id="error",
                category="aggregate",
                difficulty="easy",
                query="查询失败",
                expected_rows=[],
            ),
        ]

        async def fake_runner(query):
            if query == "查询失败":
                raise RuntimeError("服务不可用")
            return [{"sales_amount": 1.0}]

        report = asyncio.run(
            run_evaluation(cases, fake_runner, min_pass_rate=0.8)
        )

        self.assertEqual(report["summary"]["passed"], 1)
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertFalse(report["summary"]["passed_threshold"])
        self.assertEqual(report["cases"][1]["status"], "error")
