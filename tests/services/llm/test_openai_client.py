import pytest
from unittest.mock import AsyncMock, patch

from app.services.llm.openai_client import OpenAIClient

@pytest.mark.asyncio
async def test_generate_response_creates_client_and_returns_message():
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = " Hello world "
    mock_client.chat.completions.create.return_value = mock_response

    with patch("app.services.llm.openai_client.get_openai_client", return_value=mock_client):
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