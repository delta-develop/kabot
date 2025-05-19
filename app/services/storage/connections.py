import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
from opensearchpy import AsyncOpenSearch
from openai import AsyncOpenAI


_redis_client = None
_mongo_client = None
_open_search_client: AsyncOpenSearch = None
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


async def get_open_search_client() -> AsyncOpenSearch:
    """Initialize and return a singleton OpenSearch client.

    Returns:
        AsyncOpenSearch: An asynchronous OpenSearch client instance.
    """
    global _open_search_client
    if _open_search_client is None:
        host = "opensearch-node1"
        port = 9200
        auth = ("admin", "asfASAS23rae.")
        _open_search_client = AsyncOpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
            http_auth=auth,
            use_ssl=True,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )
    return _open_search_client


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
