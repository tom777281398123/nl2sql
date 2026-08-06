import json
import unittest
from types import SimpleNamespace

from backend.app.services.session_memory_service import SessionMemoryService


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.operations = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def delete(self, key):
        self.operations.append(("delete", key))

    def rpush(self, key, *values):
        self.operations.append(("rpush", key, values))

    def expire(self, key, seconds):
        self.operations.append(("expire", key, seconds))

    async def execute(self):
        for operation in self.operations:
            if operation[0] == "delete":
                self.redis.values.pop(operation[1], None)
            elif operation[0] == "rpush":
                self.redis.values.setdefault(operation[1], []).extend(operation[2])
        return []


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.sorted_sets = {}

    async def lrange(self, key, start, end):
        return self.values.get(key, [])

    async def get(self, key):
        value = self.values.get(key)
        return value if isinstance(value, str) else None

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    async def set(self, key, value, ex):
        self.values[key] = value

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)

    async def zadd(self, key, mapping):
        self.sorted_sets.setdefault(key, {}).update(mapping)

    async def zrevrange(self, key, start, end):
        values = sorted(self.sorted_sets.get(key, {}).items(), key=lambda item: item[1], reverse=True)
        return [session_id for session_id, _ in values[start : end + 1]]

    async def zrem(self, key, *members):
        values = self.sorted_sets.get(key, {})
        for member in members:
            values.pop(member, None)


class SessionMemoryServiceTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.service = SessionMemoryService(
            self.redis,
            SimpleNamespace(
                key_prefix="test:memory",
                session_ttl_seconds=3600,
            ),
            token_budget=500,
            window_turns=1,
            important_turns=1,
        )

    async def test_successful_turn_is_persisted_and_used_as_context(self):
        await self.service.record_success(
            "session-a",
            "查询去年各地区销售额",
            "查询去年各地区的销售额",
            sql="SELECT 1",
            result=[{"地区": "华东", "销售额": 100}],
        )

        context = await self.service.prepare_context("session-a", "那华东呢？")

        self.assertTrue(context.history)
        self.assertIn("查询去年各地区的销售额", json.dumps(context.history, ensure_ascii=False))
        self.assertIn("active_analysis", (await self.service._load_snapshot("session-a")))

    async def test_reference_recalls_early_turn_outside_window(self):
        await self.service.record_success(
            "session-a", "查询去年销售额", "查询去年各地区销售额", sql="SELECT 1", result=[{"销售额": 100}]
        )
        await self.service.record_success(
            "session-a", "查询今年订单量", "查询今年各地区订单量", sql="SELECT 2", result=[{"订单量": 200}]
        )

        context = await self.service.prepare_context("session-a", "之前的销售额按城市看")

        rendered = json.dumps(context.history, ensure_ascii=False)
        self.assertGreaterEqual(context.recalled_count, 1)
        self.assertIn("查询去年各地区销售额", rendered)

        await self.service.record_success(
            "session-a",
            "之前的销售额按城市看",
            "查询去年各城市销售额",
            sql="SELECT 3",
            result=[],
        )
        stored_turns = await self.service._load_turns("session-a")
        self.assertEqual(stored_turns[0]["reference_count"], 1)

    async def test_short_memory_contains_recent_successful_turns_only(self):
        service = SessionMemoryService(
            self.redis,
            SimpleNamespace(key_prefix="test:short", session_ttl_seconds=3600),
            token_budget=1000,
            window_turns=3,
        )
        for index in range(4):
            await service.record_success(
                "session-short",
                f"查询第 {index} 个问题",
                f"查询第 {index} 个销售额问题",
                sql="SELECT 1",
                result=[{"销售额": index}],
            )

        rendered = json.dumps((await service.prepare_context("session-short", "继续")).history, ensure_ascii=False)

        self.assertNotIn("查询第 0 个销售额问题", rendered)
        self.assertIn("查询第 1 个销售额问题", rendered)
        self.assertIn("查询第 3 个销售额问题", rendered)

    async def test_middle_memory_replaces_active_state_instead_of_accumulating_topics(self):
        await self.service.record_success(
            "session-state", "查询去年各地区销售额", "查询去年各地区销售额", sql="SELECT 1", result=[{"销售额": 100}]
        )
        await self.service.record_success(
            "session-state", "查询全年各地区订单量", "查询全年各地区订单量", sql="SELECT 2", result=[{"订单量": 200}]
        )

        snapshot = await self.service._load_snapshot("session-state")
        active = snapshot["active_analysis"]

        self.assertEqual(active["metric"], "订单量")
        self.assertEqual(active["time_range"], "全年")
        self.assertNotIn("销售额", active.values())

    async def test_historical_recall_does_not_restore_an_unmentioned_region_filter(self):
        await self.service.record_success(
            "session-filter",
            "查询去年各地区销售额",
            "查询去年各地区销售额",
            sql="SELECT 1",
            result=[{"销售额": 100}],
        )
        await self.service.record_success(
            "session-filter",
            "那华东呢？",
            "查询去年华东地区销售额",
            sql="SELECT 2",
            result=[{"销售额": 80}],
        )

        context = await self.service.prepare_context("session-filter", "之前的销售额按品类看")
        rendered = json.dumps(context.history, ensure_ascii=False)

        self.assertEqual(context.recalled_count, 1)
        self.assertIn("查询去年各地区销售额", rendered)
        self.assertNotIn("查询去年华东地区销售额", rendered)

    async def test_empty_result_does_not_replace_middle_memory(self):
        await self.service.record_success(
            "session-empty", "查询去年各地区销售额", "查询去年各地区销售额", sql="SELECT 1", result=[{"销售额": 100}]
        )
        await self.service.record_success(
            "session-empty", "查询今年各地区订单量", "查询今年各地区订单量", sql="SELECT 2", result=[]
        )

        snapshot = await self.service._load_snapshot("session-empty")
        turns = await self.service._load_turns("session-empty")

        self.assertEqual(snapshot["active_analysis"]["metric"], "销售额")
        self.assertEqual(turns[-1]["outcome"], "empty")

    async def test_context_respects_token_budget(self):
        service = SessionMemoryService(
            self.redis,
            SimpleNamespace(key_prefix="test:small", session_ttl_seconds=3600),
            token_budget=60,
        )
        for index in range(4):
            await service.record_success(
                "session-b",
                f"查询第 {index} 个很长的分析问题" * 4,
                f"查询第 {index} 个很长的销售额分析问题" * 4,
                sql="SELECT 1",
                result=[{"销售额": index}],
            )

        context = await service.prepare_context("session-b", "继续")

        self.assertLessEqual(context.estimated_tokens, 60)

    async def test_session_crud_restores_display_messages(self):
        session = await self.service.create_session("销售分析")
        session_id = session["session_id"]
        await self.service.record_success(
            session_id,
            "查询去年各地区销售额",
            "查询去年各地区销售额",
            sql="SELECT 1",
            result=[{"地区": "华东", "销售额": 100}],
        )

        sessions = await self.service.list_sessions()
        detail = await self.service.get_session(session_id)

        self.assertEqual(sessions[0]["title"], "销售分析")
        self.assertEqual(detail["session"]["turn_count"], 1)
        self.assertEqual(detail["messages"][0]["content"], "查询去年各地区销售额")
        self.assertEqual(detail["messages"][1]["type"], "table")
        self.assertTrue(await self.service.delete_session(session_id))
        self.assertIsNone(await self.service.get_session(session_id))


if __name__ == "__main__":
    unittest.main()
