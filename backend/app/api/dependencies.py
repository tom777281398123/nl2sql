from fastapi import Depends
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.clients.embedding_client_manager import embedding_client_manager
from backend.app.clients.es_client_manager import es_client_manager
from backend.app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from backend.app.clients.qdrant_client_manager import qdrant_client_manager
from backend.app.clients.redis_client_manager import redis_client_manager
from backend.app.conf.app_config import app_config
from backend.app.repositories.es.value_es_repository import ValueESRepository
from backend.app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from backend.app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from backend.app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from backend.app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from backend.app.services.query_service import QueryService
from backend.app.services.session_memory_service import SessionMemoryService


async def get_meta_session():
    async with meta_mysql_client_manager.session_factory() as session:
        yield session


async def get_dw_session():
    async with dw_mysql_client_manager.session_factory() as session:
        yield session


async def get_embedding_client():
    return embedding_client_manager.client


async def get_column_qdrant_repository():
    return ColumnQdrantRepository(qdrant_client_manager.client)


async def get_value_es_repository():
    return ValueESRepository(es_client_manager.client)


async def get_metric_qdrant_repository():
    return MetricQdrantRepository(qdrant_client_manager.client)


async def get_meta_mysql_repository(session: AsyncSession = Depends(get_meta_session)):
    return MetaMySQLRepository(session)


async def get_dw_mysql_repository(session: AsyncSession = Depends(get_dw_session)):
    return DWMySQLRepository(session)


async def get_session_memory_service():
    return SessionMemoryService(redis_client_manager.client, app_config.redis)


async def get_query_service(
        embedding_client: HuggingFaceEndpointEmbeddings = Depends(get_embedding_client),
        column_qdrant_repository: ColumnQdrantRepository = Depends(get_column_qdrant_repository),
        value_es_repository: ValueESRepository = Depends(get_value_es_repository),
        metric_qdrant_repository: MetricQdrantRepository = Depends(get_metric_qdrant_repository),
        meta_mysql_repository: MetaMySQLRepository = Depends(get_meta_mysql_repository),
        dw_mysql_repository: DWMySQLRepository = Depends(get_dw_mysql_repository),
        session_memory_service: SessionMemoryService = Depends(get_session_memory_service),
) -> QueryService:
    return QueryService(
        embedding_client=embedding_client,
        column_qdrant_repository=column_qdrant_repository,
        value_es_repository=value_es_repository,
        metric_qdrant_repository=metric_qdrant_repository,
        meta_mysql_repository=meta_mysql_repository,
        dw_mysql_repository=dw_mysql_repository,
        session_memory_service=session_memory_service,
    )
