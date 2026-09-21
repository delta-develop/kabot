import pytest

from app.utils import token_utils
from app.utils.token_utils import DEFAULT_ENCODING, count_tokens


@pytest.fixture(autouse=True)
def reset_encoding():
    token_utils._encoding = None
    yield
    token_utils._encoding = None


def test_encoding_follows_the_configured_model(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    assert token_utils.get_encoding().name == "o200k_base"


def test_unmapped_model_falls_back_loudly(monkeypatch, mocker):
    monkeypatch.setenv("OPENAI_MODEL", "some-other-provider/model")
    warn = mocker.patch("app.utils.token_utils.logfire.warn")

    assert token_utils.get_encoding().name == DEFAULT_ENCODING
    warn.assert_called_once()


def test_missing_model_counts_with_the_default_model(monkeypatch, mocker):
    """No warning here: an unset model still resolves to one we actually call."""
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    warn = mocker.patch("app.utils.token_utils.logfire.warn")

    assert token_utils.get_encoding().name == DEFAULT_ENCODING
    warn.assert_not_called()


@pytest.mark.parametrize(
    "model", ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5-mini", "gpt-4.1", "gpt-4o"]
)
def test_the_supported_model_line_maps_without_falling_back(model, monkeypatch, mocker):
    monkeypatch.setenv("OPENAI_MODEL", model)
    warn = mocker.patch("app.utils.token_utils.logfire.warn")

    assert token_utils.get_encoding().name == "o200k_base"
    warn.assert_not_called()


def test_encoding_is_resolved_once(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    assert token_utils.get_encoding() is token_utils.get_encoding()


def test_counts_add_up_across_newline_terminated_pieces():
    pieces = [
        "<fact_memory>{}</fact_memory>\n",
        "<summary_memory>un resumen</summary_memory>\n",
        '<fragment ts="2026-03-04">\n<user>hola</user><assistant>qué tal</assistant>\n</fragment>\n',
        "<working_memory>\n<user>y eso?</user><assistant>la mudanza</assistant>\n</working_memory>\n",
    ]

    assert sum(count_tokens(piece) for piece in pieces) == count_tokens("".join(pieces))


def test_counts_do_not_add_up_without_the_trailing_newline():
    """The newline is what makes the budget exact, not a formatting choice.

    Without it the tokenizer merges across the block boundary and the per-block
    counts stop summing to the rendered total, which is exactly how `used` would
    start lying about the ceiling.
    """
    first, second = "<summary_memory>hola</summary_memory>", "<working_memory>x"

    assert count_tokens(first) + count_tokens(second) != count_tokens(first + second)
