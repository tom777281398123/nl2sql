import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from backend.app.agent.nodes.resolve_query import resolve_query
from backend.app.api.schemas.query_schema import QuerySchema
from backend.app.services.query_service import QueryService


class QuerySchemaTestCase(unittest.TestCase):
    def test_history_is_optional_for_backward_compatibility(self):
        schema = QuerySchema(query="查询各地区销售额")

        self.assertEqual(schema.history, [])

    def test_history_accepts_user_and_assistant_turns(self):
        schema = QuerySchema(
            query="那华东呢？",
            history=[
                {"role": "user", "content": "查询各地区销售额"},
                {"role": "assistant", "content": "查询结果：华东 100"},
            ],
        )

        self.assertEqual(len(schema.history), 2)

    def test_session_id_is_optional(self):
        schema = QuerySchema(query="查询各地区销售额", session_id="session-123")

        self.assertEqual(schema.session_id, "session-123")

    def test_history_rejects_more_than_twelve_items(self):
        history = [
            {"role": "user", "content": f"问题 {index}"}
            for index in range(13)
        ]

        with self.assertRaises(ValidationError):
            QuerySchema(query="继续", history=history)


class ResolveQueryTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_first_turn_keeps_query_without_calling_llm(self):
        events = []
        runtime = SimpleNamespace(stream_writer=events.append)

        result = await resolve_query(
            {"query": "查询各地区销售额", "history": []},
            runtime,
        )

        self.assertEqual(result, {"query": "查询各地区销售额"})
        self.assertEqual(events[-1]["status"], "success")

    async def test_follow_up_is_rewritten_with_history(self):
        events = []
        runtime = SimpleNamespace(stream_writer=events.append)
        fake_llm = RunnableLambda(lambda _: "查询华东地区的销售额")

        with patch(
            "backend.app.agent.nodes.resolve_query.llm",
            fake_llm,
        ):
            result = await resolve_query(
                {
                    "query": "那华东呢？",
                    "history": [
                        {"role": "user", "content": "查询各地区销售额"},
                        {"role": "assistant", "content": "查询结果：华南 100，华东 80"},
                    ],
                },
                runtime,
            )

        self.assertEqual(result, {"query": "查询华东地区的销售额"})
        self.assertEqual(events[-1]["status"], "success")


class QueryServiceTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_history_is_forwarded_to_graph_state(self):
        class FakeGraph:
            input_state = None

            async def astream(self, input, context, stream_mode):
                self.input_state = input
                yield {"type": "result", "data": []}

        fake_graph = FakeGraph()
        service = QueryService(
            embedding_client=None,
            column_qdrant_repository=None,
            value_es_repository=None,
            metric_qdrant_repository=None,
            meta_mysql_repository=None,
            dw_mysql_repository=None,
        )
        history = [{"role": "user", "content": "查询各地区销售额"}]

        with patch("backend.app.services.query_service.graph", fake_graph):
            chunks = [
                chunk
                async for chunk in service.query("那华东呢？", history=history)
            ]

        self.assertEqual(fake_graph.input_state["history"], history)
        self.assertEqual(fake_graph.input_state["query"], "那华东呢？")
        self.assertIn('"type": "result"', chunks[0])

    async def test_server_memory_is_used_and_persisted_for_session(self):
        class FakeGraph:
            async def astream(self, input, context, stream_mode):
                self.input_state = input
                yield {"type": "query_resolved", "query": "查询华东地区销售额"}
                yield {"type": "result", "data": [{"销售额": 100}]}
                yield {
                    "type": "memory_record",
                    "sql": "SELECT 100",
                    "result": [{"销售额": 100}],
                }

        class FakeMemoryService:
            def __init__(self):
                self.recorded = None

            async def prepare_context(self, session_id, query):
                return SimpleNamespace(
                    history=[{"role": "user", "content": "查询各地区销售额"}],
                    estimated_tokens=20,
                    recalled_count=0,
                )

            async def record_success(self, *args, **kwargs):
                self.recorded = (args, kwargs)

        memory_service = FakeMemoryService()
        fake_graph = FakeGraph()
        service = QueryService(
            embedding_client=None,
            column_qdrant_repository=None,
            value_es_repository=None,
            metric_qdrant_repository=None,
            meta_mysql_repository=None,
            dw_mysql_repository=None,
            session_memory_service=memory_service,
        )

        with patch("backend.app.services.query_service.graph", fake_graph):
            chunks = [chunk async for chunk in service.query("那华东呢？", session_id="session-1")]

        self.assertEqual(fake_graph.input_state["history"][0]["content"], "查询各地区销售额")
        self.assertIn('"type": "session"', chunks[0])
        self.assertIn('"type": "context_resolved"', "".join(chunks))
        self.assertNotIn("memory_record", "".join(chunks))
        self.assertEqual(memory_service.recorded[0][:3], ("session-1", "那华东呢？", "查询华东地区销售额"))


if __name__ == "__main__":
    unittest.main()
