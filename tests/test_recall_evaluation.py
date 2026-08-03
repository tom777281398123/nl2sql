import asyncio
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from backend.app.evaluation.recall import (
    RecallEvalCase,
    evaluate_recall_at_k,
    load_recall_eval_cases,
    run_recall_evaluation,
)


class RecallAtKTestCase(unittest.TestCase):
    def test_only_unique_candidates_inside_top_k_count(self):
        matched, missing, recall = evaluate_recall_at_k(
            ["wrong", "wrong", "target_a", "target_b"],
            ["target_a", "target_b"],
            top_k=2,
        )

        self.assertEqual(matched, ["target_a"])
        self.assertEqual(missing, ["target_b"])
        self.assertEqual(recall, 0.5)

    def test_rejects_non_positive_top_k(self):
        with self.assertRaisesRegex(ValueError, "top_k"):
            evaluate_recall_at_k(["target"], ["target"], top_k=0)


class RecallDatasetLoadingTestCase(unittest.TestCase):
    def test_repository_golden_set_has_three_retriever_kinds(self):
        dataset = Path(__file__).parents[1] / "eval" / "recall_golden.yaml"

        cases = load_recall_eval_cases(dataset)

        self.assertEqual(len(cases), 33)
        self.assertEqual(
            [case.id.split("_", 1)[0] for case in cases],
            [f"r{index:03d}" for index in range(1, 34)],
        )
        self.assertEqual(Counter(case.kind for case in cases), {
            "column": 12,
            "metric": 6,
            "value": 15,
        })

    def test_rejects_invalid_retriever_kind(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset = Path(temp_dir) / "cases.yaml"
            dataset.write_text(
                "cases:\n"
                "  - id: invalid\n"
                "    kind: table\n"
                "    query: 查询表\n"
                "    expected_ids: [dim_customer]\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "kind"):
                load_recall_eval_cases(dataset)


class RecallEvaluationRunTestCase(unittest.TestCase):
    def test_report_separates_failed_and_error_cases(self):
        cases = [
            RecallEvalCase(
                id="passed", kind="column", query="销售额", expected_ids=["fact_order.order_amount"]
            ),
            RecallEvalCase(
                id="failed", kind="metric", query="GMV", expected_ids=["GMV"]
            ),
            RecallEvalCase(
                id="error", kind="value", query="华东", expected_ids=["dim_region.region_name.华东"]
            ),
        ]

        async def fake_retriever(kind, query, top_k):
            if kind == "value":
                raise RuntimeError("Elasticsearch 不可用")
            if kind == "column":
                return ["fact_order.order_amount"]
            return ["AOV"]

        report = asyncio.run(
            run_recall_evaluation(cases, fake_retriever, min_recall_at_k=0.8)
        )

        self.assertEqual(report["summary"]["passed"], 1)
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertEqual(report["summary"]["errors"], 1)
        self.assertEqual(report["summary"]["macro_recall_at_k"], 0.5)
        self.assertEqual(report["summary"]["micro_recall_at_k"], 0.5)
        self.assertFalse(report["summary"]["passed_threshold"])
        self.assertEqual(report["cases"][2]["missing_ids"], ["dim_region.region_name.华东"])


if __name__ == "__main__":
    unittest.main()
