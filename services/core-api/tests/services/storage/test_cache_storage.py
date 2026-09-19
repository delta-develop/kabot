import pytest
from unittest.mock import AsyncMock
import json

from app.services.storage.cache_storage import CacheStorage

@pytest.fixture
def cache():
    return CacheStorage(namespace="test")

@pytest.mark.asyncio
async def test_make_key(cache):
    assert cache._make_key("example") == "test:example"

@pytest.mark.asyncio
async def test_set_and_get(cache, mocker):
    mock_redis = AsyncMock()
    mocker.patch("app.services.storage.cache_storage.get_redis_client", return_value=mock_redis)
    mock_redis.get.return_value = json.dumps({"foo": "bar"})

    await cache.set("key1", {"foo": "bar"})
    value = await cache.get("key1")

    mock_redis.set.assert_called_once()
    assert value == {"foo": "bar"}

@pytest.mark.asyncio
async def test_delete(cache, mocker):
    mock_redis = AsyncMock()
    mocker.patch("app.services.storage.cache_storage.get_redis_client", return_value=mock_redis)

    await cache.delete("key2")
    mock_redis.delete.assert_called_once_with("test:key2")

@pytest.mark.asyncio
async def test_append_interaction(cache, mocker):
    mock_redis = AsyncMock()
    mocker.patch("app.services.storage.cache_storage.get_redis_client", return_value=mock_redis)
    mock_redis.get.return_value = None

    await cache.append_interaction("conv1", "Hi", "Hello!")
    expected = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    mock_redis.set.assert_called_once()
    args, kwargs = mock_redis.set.call_args
    assert "test:conv1" in args[0]
    actual = json.loads(args[1])
    assert expected == actual

@pytest.mark.asyncio
async def test_get_raw(cache, mocker):
    mock_redis = AsyncMock()
    mocker.patch("app.services.storage.cache_storage.get_redis_client", return_value=mock_redis)
    mock_redis.get.return_value = b'raw_string'

    raw_value = await cache.get_raw("key3")
    assert raw_value == b'raw_string'