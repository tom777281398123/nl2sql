import json

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from backend.app.agent.context import DataAgentContext
from backend.app.agent.graph import graph
from backend.app.agent.state import ConversationTurnState, DataAgentState
from backend.app.conf.logger import logger
from backend.app.repositories.es.value_es_repository import ValueESRepository
from backend.app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from backend.app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from backend.app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from backend.app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from backend.app.services.session_memory_service import SessionMemoryService


class QueryService:
    def __init__(self,
                 embedding_client: HuggingFaceEndpointEmbeddings,
                 column_qdrant_repository: ColumnQdrantRepository,
                 value_es_repository: ValueESRepository,
                 metric_qdrant_repository: MetricQdrantRepository,
                 meta_mysql_repository: MetaMySQLRepository,
                 dw_mysql_repository: DWMySQLRepository,
                 session_memory_service: SessionMemoryService | None = None):
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.value_es_repository = value_es_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.session_memory_service = session_memory_service

    async def query(
        self,
        query: str,
        session_id: str | None = None,
        history: list[ConversationTurnState] | None = None,
    ):
        context = self._create_context()
        resolved_query = query
        result: list[dict] | None = None
        sql: str | None = None
        memory_history = history or []
        memory_context = None

        if session_id and self.session_memory_service is not None:
            memory_context = await self.session_memory_service.prepare_context(session_id, query)
            # A healthy server-side session is authoritative; legacy history remains the fallback.
            memory_history = memory_context.history or memory_history
            logger.info(
                "会话上下文已组装: "
                f"session_id={session_id}, items={len(memory_history)}, "
                f"estimated_tokens={memory_context.estimated_tokens}, recalled={memory_context.recalled_count}"
            )

        state = DataAgentState(query=query, history=memory_history)
        if session_id:
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        try:
            async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
                if chunk.get("type") == "query_resolved":
                    resolved_query = str(chunk.get("query") or query)
                    if resolved_query != query:
                        yield f"data: {json.dumps({'type': 'context_resolved', 'query': resolved_query}, ensure_ascii=False)}\n\n"
                    continue
                if chunk.get("type") == "memory_record":
                    sql = chunk.get("sql")
                    raw_result = chunk.get("result")
                    if isinstance(raw_result, list):
                        result = raw_result
                    continue
                yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"  # SSE 格式发送数据

            if session_id and self.session_memory_service is not None and result is not None:
                await self.session_memory_service.record_success(
                    session_id,
                    query,
                    resolved_query,
                    sql=sql,
                    result=result,
                )
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
