from unittest.mock import patch

import pytest

from app.utils.messaging import send_whatsapp_message


@patch("app.utils.messaging.whatsapp_from", "whatsapp:+14155238886")
@patch("app.utils.messaging.client.messages.create")
def test_send_whatsapp_message(mock_create):
    to = "whatsapp:+521234567890"
    message = "Hola desde la prueba unitaria"

    send_whatsapp_message(to, message)

    mock_create.assert_called_once_with(
        from_="whatsapp:+14155238886", to="whatsapp:+521234567890", body=message
    )
