"""Dedicated model client for evaluation judges."""

from langchain.chat_models import init_chat_model

from backend.app.agent.llm import _normalize_openai_base_url
from backend.app.conf.app_config import app_config


judge_llm = init_chat_model(
    model=app_config.judge_llm.model_name,
    model_provider="openai",
    api_key=app_config.judge_llm.api_key,
    base_url=_normalize_openai_base_url(app_config.judge_llm.base_url),
    default_headers={"User-Agent": app_config.judge_llm.user_agent},
    temperature=0,
)
