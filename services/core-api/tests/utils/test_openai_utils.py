import pytest
from unittest.mock import AsyncMock, patch

from app.utils.openai_utils import get_embedding

@pytest.mark.asyncio
async def test_get_embedding():
    fake_embedding = [0.1, 0.2, 0.3]

    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=fake_embedding)]

    mock_client = AsyncMock()
    mock_client.embeddings.create.return_value = mock_response

    with patch("app.utils.openai_utils.get_openai_client", new_callable=AsyncMock) as mock_get_client:
        mock_get_client.return_value = mock_client
        result = await get_embedding("Mazda 3")
        assert result == fake_embedding
        mock_client.embeddings.create.assert_awaited_once_with(input=["Mazda 3"], model="text-embedding-3-small")