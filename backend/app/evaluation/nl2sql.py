"""Run deterministic result checks against the NL2SQL agent."""

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from numbers import Real
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml


DEFAULT_NUMERIC_TOLERANCE = 0.01

# 定义评测用例数据类
@dataclass(frozen=True)
class NL2SQLEvalCase:
    """A natural-language query with a manually verified expected result."""

    id: str
    category: str
    difficulty: str
    query: str
    expected_rows: list[dict[str, Any]]
    ordered: bool = False
    column_aliases: dict[str, list[str]] | None = None
    allow_extra_columns: bool = False

# 定义评测结果数据类
def load_eval_cases(dataset_path: Path) -> list[NL2SQLEvalCase]:
    """Load and validate a YAML golden set."""
    raw_dataset = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(raw_dataset, dict) or not isinstance(raw_dataset.get("cases"), list):
        raise ValueError("评测集必须是包含 cases 列表的 YAML 文件")

    cases: list[NL2SQLEvalCase] = []
    ids: set[str] = set()
    # 必填字段
    required_fields = {"id", "category", "difficulty", "query", "expected_rows"}
    for index, raw_case in enumerate(raw_dataset["cases"], start=1):
        if not isinstance(raw_case, dict):
            raise ValueError(f"第 {index} 条评测用例必须是对象")

        missing_fields = required_fields - raw_case.keys()
        if missing_fields:
            raise ValueError(f"第 {index} 条评测用例缺少字段: {', '.join(sorted(missing_fields))}")

        case_id = raw_case["id"]
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"第 {index} 条评测用例的 id 必须是非空字符串")
        if case_id in ids:
            raise ValueError(f"评测用例 id 重复: {case_id}")
        ids.add(case_id)

        expected_rows = raw_case["expected_rows"]
        if not isinstance(expected_rows, list) or not all(
            isinstance(row, dict) for row in expected_rows
        ):
            raise ValueError(f"评测用例 {case_id} 的 expected_rows 必须是对象列表")

        column_aliases = raw_case.get("column_aliases", {})
        if not isinstance(column_aliases, dict) or not all(
            isinstance(column, str)
            and isinstance(aliases, list)
            and all(isinstance(alias, str) for alias in aliases)
            for column, aliases in column_aliases.items()
        ):
            raise ValueError(f"评测用例 {case_id} 的 column_aliases 格式不正确")

        cases.append(
            NL2SQLEvalCase(
                id=case_id,
                category=_require_text(raw_case, "category", case_id),
                difficulty=_require_text(raw_case, "difficulty", case_id),
                query=_require_text(raw_case, "query", case_id),
                expected_rows=expected_rows,
                ordered=bool(raw_case.get("ordered", False)),
                column_aliases=column_aliases,
                allow_extra_columns=bool(raw_case.get("allow_extra_columns", False)),
            )
        )

    if not cases:
        raise ValueError("评测集不能为空")
    return cases

# 定义要求文本字段的函数
def _require_text(raw_case: dict[str, Any], field: str, case_id: str) -> str:
    value = raw_case[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"评测用例 {case_id} 的 {field} 必须是非空字符串")
    return value

# 核心比对逻辑
def compare_rows(
    actual_rows: Sequence[dict[str, Any]],
    expected_rows: Sequence[dict[str, Any]],
    *,
    ordered: bool,
    column_aliases: Mapping[str, Sequence[str]] | None = None,
    allow_extra_columns: bool = False,
    numeric_tolerance: float = DEFAULT_NUMERIC_TOLERANCE,
) -> tuple[bool, str | None]:
    """Compare rows by business fields, allowing declared SQL output aliases."""
    if len(actual_rows) != len(expected_rows):
        return False, f"行数不一致：期望 {len(expected_rows)} 行，实际 {len(actual_rows)} 行"

    if ordered:
        for index, (actual, expected) in enumerate(zip(actual_rows, expected_rows), start=1):
            matched, reason = _rows_match(
                actual,
                expected,
                column_aliases,
                allow_extra_columns,
                numeric_tolerance,
            )
            if not matched:
                return False, f"第 {index} 行不一致：{reason}"
        return True, None

    unmatched_actual = list(actual_rows)
    for expected in expected_rows:
        for index, actual in enumerate(unmatched_actual):
            matched, _ = _rows_match(
                actual,
                expected,
                column_aliases,
                allow_extra_columns,
                numeric_tolerance,
            )
            if matched:
                unmatched_actual.pop(index)
                break
        else:
            return False, f"未找到期望结果行：{expected}"
    return True, None

