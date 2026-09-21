import logfire
import tiktoken

from app.utils.openai_utils import get_chat_model

DEFAULT_ENCODING = "o200k_base"

_encoding: tiktoken.Encoding | None = None


def _build_encoding() -> tiktoken.Encoding:
    # tiktoken maps the whole gpt-4o/gpt-5 line to o200k_base, so this falls back
    # only for a model it has never heard of. It falls back loudly: the budget is
    # the product, and a silent tokenizer swap would make `used` lie.
    model = get_chat_model()
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        logfire.warn(
            "tiktoken does not map {model}; counting tokens with {encoding}",
            model=model,
            encoding=DEFAULT_ENCODING,
        )
    return tiktoken.get_encoding(DEFAULT_ENCODING)


def get_encoding() -> tiktoken.Encoding:
    """Return the tokenizer for the configured model, resolved once."""
    global _encoding
    if _encoding is None:
        _encoding = _build_encoding()
    return _encoding


def count_tokens(text: str) -> int:
    """Count tokens exactly as the configured model would.

    Counts are additive across concatenation only when every piece ends with a
    newline, which is what keeps the context budget exact. See
    tests/utils/test_token_utils.py.
    """
    return len(get_encoding().encode(text))
