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
    state: DataAgentState,# 对话上下文
    runtime: Runtime[DataAgentContext], # 运行时上下文
):
    # 对话问题改写
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "理解对话上下文", "status": "running"})

    query = state["query"] # 当前对话问题
    history = state.get("history", []) # 对话历史记录

    try:
        # 如果没有历史记录，则直接返回当前问题
        if not history:
            writer({"type": "query_resolved", "query": query})
            writer({"type": "progress", "step": "理解对话上下文", "status": "success"})
            return {"query": query}
        # 如果有历史记录，则使用 LLM 对当前问题进行改写
        prompt = PromptTemplate(
            template=load_prompt("resolve_query"),
            input_variables=["history", "query"],
        )
        chain = prompt | llm | StrOutputParser()
        # 调用 LLM 对当前问题进行改写
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
        # 如果改写结果为空，则抛出异常
        if not resolved_query:
            raise ValueError("对话上下文改写结果为空")
        # 将改写结果写入日志
        writer({"type": "query_resolved", "query": resolved_query})
        writer({"type": "progress", "step": "理解对话上下文", "status": "success"})
        logger.info(f"对话问题改写: {query!r} -> {resolved_query!r}")
        return {"query": resolved_query}
    except Exception as exc:
        writer({"type": "progress", "step": "理解对话上下文", "status": "error"})
        logger.error(f"对话上下文理解失败: {str(exc)}")
        raise
