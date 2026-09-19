import json
from typing import Any

from app.services.storage.connections import get_redis_client


class CacheStorage:
    """Handles caching operations with Redis for namespaced memory interactions."""

    def __init__(self, namespace="memory"):
        """
        Initializes a new instance of CacheStorage.

        Args:
            namespace (str): The namespace prefix for Redis keys.
        """
        self.namespace = namespace

    async def _get_redis(self):
        """
        Retrieves a Redis client connection.

        Returns:
            Redis client instance.
        """
        return await get_redis_client()

    def _make_key(self, key: str) -> str:
        """
        Constructs a namespaced Redis key.

        Args:
            key (str): The base key.

        Returns:
            str: The namespaced key.
        """
        return f"{self.namespace}:{key}"

    async def get(self, key: str) -> Any:
        """
        Retrieves and deserializes the value for the given key from Redis.

        Args:
            key (str): The key to retrieve.

        Returns:
            Any: The deserialized value or None if not found.
        """
        redis = await self._get_redis()
        data = await redis.get(self._make_key(key))
        if data is not None:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return None

    async def set(self, key: str, value: Any, ttl: int = 0) -> None:
        """
        Serializes and stores a value in Redis under the specified key.

        Args:
            key (str): The key under which to store the value.
            value (Any): The value to store.
            ttl (int): Time to live in seconds. If 0, the key does not expire.
        """
        redis = await self._get_redis()
        data = json.dumps(value)
        namespaced_key = self._make_key(key)
        if ttl > 0:
            await redis.set(namespaced_key, data, ex=ttl)
        else:
            await redis.set(namespaced_key, data)

    async def delete(self, key: str) -> None:
        """
        Deletes a key from Redis.

        Args:
            key (str): The key to delete.
        """
        redis = await self._get_redis()
        await redis.delete(self._make_key(key))

    async def append_interaction(
        self, key: str, user_msg: str, assistant_msg: str
    ) -> None:
        """
        Appends a user and assistant interaction to a Redis list.

        Args:
            key (str): The key representing the conversation.
            user_msg (str): The user's message.
            assistant_msg (str): The assistant's reply.
        """
        redis = await self._get_redis()
        current = await self.get(key) or []
        current.append({"role": "user", "content": user_msg})
        current.append({"role": "assistant", "content": assistant_msg})
        await self.set(key, current)

    async def get_raw(self, key: str) -> str:
        """
        Retrieves the raw (unparsed) Redis value for a given key.

        Args:
            key (str): The key to retrieve.

        Returns:
            str: The raw string value stored in Redis.
        """
        redis = await self._get_redis()
        return await redis.get(self._make_key(key))
