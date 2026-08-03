"""LLM-as-Judge evaluation for complete NL2SQL runs."""

import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.app.evaluation.nl2sql import NL2SQLEvalCase, compare_rows
from backend.app.prompt.prompt_loader import load_prompt


JudgeInvoker = Callable[[str], Awaitable[str]]
AgentRunner = Callable[[str], Awaitable[dict[str, Any]]]
VALID_VERDICTS = frozenset({"pass", "minor_error", "major_error"})
DIMENSION_NAMES = (
    "intent_correctness",
    "sql_grounding",
    "result_correctness",
)
WRITE_SQL_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke)\b",
    re.IGNORECASE,
)


class JudgeResponseError(ValueError):
    """Raised when the judge does not produce the agreed JSON schema."""


class JudgeInvocationError(RuntimeError):
    """Raised when a judge request fails and the evaluation must stop."""


class JudgeAvailabilityError(RuntimeError):
    """Raised when the judge cannot be reached before an evaluation starts."""


@dataclass(frozen=True)
class JudgeAssessment:
    verdict: str
    overall_score: int
    dimensions: dict[str, int]
    critical_error: bool
    reason: str
    evidence: list[str]
    raw_responses: list[str]
    retried_for_format: bool
    source: str = "llm"


def build_judge_prompt(case: NL2SQLEvalCase, trace: Mapping[str, Any]) -> str:
    """Render the prompt from only the artifacts produced by this agent run."""
    return load_prompt("judge_nl2sql").format(
        query=case.query,
        resolved_query=_json_text(trace.get("resolved_query", case.query)),
        sql=_json_text(trace.get("sql")),
        table_infos=_json_text(trace.get("table_infos", [])),
        metric_infos=_json_text(trace.get("metric_infos", [])),
        runtime_context=_json_text(
            {"date_info": trace.get("date_info"), "db_info": trace.get("db_info")}
        ),
        expected_rows=_json_text(case.expected_rows),
        actual_rows=_json_text(trace.get("actual_rows")),
    )


def parse_judge_response(raw_response: str) -> JudgeAssessment:
    """Parse and validate one structured judge response without repairing its content."""
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise JudgeResponseError("裁判返回为空")

    payload = _decode_first_json_object(raw_response)
    verdict = payload.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise JudgeResponseError("verdict 必须为 pass、minor_error 或 major_error")

    overall_score = _require_score(payload.get("overall_score"), "overall_score")
    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, dict) or set(dimensions) != set(DIMENSION_NAMES):
        raise JudgeResponseError("dimensions 必须包含三个指定维度")
    parsed_dimensions = {
        name: _require_score(dimensions[name], f"dimensions.{name}")
        for name in DIMENSION_NAMES
    }

    critical_error = payload.get("critical_error")
    if not isinstance(critical_error, bool):
        raise JudgeResponseError("critical_error 必须为布尔值")
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise JudgeResponseError("reason 必须为非空字符串")
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence or not all(
        isinstance(item, str) and item.strip() for item in evidence
    ):
        raise JudgeResponseError("evidence 必须为非空字符串列表")

    if verdict == "pass" and overall_score < 4:
        raise JudgeResponseError("pass 的 overall_score 必须为 4 或 5")
    if verdict == "minor_error" and overall_score not in {2, 3, 4}:
        raise JudgeResponseError("minor_error 的 overall_score 必须为 2 到 4")
    if verdict == "major_error" and overall_score > 2:
        raise JudgeResponseError("major_error 的 overall_score 必须为 1 或 2")
    if critical_error and verdict != "major_error":
        raise JudgeResponseError("critical_error 为 true 时 verdict 必须为 major_error")

    return JudgeAssessment(
        verdict=verdict,
        overall_score=overall_score,
        dimensions=parsed_dimensions,
        critical_error=critical_error,
        reason=reason.strip(),
        evidence=[item.strip() for item in evidence],
        raw_responses=[raw_response],
        retried_for_format=False,
    )


async def judge_trace(
    case: NL2SQLEvalCase,
    trace: Mapping[str, Any],
    judge_invoker: JudgeInvoker,
) -> JudgeAssessment:
    """Judge one valid agent trace and retry once only for invalid output formatting."""
    hard_failure = assess_hard_failure(trace)
    if hard_failure is not None:
        return hard_failure

    prompt = build_judge_prompt(case, trace)
    first_response = await judge_invoker(prompt)
    try:
        return parse_judge_response(first_response)
    except JudgeResponseError as first_error:
        repair_prompt = _build_format_repair_prompt(first_response, str(first_error))
        second_response = await judge_invoker(repair_prompt)
        assessment = parse_judge_response(second_response)
        return JudgeAssessment(
            **{
                **asdict(assessment),
                "raw_responses": [first_response, second_response],
                "retried_for_format": True,
            }
        )


def assess_hard_failure(trace: Mapping[str, Any]) -> JudgeAssessment | None:
    """Apply non-negotiable safety and executability rules before asking the model."""
    sql = trace.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        return _hard_failure("未生成可评估的 SQL", "生成 SQL 为空")
    normalized_sql = sql.lstrip().lower()
    if not normalized_sql.startswith(("select", "with", "show", "explain")):
        return _hard_failure("生成了非只读 SQL", f"SQL 以 {normalized_sql.split(None, 1)[0]!r} 开头")
    if WRITE_SQL_PATTERN.search(sql):
        return _hard_failure("SQL 包含写操作关键字", "只允许在数据仓库执行只读 SQL")
    actual_rows = trace.get("actual_rows")
    if not isinstance(actual_rows, list) or not all(isinstance(row, dict) for row in actual_rows):
        return _hard_failure("SQL 未返回可用的表格结果", "actual_rows 不是对象列表")
    return None


