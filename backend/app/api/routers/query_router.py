import uuid

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.params import Depends
from starlette.responses import StreamingResponse

from backend.app.api.dependencies import get_query_service, get_session_memory_service
from backend.app.api.schemas.query_schema import QuerySchema, SessionCreateSchema
from backend.app.conf.logger import logger
from backend.app.services.query_service import QueryService
from backend.app.services.session_memory_service import SessionMemoryService

query_router = APIRouter()


@query_router.get("/api/sessions")
async def list_sessions(memory_service: SessionMemoryService = Depends(get_session_memory_service)):
    return {"sessions": await memory_service.list_sessions()}


@query_router.post("/api/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    schema: SessionCreateSchema,
    memory_service: SessionMemoryService = Depends(get_session_memory_service),
):
    return await memory_service.create_session(schema.title)


@query_router.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    memory_service: SessionMemoryService = Depends(get_session_memory_service),
):
    session = await memory_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在或已过期")
    return session


@query_router.delete("/api/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    memory_service: SessionMemoryService = Depends(get_session_memory_service),
):
    if not await memory_service.delete_session(session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在或已过期")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@query_router.post("/api/query")
async def query(
    schema: QuerySchema, query_service: QueryService = Depends(get_query_service)
):
    session_id = schema.session_id or str(uuid.uuid4())
    logger.info(
        f"收到查询请求，session_id={session_id}, query={schema.query!r}, "
        f"history_count={len(schema.history)}"
    )
    return StreamingResponse(
        query_service.query(
            schema.query,
            session_id=session_id,
            history=[turn.model_dump() for turn in schema.history],
        ),
        media_type="text/event-stream",
    )
