import os

import redis.asyncio as aioredis
from openai import AsyncOpenAI
from pymongo import AsyncMongoClient
from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017/elephant")

# redis-py applies this timeout to the socket read of a blocking command, so a
# BLOCK of N seconds reads for N seconds against a perfectly healthy server. Left
# at the default of `block` itself, XREADGROUP loses that race every time the
# stream is idle and kills the worker. It has to outlast the longest blocking
# call, which is `consolidation.BLOCK_MS`.
REDIS_SOCKET_TIMEOUT = int(os.getenv("REDIS_SOCKET_TIMEOUT", "30"))

_redis_client = None
_mongo_client = None
_openai_client = None
_typesafe_client = None


async def get_redis_client(redis_url=REDIS_URL):
    """Initialize and return a singleton Redis client.

    Args:
        redis_url (str): Redis connection URL.

    Returns:
        Redis: A Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
        )
    return _redis_client


async def get_mongo_client(mongo_url=MONGO_URL):
    """Initialize and return a singleton MongoDB client.

    Args:
        mongo_url (str): MongoDB connection URL.

    Returns:
        AsyncMongoClient: An asynchronous MongoDB client instance.
    """
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncMongoClient(mongo_url)
    return _mongo_client


async def get_openai_client():
    """Initialize and return a singleton OpenAI client.

    Returns:
        AsyncOpenAI: An asynchronous OpenAI client instance.
    """
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


async def get_typesafe_client():
    """Initialize and return a singleton TypeSafe client.

    Returns:
        AsyncTypeSafeClient: An asynchronous TypeSafe client instance.
    """
    global _typesafe_client
    if _typesafe_client is None:
        # The re-rank sits in the hot path of every chat turn and its fallback is
        # the cosine order recall already had, so a dead service must cost close
        # to nothing. Measured against the SDK defaults — 10 s per attempt, two
        # retries — an outage costs 31.4 s per turn against the 215 ms the call
        # takes when it answers. RetryPolicy's total budget stops the next
        # attempt, it never cuts the one in flight, so the only real lever is
        # timeout x (retries + 1): one attempt, 1.5 s.
        _typesafe_client = AsyncTypeSafeClient(
            timeout=1.5,
            retry=RetryPolicy(max_retries=0),
        )
    return _typesafe_client
