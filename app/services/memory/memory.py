import redis.asyncio as aioredis
import json
from typing import Any, Optional
from .base import WorkingMemoryBase


class RedisWorkingMemory(WorkingMemoryBase):
    def __init__(self, redis_url: str = "redis://redis:6379", namespace: str = "memory"):
        self.redis_url = redis_url
        self.namespace = namespace
        self.redis = None

    async def _get_redis(self):
        if self.redis is None:
            self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self.redis

    def _make_key(self, key: str) -> str:
        return f"{self.namespace}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        redis = await self._get_redis()
        data = await redis.get(self._make_key(key))
        if data is not None:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return None

    async def set(self, key: str, value: Any, ttl: int = 0) -> None:
        redis = await self._get_redis()
        data = json.dumps(value)
        namespaced_key = self._make_key(key)
        if ttl > 0:
            await redis.set(namespaced_key, data, ex=ttl)
        else:
            await redis.set(namespaced_key, data)

    async def delete(self, key: str) -> None:
        redis = await self._get_redis()
        await redis.delete(self._make_key(key))
        
    async def append_turn(self, key: str, role: str, content: str) -> None:
        redis = await self._get_redis()

        current = await self.get(key) or []
        current.append({"role": role, "content": content})

        await self.set(key, current)