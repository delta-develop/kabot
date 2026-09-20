from unittest.mock import AsyncMock, MagicMock

import pytest

from app.utils.openai_utils import get_embedding, get_embeddings


def embedding_response(count: int):
    return MagicMock(
        data=[MagicMock(embedding=[float(index)]) for index in range(count)]
    )


@pytest.mark.asyncio
async def test_get_embedding_wraps_single_input(mocker):
    client = AsyncMock()
    client.embeddings.create.return_value = embedding_response(1)
    mocker.patch(
        "app.utils.openai_utils.get_openai_client", AsyncMock(return_value=client)
    )

    assert await get_embedding("hello") == [0.0]
    client.embeddings.create.assert_awaited_once_with(
        input=["hello"], model="text-embedding-3-small"
    )


@pytest.mark.asyncio
async def test_get_embeddings_sends_36_inputs_in_one_call(mocker):
    client = AsyncMock()
    client.embeddings.create.return_value = embedding_response(36)
    mocker.patch(
        "app.utils.openai_utils.get_openai_client", AsyncMock(return_value=client)
    )

    await get_embeddings([f"turn {index}" for index in range(36)])

    client.embeddings.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_embeddings_batches_at_36_inputs(mocker):
    client = AsyncMock()
    client.embeddings.create.side_effect = [
        embedding_response(36),
        embedding_response(1),
    ]
    mocker.patch(
        "app.utils.openai_utils.get_openai_client", AsyncMock(return_value=client)
    )
    inputs = [f"turn {index}" for index in range(37)]

    result = await get_embeddings(inputs)

    assert len(result) == 37
    assert client.embeddings.create.await_count == 2
    assert len(client.embeddings.create.await_args_list[0].kwargs["input"]) == 36
    assert len(client.embeddings.create.await_args_list[1].kwargs["input"]) == 1


@pytest.mark.asyncio
async def test_get_embeddings_rejects_oversized_utf8_payload_before_provider(mocker):
    client = AsyncMock()
    mocker.patch(
        "app.utils.openai_utils.get_openai_client", AsyncMock(return_value=client)
    )

    with pytest.raises(ValueError, match="8,192 UTF-8 bytes"):
        await get_embeddings(["é" * 4097])

    client.embeddings.create.assert_not_awaited()
