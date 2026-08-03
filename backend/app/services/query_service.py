import json

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from backend.app.agent.context import DataAgentContext
from backend.app.agent.graph import graph
from backend.app.agent.state import ConversationTurnState, DataAgentState
from backend.app.repositories.es.value_es_repository import ValueESRepository
from backend.app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from backend.app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from backend.app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from backend.app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService:
    def __init__(self,
                 embedding_client: HuggingFaceEndpointEmbeddings,
                 column_qdrant_repository: ColumnQdrantRepository,
                 value_es_repository: ValueESRepository,
                 metric_qdrant_repository: MetricQdrantRepository,
                 meta_mysql_repository: MetaMySQLRepository,
                 dw_mysql_repository: DWMySQLRepository):
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.value_es_repository = value_es_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository

    async def query(
        self,
        query: str,
        history: list[ConversationTurnState] | None = None,
    ):
        context = self._create_context()
        state = DataAgentState(query=query, history=history or [])
        try:
            async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
                yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"  # SSE 格式发送数据
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False, default=str)}\n\n"

    def _create_context(self) -> DataAgentContext:
        return DataAgentContext(
            embedding_client=self.embedding_client,
            column_qdrant_repository=self.column_qdrant_repository,
            value_es_repository=self.value_es_repository,
            metric_qdrant_repository=self.metric_qdrant_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository
        )

    async def run_for_evaluation(self, query: str) -> dict:
        """Run the production graph and retain the artifacts needed by an evaluator."""
        final_state = await graph.ainvoke(
            input=DataAgentState(query=query, history=[]),
            context=self._create_context(),
        )
        result = final_state.get("result")
        if not isinstance(result, list) or not all(isinstance(row, dict) for row in result):
            raise RuntimeError("NL2SQL 执行后未产生表格结果")

        return {
            "query": query,
            "resolved_query": final_state.get("query", query),
            "sql": final_state.get("sql"),
            "table_infos": final_state.get("table_infos", []),
            "metric_infos": final_state.get("metric_infos", []),
            "date_info": final_state.get("date_info"),
            "db_info": final_state.get("db_info"),
            "actual_rows": result,
        }
