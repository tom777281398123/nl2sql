"""Command-line runner for deterministic column, metric, and value recall checks."""

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from backend.app.clients.embedding_client_manager import embedding_client_manager
from backend.app.clients.es_client_manager import es_client_manager
from backend.app.clients.qdrant_client_manager import qdrant_client_manager
from backend.app.constants.project_constant import PROJECT_ROOT
from backend.app.evaluation.recall import (
    load_recall_eval_cases,
    run_recall_evaluation,
    write_recall_report,
)
from backend.app.repositories.es.value_es_repository import ValueESRepository
from backend.app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from backend.app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


DEFAULT_DATASET_PATH = PROJECT_ROOT / "eval" / "recall_golden.yaml"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "eval" / "reports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行字段、指标与取值的 Recall@K 评测")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--top-k", type=int, help="覆盖评测集内的 top_k")
    parser.add_argument("--vector-score-threshold", type=float, default=0.6)
    parser.add_argument("--value-score-threshold", type=float, default=0.6)
    parser.add_argument("--min-recall-at-k", type=float, default=0.8)
    args = parser.parse_args()
    if args.top_k is not None and args.top_k <= 0:
        parser.error("--top-k 必须是正整数")
    if not -1 <= args.vector_score_threshold <= 1:
        parser.error("--vector-score-threshold 必须在 -1 到 1 之间")
    if args.value_score_threshold < 0:
        parser.error("--value-score-threshold 必须大于等于 0")
    if not 0 <= args.min_recall_at_k <= 1:
        parser.error("--min-recall-at-k 必须在 0 到 1 之间")
    return args


@asynccontextmanager
async def create_retriever(
    vector_score_threshold: float, value_score_threshold: float
) -> AsyncIterator["RecallRetriever"]:
    embedding_client_manager.init()
    qdrant_client_manager.init()
    es_client_manager.init()
    try:
        await _verify_retrieval_knowledge_base()
        yield RecallRetriever(
            column_repository=ColumnQdrantRepository(qdrant_client_manager.client),
            metric_repository=MetricQdrantRepository(qdrant_client_manager.client),
            value_repository=ValueESRepository(es_client_manager.client),
            vector_score_threshold=vector_score_threshold,
            value_score_threshold=value_score_threshold,
        )
    finally:
        await qdrant_client_manager.close()
        await es_client_manager.close()


async def _verify_retrieval_knowledge_base() -> None:
    """Fail before evaluation when the required retrieval indexes were never built."""
    column_repository = ColumnQdrantRepository(qdrant_client_manager.client)
    metric_repository = MetricQdrantRepository(qdrant_client_manager.client)
    value_repository = ValueESRepository(es_client_manager.client)
    try:
        availability = {
            column_repository.collection_name: await qdrant_client_manager.client.collection_exists(
                column_repository.collection_name
            ),
            metric_repository.collection_name: await qdrant_client_manager.client.collection_exists(
                metric_repository.collection_name
            ),
            value_repository.index_name: await es_client_manager.client.indices.exists(
                index=value_repository.index_name
            ),
        }
    except Exception as exc:
        raise RuntimeError(
            "无法连接召回中间件，请先启动 Docker 并执行 ./run.sh start middleware"
        ) from exc

    missing_names = [name for name, exists in availability.items() if not exists]
    if missing_names:
        raise RuntimeError(
            f"召回知识库未构建，缺少: {', '.join(missing_names)}。请执行 ./run.sh build-kb"
        )


class RecallRetriever:
    """Run the same repository searches used by the three recall nodes, without LLM expansion."""

    def __init__(
        self,
        *,
        column_repository: ColumnQdrantRepository,
        metric_repository: MetricQdrantRepository,
        value_repository: ValueESRepository,
        vector_score_threshold: float,
        value_score_threshold: float,
    ):
        self.column_repository = column_repository
        self.metric_repository = metric_repository
        self.value_repository = value_repository
        self.vector_score_threshold = vector_score_threshold
        self.value_score_threshold = value_score_threshold

    async def retrieve(self, kind: str, query: str, top_k: int) -> list[str]:
        if kind == "value":
            values = await self.value_repository.search(
                query, score_threshold=self.value_score_threshold, limit=top_k
            )
            return [value.id for value in values]

        embedding = await embedding_client_manager.client.aembed_query(query)
        if kind == "column":
            columns = await self.column_repository.search(
                embedding, score_threshold=self.vector_score_threshold, limit=top_k
            )
            return [column.id for column in columns]
        if kind == "metric":
            metrics = await self.metric_repository.search(
                embedding, score_threshold=self.vector_score_threshold, limit=top_k
            )
            return [metric.id for metric in metrics]
        raise ValueError(f"未知召回类型: {kind}")


async def main() -> int:
    args = parse_args()
    cases = load_recall_eval_cases(args.dataset)
    if args.top_k is not None:
        cases = [replace(case, top_k=args.top_k) for case in cases]

    report_path = args.report or (
        DEFAULT_REPORT_DIR / f"recall_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    print(f"加载召回评测集：{args.dataset}（{len(cases)} 条）")
    try:
        async with create_retriever(
            args.vector_score_threshold, args.value_score_threshold
        ) as retriever:
            report = await run_recall_evaluation(
                cases,
                retriever.retrieve,
                min_recall_at_k=args.min_recall_at_k,
            )
    except RuntimeError as exc:
        print(f"评测无法启动：{exc}")
        return 2

    write_recall_report(report, report_path)
    summary = report["summary"]
    print(
        "评测完成："
        f"Macro Recall@K {summary['macro_recall_at_k']:.1%}，"
        f"Micro Recall@K {summary['micro_recall_at_k']:.1%}，"
        f"门槛 {summary['min_recall_at_k']:.1%}"
    )
    print(f"报告已写入：{report_path}")
    for case in report["cases"]:
        if case["status"] != "passed":
            print(f"- {case['id']} [{case['status']}] {case['reason']}")
    return 0 if summary["passed_threshold"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
