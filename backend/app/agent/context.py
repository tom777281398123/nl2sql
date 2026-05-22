from typing import TypedDict

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from backend.app.repositories.es.value_es_repository import ValueESRepository
from backend.app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from backend.app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from backend.app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from backend.app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class DataAgentContext(TypedDict):
    embedding_client: HuggingFaceEndpointEmbeddings
    column_qdrant_repository: ColumnQdrantRepository
    value_es_repository: ValueESRepository
    metric_qdrant_repository: MetricQdrantRepository
    meta_mysql_repository: MetaMySQLRepository
    dw_mysql_repository: DWMySQLRepository
