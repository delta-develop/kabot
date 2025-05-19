import json
from typing import Any, Optional
from app.services.storage.connections import get_redis_client

class CacheStorage:
    def __init__(self, namespace="memory"):
        self.namespace = namespace

    async def _get_redis(self):
        return await get_redis_client()

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

    async def append_interaction(self, key: str, user_msg: str, assistant_msg: str) -> None:
        redis = await self._get_redis()
        current = await self.get(key) or []
        current.append({"role": "user", "content": user_msg})
        current.append({"role": "assistant", "content": assistant_msg})
        await self.set(key, current)
        
    async def get_raw(self, key: str) -> Optional[str]:
        redis = await self._get_redis()
        return await redis.get(self._make_key(key))