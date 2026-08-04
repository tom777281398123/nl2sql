"""服务端会话记忆：原始历史兜底、分析语义快照和引用找回。"""

import json
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.app.conf.app_config import RedisConfig
from backend.app.conf.logger import logger


REFERENCE_MARKERS = (
    "刚才", "之前", "前面", "上面", "此前", "以前", "上次", "其中", "还是那个", "你说的", "我说的",
)
METRIC_TERMS = ("销售额", "营业额", "订单量", "订单数", "客单价", "销量", "退款金额", "退款率")
TIME_PATTERN = re.compile(
    r"(?:今天|昨天|本周|上周|本月|上月|本季度|上季度|今年|去年|全年|近\s*\d+\s*[天月年]|20\d{2}年(?:\d{1,2}月)?)"
)
LIMIT_PATTERN = re.compile(r"(?:top\s*\d+|前\s*\d+|最多\s*\d+)", re.IGNORECASE)
DISPLAY_RESULT_LIMIT = 50
DIMENSION_TERMS = ("地区", "城市", "品类", "门店", "商品", "客户", "月份", "日期")
FILTER_TERMS = ("华东", "华南", "华北", "华中", "西南", "西北", "东北", "北京", "上海", "广州", "深圳")


@dataclass
class MemoryContext:
    """本轮提供给问题改写节点的受控历史。"""

    history: list[dict[str, str]]
    recalled_count: int
    estimated_tokens: int


