import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
from openai import AsyncOpenAI


_redis_client = None
_mongo_client = None
_openai_client = None


async def get_redis_client(redis_url="redis://redis:6379"):
    """Initialize and return a singleton Redis client.

    Args:
        redis_url (str): Redis connection URL.

    Returns:
        Redis: A Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(redis_url, decode_responses=True)
    return _redis_client


async def get_mongo_client(mongo_url="mongodb://mongo:27017/kabot"):
    """Initialize and return a singleton MongoDB client.

    Args:
        mongo_url (str): MongoDB connection URL.

    Returns:
        AsyncIOMotorClient: An asynchronous MongoDB client instance.
    """
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(mongo_url)
    return _mongo_client


async def get_openai_client():
    """Initialize and return a singleton OpenAI client.

    Returns:
        AsyncOpenAI: An asynchronous OpenAI client instance.
    """
    global _openai_client
    if _openai_client is None:
        import os

        api_key = os.getenv("OPENAI_API_KEY")
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client