async def invoke_configured_judge(prompt: str) -> str:
    """Call the independently configured judge model and normalize its text response."""
    from backend.app.agent.judge_llm import judge_llm

    response = await judge_llm.ainvoke(prompt)
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item if isinstance(item, str) else str(item.get("text", ""))
            for item in content
        )
    return str(content)


async def verify_judge_availability(judge_invoker: JudgeInvoker) -> None:
    """Fail before running any Agent case when the judge endpoint is unavailable."""
    try:
        response = await judge_invoker("这是连通性检查。请只回复 OK。")
    except Exception as exc:
        raise JudgeAvailabilityError(
            f"LLM-as-Judge 连通性检查失败，评测未启动：{exc}"
        ) from exc
    if not isinstance(response, str) or not response.strip():
        raise JudgeAvailabilityError("LLM-as-Judge 连通性检查失败，评测未启动：裁判返回为空")


async def run_judge_evaluation(
    cases: Sequence[NL2SQLEvalCase],
    agent_runner: AgentRunner,
    judge_invoker: JudgeInvoker,
    *,
    min_judge_pass_rate: float,
) -> dict[str, Any]:
    """Run every golden case through production, deterministic, and LLM judge checks."""
    if not 0 <= min_judge_pass_rate <= 1:
        raise ValueError("min_judge_pass_rate 必须在 0 到 1 之间")

    case_reports: list[dict[str, Any]] = []
    for case in cases:
        started_at = perf_counter()
        trace: dict[str, Any] | None = None
        deterministic: dict[str, Any]
        judge_assessment: JudgeAssessment | None = None
        judge_error: str | None = None
        try:
            trace = await agent_runner(case.query)
            actual_rows = trace.get("actual_rows")
            if not isinstance(actual_rows, list) or not all(isinstance(row, dict) for row in actual_rows):
                raise RuntimeError("评测运行未返回对象列表结果")
            matched, reason = compare_rows(
                actual_rows,
                case.expected_rows,
                ordered=case.ordered,
                column_aliases=case.column_aliases,
                allow_extra_columns=case.allow_extra_columns,
            )
            deterministic = {
                "status": "passed" if matched else "failed",
                "reason": reason,
            }
        except Exception as exc:
            deterministic = {"status": "error", "reason": str(exc)}

        if trace is None:
            judge_assessment = _hard_failure(
                "Agent 执行失败，无法生成 SQL 结果",
                deterministic["reason"],
            )
        else:
            try:
                judge_assessment = await judge_trace(case, trace, judge_invoker)
            except Exception as exc:
                raise JudgeInvocationError(
                    f"用例 {case.id} 的 LLM-as-Judge 调用失败，评测已中止：{exc}"
                ) from exc

        if judge_error is not None or deterministic["status"] == "error":
            status = "error"
        elif deterministic["status"] == "passed" and judge_assessment is not None and judge_assessment.verdict == "pass":
            status = "passed"
        else:
            status = "failed"

        case_reports.append(
            {
                "id": case.id,
                "category": case.category,
                "difficulty": case.difficulty,
                "query": case.query,
                "status": status,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "deterministic": deterministic,
                "judge": asdict(judge_assessment) if judge_assessment else None,
                "judge_error": judge_error,
                "trace": trace,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": _summarize(case_reports, min_judge_pass_rate),
        "cases": case_reports,
    }


def write_judge_report(report: Mapping[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _summarize(case_reports: Sequence[Mapping[str, Any]], min_judge_pass_rate: float) -> dict[str, Any]:
    total = len(case_reports)
    judge_reports = [report["judge"] for report in case_reports if report["judge"] is not None]
    judge_passed = sum(judge["verdict"] == "pass" for judge in judge_reports)
    scores = [judge["overall_score"] for judge in judge_reports]
    return {
        "total": total,
        "combined_passed": sum(report["status"] == "passed" for report in case_reports),
        "deterministic_passed": sum(
            report["deterministic"]["status"] == "passed" for report in case_reports
        ),
        "judge_passed": judge_passed,
        "judge_errors": sum(report["judge_error"] is not None for report in case_reports),
        "major_errors": sum(judge["verdict"] == "major_error" for judge in judge_reports),
        "critical_errors": sum(judge["critical_error"] for judge in judge_reports),
        "judge_pass_rate": round(judge_passed / total, 4) if total else 0.0,
        "average_overall_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "min_judge_pass_rate": min_judge_pass_rate,
        "passed_threshold": (judge_passed / total if total else 0.0) >= min_judge_pass_rate,
    }


def _decode_first_json_object(raw_response: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw_response):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(raw_response[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise JudgeResponseError("裁判返回中没有可解析的 JSON 对象")


def _require_score(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise JudgeResponseError(f"{name} 必须是 1 到 5 的整数")
    return value


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _build_format_repair_prompt(raw_response: str, error: str) -> str:
    return (
        "你刚才的裁判输出无法被程序解析。只修复格式，不重新判断，不添加解释。"
        "严格输出一个满足原 JSON schema 的对象。解析错误："
        f"{error}\n原始输出：\n{raw_response[:12000]}"
    )


def _hard_failure(reason: str, evidence: str) -> JudgeAssessment:
    return JudgeAssessment(
        verdict="major_error",
        overall_score=1,
        dimensions={name: 1 for name in DIMENSION_NAMES},
        critical_error=True,
        reason=reason,
        evidence=[evidence],
        raw_responses=[],
        retried_for_format=False,
        source="hard_rule",
    )
