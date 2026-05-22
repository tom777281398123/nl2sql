from fastapi import APIRouter
from fastapi.params import Depends
from starlette.responses import StreamingResponse

from backend.app.api.dependencies import get_query_service
from backend.app.api.schemas.query_schema import QuerySchema
from backend.app.conf.logger import logger
from backend.app.services.query_service import QueryService

query_router = APIRouter()


@query_router.post("/api/query")
async def query(
    query: QuerySchema, query_service: QueryService = Depends(get_query_service)
):
    logger.info(f"收到查询请求，入参: {query}")
    return StreamingResponse(
        query_service.query(query.query), media_type="text/event-stream"
    )
