from urllib.parse import urlsplit, urlunsplit

from langchain.chat_models import init_chat_model
from openai import APIStatusError

from backend.app.conf.app_config import app_config


def _normalize_openai_base_url(base_url: str) -> str:
    if not base_url:
        return base_url

    parts = urlsplit(base_url)
    path = (parts.path or "").rstrip("/")
    if path.endswith("/v1"):
        return base_url.rstrip("/")

    normalized_path = f"{path}/v1" if path else "/v1"
    return urlunsplit((parts.scheme, parts.netloc, normalized_path, parts.query, parts.fragment))


llm = init_chat_model(
    model=app_config.llm.model_name,
    model_provider="openai",
    api_key=app_config.llm.api_key,
    base_url=_normalize_openai_base_url(app_config.llm.base_url),
    temperature=0,
)


if __name__ == '__main__':
    try:
        for chunk in llm.stream("你好"):
            print(chunk.text)
    except APIStatusError as exc:
        print(f"status_code={exc.status_code}")
        print(exc.message)
        if exc.response is not None:
            print(exc.response.text)
        raise
