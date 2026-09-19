

import pytest
from app.utils.sanitization import sanitize_message

def test_sanitize_message_returns_same_string():
    input_text = "Hello, world!"
    assert sanitize_message(input_text) == input_text

def test_sanitize_message_empty_string():
    input_text = ""
    assert sanitize_message(input_text) == ""

def test_sanitize_message_with_html():
    input_text = "<b>bold</b>"
    assert sanitize_message(input_text) == input_text

def test_sanitize_message_with_script():
    input_text = "<script>alert('xss');</script>"
    assert sanitize_message(input_text) == input_text