from typing import Optional

from redis.asyncio import Redis

from backend.app.conf.app_config import RedisConfig, app_config


class RedisClientManager:
    """管理会话记忆使用的异步 Redis 客户端。"""

    def __init__(self, redis_config: RedisConfig):
        self.redis_config = redis_config
        self.client: Optional[Redis] = None

    def init(self):
        self.client = Redis(
            host=self.redis_config.host,
            port=self.redis_config.port,
            db=self.redis_config.db,
            decode_responses=True,
        )

    async def close(self):
        if self.client is not None:
            await self.client.aclose()


redis_client_manager = RedisClientManager(app_config.redis)
