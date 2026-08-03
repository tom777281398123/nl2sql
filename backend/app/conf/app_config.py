"""从 YAML 和环境变量加载应用基础设施配置。"""

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from omegaconf import OmegaConf

# 在解析 ${oc.env:...} 插值前，先把 .env 加载进 os.environ
load_dotenv()


# 日志配置
@dataclass
class File:
    """文件日志输出配置。"""
    enable: bool
    level: str
    path: str
    rotation: str
    retention: str


@dataclass
class Console:
    """控制台日志输出配置。"""
    enable: bool
    level: str


@dataclass
class LoggingConfig:
    """应用日志配置集合。"""
    file: File
    console: Console


# 数据库配置
@dataclass
class DBConfig:
    """单个 MySQL 数据源的连接参数。"""
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class QdrantConfig:
    """Qdrant 服务地址及向量维度。"""
    host: str
    port: int
    embedding_size: int


@dataclass
class EmbeddingConfig:
    """Embedding 服务地址与模型标识。"""
    host: str
    port: int
    model: str


@dataclass
class ESConfig:
    """Elasticsearch 服务与索引配置。"""
    host: str
    port: int
    index_name: str


@dataclass
class LLMConfig:
    """OpenAI 兼容聊天模型配置。"""
    model_name: str
    api_key: str
    base_url: str
    user_agent: str


@dataclass
class AppConfig:
    """应用运行所需的全部基础设施配置。"""
    logging: LoggingConfig
    db_meta: DBConfig
    db_dw: DBConfig
    qdrant: QdrantConfig
    embedding: EmbeddingConfig
    es: ESConfig
    llm: LLMConfig
    judge_llm: LLMConfig


config_file = Path(__file__).parents[2] / 'conf' / 'app_config.yaml'
context = OmegaConf.load(config_file)
schema = OmegaConf.structured(AppConfig)
app_config: AppConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))

if __name__ == '__main__':
    print(app_config.es.host)
