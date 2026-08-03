"""Evaluate the three retrieval stores with deterministic Recall@K checks."""

import json
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

# 默认召回评测参数
DEFAULT_TOP_K = 5
# 允许的召回评测类型
RETRIEVER_KINDS = frozenset({"column", "metric", "value"})

# 召回评测用例
@dataclass(frozen=True)
class RecallEvalCase:
    """A retrieval query and the metadata IDs that must appear in its top K."""

    id: str
    kind: str
    query: str
    expected_ids: list[str]
    top_k: int = DEFAULT_TOP_K


def load_recall_eval_cases(dataset_path: Path) -> list[RecallEvalCase]:
    """Load a recall golden set and reject malformed or duplicate cases."""
    raw_dataset = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(raw_dataset, dict) or not isinstance(raw_dataset.get("cases"), list):
        raise ValueError("召回评测集必须是包含 cases 列表的 YAML 文件")

    cases: list[RecallEvalCase] = []
    ids: set[str] = set()
    for index, raw_case in enumerate(raw_dataset["cases"], start=1):
        if not isinstance(raw_case, dict):
            raise ValueError(f"第 {index} 条召回评测用例必须是对象")

        case_id = _require_text(raw_case, "id", index)
        if case_id in ids:
            raise ValueError(f"召回评测用例 id 重复: {case_id}")
        ids.add(case_id)

        kind = _require_text(raw_case, "kind", case_id)
        if kind not in RETRIEVER_KINDS:
            allowed_kinds = ", ".join(sorted(RETRIEVER_KINDS))
            raise ValueError(f"召回评测用例 {case_id} 的 kind 必须是: {allowed_kinds}")

        expected_ids = raw_case.get("expected_ids")
        if (
            not isinstance(expected_ids, list)
            or not expected_ids
            or not all(isinstance(item, str) and item.strip() for item in expected_ids)
            or len(set(expected_ids)) != len(expected_ids)
        ):
            raise ValueError(
                f"召回评测用例 {case_id} 的 expected_ids 必须是非空且不重复的字符串列表"
            )

        top_k = raw_case.get("top_k", DEFAULT_TOP_K)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
            raise ValueError(f"召回评测用例 {case_id} 的 top_k 必须是正整数")

        cases.append(
            RecallEvalCase(
                id=case_id,
                kind=kind,
                query=_require_text(raw_case, "query", case_id),
                expected_ids=expected_ids,
                top_k=top_k,
            )
        )

    if not cases:
        raise ValueError("召回评测集不能为空")
    return cases

# 验证必填字段
def _require_text(raw_case: dict[str, Any], field: str, case_id: str | int) -> str:
    value = raw_case.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"召回评测用例 {case_id} 的 {field} 必须是非空字符串")
    return value

# 召回评测逻辑
def evaluate_recall_at_k(
    retrieved_ids: Sequence[str], expected_ids: Sequence[str], top_k: int
) -> tuple[list[str], list[str], float]:
    """Return matched IDs, missing IDs, and Recall@K for one retrieval result."""
    if top_k <= 0:
        raise ValueError("top_k 必须是正整数")
    # 去重并取前 top_k 个 ID
    top_ids = _unique_ids(retrieved_ids)[:top_k]
    retrieved_set = set(top_ids)
    matched_ids = [expected_id for expected_id in expected_ids if expected_id in retrieved_set]
    missing_ids = [expected_id for expected_id in expected_ids if expected_id not in retrieved_set]
    return matched_ids, missing_ids, len(matched_ids) / len(expected_ids)

# 去重逻辑
def _unique_ids(ids: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique_ids: list[str] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            unique_ids.append(item)
    return unique_ids


async def run_recall_evaluation(
    cases: Sequence[RecallEvalCase],
    retriever: Callable[[str, str, int], Awaitable[list[str]]],
    *,
    min_recall_at_k: float,
) -> dict[str, Any]:
    """Run every retrieval query and return a JSON-serializable report."""
    if not 0 <= min_recall_at_k <= 1:
        raise ValueError("min_recall_at_k 必须在 0 到 1 之间")

    case_reports: list[dict[str, Any]] = []
    for case in cases:
        started_at = perf_counter()
        retrieved_ids: list[str] | None = None
        try:
            retrieved_ids = await retriever(case.kind, case.query, case.top_k)
            matched_ids, missing_ids, recall_at_k = evaluate_recall_at_k(
                retrieved_ids, case.expected_ids, case.top_k
            )
            status = "passed" if not missing_ids else "failed"
            reason = None if not missing_ids else f"未召回目标: {missing_ids}"
        except Exception as exc:
            matched_ids = []
            missing_ids = list(case.expected_ids)
            recall_at_k = None
            status = "error"
            reason = str(exc)

        case_reports.append(
            {
                **asdict(case),
                "status": status,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "retrieved_ids": retrieved_ids,
                "matched_ids": matched_ids,
                "missing_ids": missing_ids,
                "recall_at_k": recall_at_k,
                "reason": reason,
            }
        )

    summary = _summarize_reports(case_reports, min_recall_at_k)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "by_kind": _summarize_by_kind(case_reports),
        "cases": case_reports,
    }

# 总结评测结果
def _summarize_reports(
    case_reports: Sequence[dict[str, Any]], min_recall_at_k: float
) -> dict[str, Any]:
    successful_reports = [report for report in case_reports if report["status"] != "error"]
    recalls = [report["recall_at_k"] for report in successful_reports]
    matched_count = sum(len(report["matched_ids"]) for report in successful_reports)
    expected_count = sum(len(report["expected_ids"]) for report in successful_reports)
    error_count = sum(report["status"] == "error" for report in case_reports)
    passed_count = sum(report["status"] == "passed" for report in case_reports)
    failed_count = sum(report["status"] == "failed" for report in case_reports)
    # 计算宏观召回率 + 微观召回率
    macro_recall = sum(recalls) / len(recalls) if recalls else 0.0 # 逐条用例的平均召回率
    micro_recall = matched_count / expected_count if expected_count else 0.0 # 所有 ID 级别的全局召回率
    return {
        "total": len(case_reports),
        "passed": passed_count,
        "failed": failed_count,
        "errors": error_count,
        "evaluated": len(successful_reports),
        "macro_recall_at_k": round(macro_recall, 4),
        "micro_recall_at_k": round(micro_recall, 4),
        "min_recall_at_k": min_recall_at_k,
        "passed_threshold": error_count == 0 and macro_recall >= min_recall_at_k,
    }


def _summarize_by_kind(case_reports: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    reports_by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for report in case_reports:
        reports_by_kind[report["kind"]].append(report)

    return {
        kind: _summarize_reports(reports, min_recall_at_k=0.0)
        for kind, reports in sorted(reports_by_kind.items())
    }


def write_recall_report(report: dict[str, Any], report_path: Path) -> None:
    """Write a recall evaluation report without tracking generated artifacts."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
