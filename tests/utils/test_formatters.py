

import pytest
from app.utils.formatters import to_openai_format

def test_to_openai_format_valid_messages():
    input_messages = [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Hola, ¿cómo estás?"}
    ]
    expected = [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Hola, ¿cómo estás?"}
    ]
    assert to_openai_format(input_messages) == expected

def test_to_openai_format_skips_invalid_entries():
    input_messages = [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": None},  # inválido
        {"role": None, "content": "Mensaje sin rol"},  # inválido
        {"role": "system", "content": "Bienvenido"}  # válido
    ]
    expected = [
        {"role": "user", "content": "Hola"},
        {"role": "system", "content": "Bienvenido"}
    ]
    assert to_openai_format(input_messages) == expected