class SessionMemoryService:
    """Redis-backed memory scoped to an anonymous browser session."""

    def __init__(
        self,
        redis_client: Any,
        redis_config: RedisConfig,
        *,
        token_budget: int = 1600,
        window_turns: int = 3,
        important_turns: int = 2,
        recall_turns: int = 1,
    ):
        self.redis = redis_client
        self.config = redis_config
        self.token_budget = token_budget
        self.window_turns = window_turns
        # Keep this argument for callers created before the structured memory change.
        # Important records are now recalled only when the user explicitly refers to them.
        self.important_turns = important_turns
        self.recall_turns = recall_turns

    async def prepare_context(self, session_id: str, query: str) -> MemoryContext:
        """Load, selectively compress, and optionally recall session history."""
        try:
            await self.ensure_session(session_id)
            turns = await self._load_turns(session_id)
            snapshot = await self._load_snapshot(session_id)
            successful_turns = [turn for turn in turns if self._is_context_eligible(turn)]
            active_state = self._active_state(snapshot, successful_turns)
            recalled = self._select_recalled_turns(query, successful_turns)
            history = self._build_history(successful_turns, active_state, recalled)
            history, estimated_tokens = self._trim_to_budget(history)
            return MemoryContext(
                history=history,
                recalled_count=len(recalled),
                estimated_tokens=estimated_tokens,
            )
        except Exception as exc:
            # Memory improves continuity but must not make the query API unavailable.
            logger.warning(f"会话记忆读取失败，降级为无服务端历史: {exc}")
            return MemoryContext(history=[], recalled_count=0, estimated_tokens=0)

    async def create_session(self, title: str = "新对话", session_id: str | None = None) -> dict[str, Any]:
        """Create a user-visible conversation session."""
        session_id = session_id or str(uuid.uuid4())
        existing = await self._load_session_metadata(session_id)
        if existing is not None:
            return existing

        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            "session_id": session_id,
            "title": title.strip()[:40] or "新对话",
            "created_at": now,
            "updated_at": now,
        }
        await self._save_session_metadata(metadata)
        return metadata

    async def ensure_session(self, session_id: str) -> dict[str, Any]:
        metadata = await self._load_session_metadata(session_id)
        if metadata is None:
            return await self.create_session(session_id=session_id)
        return metadata

    async def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        session_ids = await self.redis.zrevrange(self._session_index_key(), 0, limit - 1)
        sessions: list[dict[str, Any]] = []
        stale_session_ids: list[str] = []
        for session_id in session_ids:
            if isinstance(session_id, bytes):
                session_id = session_id.decode("utf-8")
            metadata = await self._load_session_metadata(session_id)
            if metadata is None:
                stale_session_ids.append(session_id)
                continue
            turns = await self._load_turns(session_id)
            sessions.append({**metadata, "turn_count": len(turns)})

        if stale_session_ids:
            await self.redis.zrem(self._session_index_key(), *stale_session_ids)
        return sessions

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        metadata = await self._load_session_metadata(session_id)
        if metadata is None:
            return None
        turns = await self._load_turns(session_id)
        messages: list[dict[str, Any]] = []
        for turn in turns:
            messages.extend(self._turn_to_display_messages(turn))
        return {"session": {**metadata, "turn_count": len(turns)}, "messages": messages}

    async def delete_session(self, session_id: str) -> bool:
        metadata = await self._load_session_metadata(session_id)
        if metadata is None:
            return False
        await self.redis.delete(
            self._session_metadata_key(session_id),
            self._turns_key(session_id),
            self._snapshot_key(session_id),
        )
        await self.redis.zrem(self._session_index_key(), session_id)
        return True

    async def record_success(
        self,
        session_id: str,
        original_query: str,
        resolved_query: str,
        *,
        sql: str | None,
        result: list[dict] | None,
    ) -> None:
        """Persist a completed turn; only result-bearing turns update context memory."""
        try:
            turns = await self._load_turns(session_id)
            snapshot = await self._load_snapshot(session_id)
            metadata = await self.ensure_session(session_id)
            referenced_turns = self._select_recalled_turns(
                original_query,
                [turn for turn in turns if self._is_context_eligible(turn)],
            )
            for referenced_turn in referenced_turns:
                reference_count = int(referenced_turn.get("reference_count", 0)) + 1
                referenced_turn["reference_count"] = reference_count
            has_rows = bool(result)
            turn = {
                "original_query": original_query,
                "resolved_query": resolved_query,
                "sql": sql,
                "result_columns": list(result[0].keys()) if result else [],
                "result_row_count": len(result or []),
                "result_preview": (result or [])[:DISPLAY_RESULT_LIMIT],
                "outcome": "success" if has_rows else "empty",
                "analysis_state": self._analysis_state_from_query(resolved_query) if has_rows else None,
                "reference_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            turns.append(turn)
            if has_rows:
                snapshot = self._update_snapshot(snapshot, turn["analysis_state"])
            if metadata["title"] == "新对话":
                metadata["title"] = self._make_title(original_query)
            metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

            await self._save_turns(session_id, turns)
            await self._save_snapshot(session_id, snapshot)
            await self._save_session_metadata(metadata)
            logger.info(
                "会话记忆已保存: "
                f"session_id={session_id}, turns={len(turns)}, outcome={turn['outcome']}"
            )
        except Exception as exc:
            logger.warning(f"会话记忆写入失败，查询结果不受影响: {exc}")

    def _turns_key(self, session_id: str) -> str:
        return f"{self.config.key_prefix}:session:{session_id}:turns"

    def _session_index_key(self) -> str:
        return f"{self.config.key_prefix}:sessions"

    def _session_metadata_key(self, session_id: str) -> str:
        return f"{self.config.key_prefix}:session:{session_id}:metadata"

    def _snapshot_key(self, session_id: str) -> str:
        return f"{self.config.key_prefix}:session:{session_id}:snapshot"

    async def _load_turns(self, session_id: str) -> list[dict[str, Any]]:
        values = await self.redis.lrange(self._turns_key(session_id), 0, -1)
        return [self._decode_json(value) for value in values]

    async def _load_snapshot(self, session_id: str) -> dict[str, Any]:
        value = await self.redis.get(self._snapshot_key(session_id))
        return self._decode_json(value) if value else {}

    async def _load_session_metadata(self, session_id: str) -> dict[str, Any] | None:
        value = await self.redis.get(self._session_metadata_key(session_id))
        return self._decode_json(value) if value else None

    async def _save_session_metadata(self, metadata: dict[str, Any]) -> None:
        session_id = metadata["session_id"]
        await self.redis.set(
            self._session_metadata_key(session_id),
            json.dumps(metadata, ensure_ascii=False),
            ex=self.config.session_ttl_seconds,
        )
        await self.redis.zadd(
            self._session_index_key(),
            {session_id: datetime.fromisoformat(metadata["updated_at"]).timestamp()},
        )

    async def _save_turns(self, session_id: str, turns: list[dict[str, Any]]) -> None:
        key = self._turns_key(session_id)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.delete(key)
            if turns:
                pipe.rpush(key, *[json.dumps(turn, ensure_ascii=False, default=str) for turn in turns])
            pipe.expire(key, self.config.session_ttl_seconds)
            await pipe.execute()

    async def _save_snapshot(self, session_id: str, snapshot: dict[str, Any]) -> None:
        await self.redis.set(
            self._snapshot_key(session_id),
            json.dumps(snapshot, ensure_ascii=False),
            ex=self.config.session_ttl_seconds,
        )

    @staticmethod
    def _decode_json(value: str | bytes) -> dict[str, Any]:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        decoded = json.loads(value)
        if not isinstance(decoded, dict):
            raise ValueError("会话记忆数据格式错误")
        return decoded

    def _select_recalled_turns(
        self, query: str, turns: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not any(marker in query for marker in REFERENCE_MARKERS):
            return []

        query_terms = self._search_terms(query)
        query_filters = {term for term in FILTER_TERMS if term in query}
        scored: list[tuple[int, int, dict[str, Any]]] = []
        for index, turn in enumerate(turns):
            state = turn.get("analysis_state") or {}
            content = " ".join(
                [
                    str(turn.get("resolved_query", "")),
                    str(state.get("metric", "")),
                    str(state.get("time_range", "")),
                    " ".join(state.get("dimensions", [])),
                    " ".join(state.get("filters", [])),
                ]
            )
            score = sum(term in content for term in query_terms)
            candidate_filters = set(state.get("filters", []))
            # “之前的销售额按品类看” should recover the broad sales topic rather
            # than a later follow-up that silently adds a region such as “华东”.
            if query_filters:
                score += 2 * len(query_filters & candidate_filters)
                score -= len(candidate_filters - query_filters)
            else:
                score -= 2 * len(candidate_filters)
            # A reference without a precise keyword should still recover recent facts.
            if score > 0 or not query_terms:
                scored.append((score, index, turn))

        selected = sorted(scored, key=lambda item: (item[0], item[1]), reverse=True)[
            : self.recall_turns
        ]
        if not selected and turns:
            # “前面那个” has no usable keyword. In that case, the latest successful
            # analysis is the only defensible reference target.
            selected = [(0, len(turns) - 1, turns[-1])]
        return [turn for _, _, turn in sorted(selected, key=lambda item: item[1])]

    def _build_history(
        self,
        turns: list[dict[str, Any]],
        active_state: dict[str, Any] | None,
        recalled: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        # An explicit historical reference selects a topic. Do not inject the current
        # state or recent unrelated turns alongside it.
        if active_state and not recalled:
            history.append(
                {
                    "role": "assistant",
                    "content": "当前分析状态（仅用于连续追问；当前问题明确给出新条件时必须覆盖）：\n"
                    + json.dumps(active_state, ensure_ascii=False, separators=(",", ":")),
                }
            )

        selected_ids: set[int] = set()
        selected_turns: list[tuple[dict[str, Any], str]] = []

        def add_turn(turn: dict[str, Any], prefix: str) -> None:
            if id(turn) not in selected_ids:
                selected_ids.add(id(turn))
                selected_turns.append((turn, prefix))

        # Old records are only injected after an explicit reference, preventing topic pollution.
        for turn in recalled:
            add_turn(turn, "找回的历史分析记录")
        if not recalled:
            for turn in turns[-self.window_turns :]:
                add_turn(turn, "短期记忆（最近成功查询）")

        for turn, prefix in selected_turns:
            history.extend(self._turn_to_messages(turn, prefix))
        return history

    @staticmethod
    def _turn_to_messages(turn: dict[str, Any], prefix: str) -> list[dict[str, str]]:
        row_count = turn.get("result_row_count", 0)
        columns = "、".join(turn.get("result_columns", [])) or "无"
        return [
            {"role": "user", "content": turn.get("original_query", "")},
            {
                "role": "assistant",
                "content": f"{prefix}：完整问题为“{turn.get('resolved_query', '')}”。"
                f"查询成功，返回 {row_count} 行，字段：{columns}。",
            },
        ]

    @staticmethod
    def _turn_to_display_messages(turn: dict[str, Any]) -> list[dict[str, Any]]:
        user_message = {
            "role": "user",
            "type": "text",
            "content": turn.get("original_query", ""),
        }
        resolved_query = str(turn.get("resolved_query", ""))
        messages: list[dict[str, Any]] = [user_message]
        if resolved_query and resolved_query != user_message["content"]:
            messages.append({"role": "assistant", "type": "context", "content": resolved_query})
        preview = turn.get("result_preview", [])
        if preview:
            assistant_message = {
                "role": "assistant",
                "type": "table",
                "columns": turn.get("result_columns") or list(preview[0].keys()),
                "rows": preview,
                "content": "",
            }
        elif turn.get("result_row_count", 0) == 0:
            assistant_message = {"role": "assistant", "type": "text", "content": "查询完成，暂无结果"}
        else:
            assistant_message = {
                "role": "assistant",
                "type": "text",
                "content": f"查询完成，共返回 {turn['result_row_count']} 行结果。",
            }
        messages.append(assistant_message)
        return messages

    @staticmethod
    def _make_title(query: str) -> str:
        compact_query = " ".join(query.split())
        return compact_query[:40] + ("..." if len(compact_query) > 40 else "")

    def _trim_to_budget(self, history: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
        selected: list[dict[str, str]] = []
        used = 0
        # Keep the compact active state first, then consume the selected short-term or recalled turns.
        for message in history:
            estimate = self._estimate_tokens(message["content"])
            if estimate > self.token_budget and not selected:
                max_characters = max(1, math.floor(self.token_budget / 0.65))
                content = message["content"][:max_characters]
                selected.append({**message, "content": content})
                return selected, self._estimate_tokens(content)
            if used + estimate > self.token_budget:
                continue
            selected.append(message)
            used += estimate
        return selected, used

    @staticmethod
    def _estimate_tokens(content: str) -> int:
        # Conservative approximation for mixed Chinese and English prompts without model-specific tokenizers.
        return max(1, math.ceil(len(content) * 0.65))

    @staticmethod
    def _search_terms(query: str) -> set[str]:
        text = query
        for marker in REFERENCE_MARKERS:
            text = text.replace(marker, "")
        chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
        terms = set(re.findall(r"[A-Za-z0-9_]+", text))
        terms.update(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
        terms.update(term for term in METRIC_TERMS if term in query)
        terms.update(TIME_PATTERN.findall(query))
        return {term for term in terms if len(term) >= 2}

    @staticmethod
    def _is_context_eligible(turn: dict[str, Any]) -> bool:
        """Empty result sets remain visible in history but never drive later queries."""
        return turn.get("outcome") == "success" or (
            "outcome" not in turn and int(turn.get("result_row_count", 0)) > 0
        )

    def _active_state(
        self, snapshot: dict[str, Any], successful_turns: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        active = snapshot.get("active_analysis")
        if isinstance(active, dict):
            return active
        if successful_turns:
            latest = successful_turns[-1]
            return latest.get("analysis_state") or self._analysis_state_from_query(
                str(latest.get("resolved_query", ""))
            )
        return None

    @staticmethod
    def _analysis_state_from_query(query: str) -> dict[str, Any]:
        """Create a replaceable middle-memory state from a complete resolved query."""
        metrics = [term for term in METRIC_TERMS if term in query]
        time_ranges = TIME_PATTERN.findall(query)
        dimensions = [term for term in DIMENSION_TERMS if term in query]
        filters = [term for term in FILTER_TERMS if term in query]
        limit = LIMIT_PATTERN.findall(query)

        state: dict[str, Any] = {"resolved_query": query}
        if metrics:
            state["metric"] = metrics[-1]
        if time_ranges:
            state["time_range"] = time_ranges[-1]
        if dimensions:
            state["dimensions"] = dimensions
        if filters:
            state["filters"] = filters
        if limit:
            state["limit"] = limit[-1]
        if any(term in query for term in ("最高", "降序", "从高到低")):
            state["sort"] = "descending"
        elif any(term in query for term in ("最低", "升序", "从低到高")):
            state["sort"] = "ascending"
        return state

    @staticmethod
    def _update_snapshot(snapshot: dict[str, Any], analysis_state: dict[str, Any] | None) -> dict[str, Any]:
        if not analysis_state:
            return snapshot
        return {"version": 2, "active_analysis": analysis_state}
