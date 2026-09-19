

import pytest
from app.utils.message_adapter import (
    format_conversation,
    message_from_user_input,
    message_from_llm_output,
)

def test_format_conversation_filters_and_strips():
    raw_messages = [
        {"role": "user", "content": " Hola "},
        {"role": "assistant", "content": " Qué tal "},
        {"role": "system", "content": " Contexto "},
        {"role": "ignored", "content": " No debería aparecer "},
        {"role": "user", "content": ""},
        {"role": "assistant", "content": None},
    ]
    expected = [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Qué tal"},
        {"role": "system", "content": "Contexto"},
    ]
    assert format_conversation(raw_messages) == expected

def test_message_from_user_input_strips_text():
    text = "   ¿Tienen camionetas disponibles?   "
    expected = {"role": "user", "content": "¿Tienen camionetas disponibles?"}
    assert message_from_user_input(text) == expected

def test_message_from_llm_output_strips_text():
    text = "   Sí, tenemos camionetas de varias marcas.   "
    expected = {"role": "assistant", "content": "Sí, tenemos camionetas de varias marcas."}
    assert message_from_llm_output(text) == expected