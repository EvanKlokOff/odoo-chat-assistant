# src/cache/redis_client.py
import redis_db.asyncio as redis
from typing import Optional, Any, Dict, List
import json
import logging


logger = logging.getLogger(__name__)


class RedisClient:
    """Асинхронный клиент для Redis"""

    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self._pool: Optional[redis.ConnectionPool] = None

    async def connect(self, url: str = "redis_db://localhost:6379/0"):
        """Установка соединения с Redis"""
        try:
            self._pool = redis.ConnectionPool.from_url(
                url,
                max_connections=50,
                decode_responses=True
            )
            self.redis = redis.Redis(connection_pool=self._pool)

            # Проверяем соединение
            await self.redis.ping()
            logger.info("Successfully connected to Redis")
            return self.redis
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Закрытие соединения"""
        if self.redis:
            await self.redis.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[Any]:
        """Получить значение по ключу"""
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None

    async def set(
            self,
            key: str,
            value: Any,
            ttl: Optional[int] = None
    ) -> bool:
        """Установить значение с опциональным TTL"""
        try:
            serialized = json.dumps(value, default=str)
            if ttl:
                await self.redis.setex(key, ttl, serialized)
            else:
                await self.redis.set(key, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Удалить ключ"""
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Проверить существование ключа"""
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """Установить TTL для ключа"""
        try:
            return await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False

    async def lpush(self, key: str, *values) -> int:
        """Добавить элементы в начало списка"""
        try:
            serialized = [json.dumps(v, default=str) for v in values]
            return await self.redis.lpush(key, *serialized)
        except Exception as e:
            logger.error(f"Redis lpush error for key {key}: {e}")
            return 0

    async def lrange(self, key: str, start: int, end: int) -> List[Any]:
        """Получить элементы списка"""
        try:
            values = await self.redis.lrange(key, start, end)
            return [json.loads(v) for v in values]
        except Exception as e:
            logger.error(f"Redis lrange error for key {key}: {e}")
            return []

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """Обрезать список"""
        try:
            await self.redis.ltrim(key, start, end)
            return True
        except Exception as e:
            logger.error(f"Redis ltrim error for key {key}: {e}")
            return False

    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Установить значение в хэше"""
        try:
            serialized = json.dumps(value, default=str)
            await self.redis.hset(key, field, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis hset error for key {key}: {e}")
            return False

    async def hget(self, key: str, field: str) -> Optional[Any]:
        """Получить значение из хэша"""
        try:
            value = await self.redis.hget(key, field)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis hget error for key {key}: {e}")
            return None

    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Получить весь хэш"""
        try:
            data = await self.redis.hgetall(key)
            return {k: json.loads(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Redis hgetall error for key {key}: {e}")
            return {}


# Глобальный экземпляр
redis_client = RedisClient()