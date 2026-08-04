from typing import Literal

from pydantic import BaseModel, Field


class ConversationTurnSchema(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class QuerySchema(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    history: list[ConversationTurnSchema] = Field(default_factory=list, max_length=12)


class SessionCreateSchema(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=40)
