"""Command-line runner for the end-to-end NL2SQL golden-set evaluation."""

import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from backend.app.clients.embedding_client_manager import embedding_client_manager
from backend.app.clients.es_client_manager import es_client_manager
from backend.app.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from backend.app.clients.qdrant_client_manager import qdrant_client_manager
from backend.app.constants.project_constant import PROJECT_ROOT
from backend.app.evaluation.nl2sql import (
    collect_query_result,
    load_eval_cases,
    run_evaluation,
    write_report,
)
from backend.app.repositories.es.value_es_repository import ValueESRepository
from backend.app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from backend.app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from backend.app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from backend.app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from backend.app.services.query_service import QueryService


DEFAULT_DATASET_PATH = PROJECT_ROOT / "eval" / "nl2sql_golden.yaml"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "eval" / "reports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行端到端 NL2SQL 黄金集评测")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--min-pass-rate", type=float, default=0.8)
    args = parser.parse_args()
    if not 0 <= args.min_pass_rate <= 1:
        parser.error("--min-pass-rate 必须在 0 到 1 之间")
    return args


@asynccontextmanager
async def create_query_service() -> AsyncIterator[QueryService]:
    """Create the same infrastructure dependencies used by the FastAPI service."""
    embedding_client_manager.init()
    qdrant_client_manager.init()
    es_client_manager.init()
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()

    try:
        async with (
            meta_mysql_client_manager.session_factory() as meta_session,
            dw_mysql_client_manager.session_factory() as dw_session,
        ):
            yield QueryService(
                embedding_client=embedding_client_manager.client,
                column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manager.client),
                value_es_repository=ValueESRepository(es_client_manager.client),
                metric_qdrant_repository=MetricQdrantRepository(qdrant_client_manager.client),
                meta_mysql_repository=MetaMySQLRepository(meta_session),
                dw_mysql_repository=DWMySQLRepository(dw_session),
            )
    finally:
        await qdrant_client_manager.close()
        await es_client_manager.close()
        await meta_mysql_client_manager.close()
        await dw_mysql_client_manager.close()


async def main() -> int:
    args = parse_args()
    cases = load_eval_cases(args.dataset)
    report_path = args.report or (
        DEFAULT_REPORT_DIR
        / f"nl2sql_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    print(f"加载评测集：{args.dataset}（{len(cases)} 条）")
    async with create_query_service() as query_service:
        report = await run_evaluation(
            cases,
            lambda query: collect_query_result(query_service, query),
            min_pass_rate=args.min_pass_rate,
        )

    write_report(report, report_path)
    summary = report["summary"]
    print(
        "评测完成："
        f"{summary['passed']}/{summary['total']} 通过，"
        f"通过率 {summary['pass_rate']:.1%}，"
        f"门槛 {summary['min_pass_rate']:.1%}"
    )
    print(f"报告已写入：{report_path}")

    for case in report["cases"]:
        if case["status"] != "passed":
            print(f"- {case['id']} [{case['status']}] {case['reason']}")
    return 0 if summary["passed_threshold"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
