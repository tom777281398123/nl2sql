import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from backend.app.agent.context import DataAgentContext
from backend.app.agent.llm import llm
from backend.app.agent.state import DataAgentState
from backend.app.conf.logger import logger
from backend.app.prompt.prompt_loader import load_prompt


async def resolve_query(
    state: DataAgentState,
    runtime: Runtime[DataAgentContext],
):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "理解对话上下文", "status": "running"})

    query = state["query"]
    history = state.get("history", [])

    try:
        if not history:
            writer({"type": "progress", "step": "理解对话上下文", "status": "success"})
            return {"query": query}

        prompt = PromptTemplate(
            template=load_prompt("resolve_query"),
            input_variables=["history", "query"],
        )
        chain = prompt | llm | StrOutputParser()
        resolved_query = (
            await chain.ainvoke(
                {
                    "history": yaml.dump(
                        history,
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                    "query": query,
                }
            )
        ).strip()

        if not resolved_query:
            raise ValueError("对话上下文改写结果为空")

        writer({"type": "progress", "step": "理解对话上下文", "status": "success"})
        logger.info(f"对话问题改写: {query!r} -> {resolved_query!r}")
        return {"query": resolved_query}
    except Exception as exc:
        writer({"type": "progress", "step": "理解对话上下文", "status": "error"})
        logger.error(f"对话上下文理解失败: {str(exc)}")
        raise
