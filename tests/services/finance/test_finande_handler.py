import pytest
from unittest.mock import AsyncMock, patch
from app.services.finance import finande_handler

@pytest.mark.asyncio
async def test_handle_financing_intent_generates_response():
    user_query = "¿Cuánto pagaría al mes por un auto de $300,000 MXN?"
    fake_response = "Pagando un enganche del 20% y con un interés del 13%, tu mensualidad sería de aproximadamente $7,500 MXN."

    with patch.object(finande_handler.llm, 'generate_response', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = fake_response
        result = await finande_handler.handle_financing_intent(user_query)

        assert result == fake_response
        mock_generate.assert_awaited_once_with([
            {"role": "system", "content": finande_handler.FINANCE_PROMPT},
            {"role": "user", "content": user_query},
        ])