from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm.openai_client import OpenAIClient
from app.utils.openai_utils import DEFAULT_CHAT_MODEL


@pytest.mark.asyncio
async def test_generate_response_creates_client_and_returns_message():
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = " Hello world "
    mock_client.chat.completions.create.return_value = mock_response

    with patch(
        "app.services.llm.openai_client.get_openai_client", return_value=mock_client
    ):
        client = OpenAIClient()
        result = await client.generate_response([{"role": "user", "content": "Hello"}])

    assert result == "Hello world"
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_response_uses_existing_client():
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = " Already here "
    mock_client.chat.completions.create.return_value = mock_response

    client = OpenAIClient()
    client.client = mock_client  # set client directly

    result = await client.generate_response([{"role": "user", "content": "Hi"}])

    assert result == "Already here"
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_interpret_returns_default_intent():
    client = OpenAIClient()
    result = await client.interpret("Tell me a joke.")
    assert result == {"intent": "default", "message": "Tell me a joke."}


@pytest.mark.asyncio
async def test_never_sends_temperature_and_asks_for_no_reasoning(monkeypatch):
    """The gpt-5 line answers 400 for any temperature but the default."""
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "ok"
    mock_client.chat.completions.create.return_value = mock_response

    client = OpenAIClient()
    client.client = mock_client
    await client.generate_response([{"role": "user", "content": "Hi"}])

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "temperature" not in kwargs
    assert kwargs["model"] == DEFAULT_CHAT_MODEL
    assert kwargs["reasoning_effort"] == "none"


@pytest.mark.asyncio
async def test_reasoning_effort_is_omitted_when_blanked_out(monkeypatch):
    """A model that rejects the parameter outright needs it gone, not defaulted."""
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "")
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "ok"
    mock_client.chat.completions.create.return_value = mock_response

    client = OpenAIClient()
    client.client = mock_client
    await client.generate_response([{"role": "user", "content": "Hi"}])

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "reasoning_effort" not in kwargs
    assert "temperature" not in kwargs
    assert kwargs["model"] == "gpt-4o"