# 单行匹配
def _rows_match(
    actual: dict[str, Any],
    expected: dict[str, Any],
    column_aliases: Mapping[str, Sequence[str]] | None,
    allow_extra_columns: bool,
    numeric_tolerance: float,
) -> tuple[bool, str | None]:
    expected_columns = set(expected)
    resolved_columns: dict[str, str] = {}
    for expected_column in expected_columns:
        aliases = (column_aliases or {}).get(expected_column, [])
        candidates = [expected_column, *aliases]
        actual_column = next((column for column in candidates if column in actual), None)
        if actual_column is None:
            return False, f"缺少业务列 {expected_column}：实际列为 {sorted(actual)}"
        resolved_columns[expected_column] = actual_column

    if not allow_extra_columns and set(resolved_columns.values()) != set(actual):
        return False, f"存在未声明的额外列：实际列为 {sorted(actual)}"

    for column, expected_value in expected.items():
        actual_value = actual[resolved_columns[column]]
        if _numbers_match(actual_value, expected_value, numeric_tolerance):
            continue
        if actual_value != expected_value:
            return False, (
                f"列 {column} 的值不一致：期望 {expected_value!r}，实际 {actual_value!r}"
            )
    return True, None

# 数值匹配
def _numbers_match(actual: Any, expected: Any, numeric_tolerance: float) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return False
    if not isinstance(expected, Real):
        return False
    try:
        actual_number = float(actual)
    except (TypeError, ValueError):
        return False
    return abs(actual_number - float(expected)) <= numeric_tolerance

# 收集查询结果
async def collect_query_result(query_service: Any, query: str) -> list[dict[str, Any]]:
    """Read the result event from QueryService's SSE-compatible event stream."""
    async for event in query_service.query(query):
        payload = _parse_sse_event(event)
        if payload.get("type") == "result":
            result = payload.get("data")
            if not isinstance(result, list) or not all(isinstance(row, dict) for row in result):
                raise RuntimeError("评测接口返回了非表格结果")
            return result
        if payload.get("type") == "error":
            raise RuntimeError(payload.get("message") or "NL2SQL 执行失败")

    raise RuntimeError("NL2SQL 未返回结果事件")

# 解析 SSE 事件
def _parse_sse_event(event: str) -> dict[str, Any]:
    payload = "\n".join(
        line.removeprefix("data:").lstrip()
        for line in event.splitlines()
        if line.startswith("data:")
    )
    if not payload:
        raise RuntimeError("收到空 SSE 事件")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise RuntimeError("收到非对象 SSE 事件")
    return parsed

# 运行评测
async def run_evaluation(
    cases: Sequence[NL2SQLEvalCase],
    query_runner: Callable[[str], Awaitable[list[dict[str, Any]]]],
    *,
    min_pass_rate: float,
) -> dict[str, Any]:
    """Execute every case and return a JSON-serializable report."""
    case_reports: list[dict[str, Any]] = []
    for case in cases:
        started_at = perf_counter()
        actual_rows: list[dict[str, Any]] | None = None
        try:
            actual_rows = await query_runner(case.query)
            passed, reason = compare_rows(
                actual_rows,
                case.expected_rows,
                ordered=case.ordered,
                column_aliases=case.column_aliases,
                allow_extra_columns=case.allow_extra_columns,
            )
            status = "passed" if passed else "failed"
        except Exception as exc:
            status = "error"
            reason = str(exc)

        case_reports.append(
            {
                "id": case.id,
                "category": case.category,
                "difficulty": case.difficulty,
                "query": case.query,
                "ordered": case.ordered,
                "column_aliases": case.column_aliases,
                "allow_extra_columns": case.allow_extra_columns,
                "status": status,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "reason": reason,
                "expected_rows": case.expected_rows,
                "actual_rows": actual_rows,
            }
        )

    passed_count = sum(report["status"] == "passed" for report in case_reports)
    total_count = len(case_reports)
    pass_rate = passed_count / total_count if total_count else 0.0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total_count,
            "passed": passed_count,
            "failed": total_count - passed_count,
            "pass_rate": round(pass_rate, 4),
            "min_pass_rate": min_pass_rate,
            "passed_threshold": pass_rate >= min_pass_rate,
        },
        "cases": case_reports,
    }

# 写入评测报告
def write_report(report: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

# 转换评测用例为字典
def case_to_dict(case: NL2SQLEvalCase) -> dict[str, Any]:
    """Expose case metadata for command-line reporting."""
    return asdict(case)
