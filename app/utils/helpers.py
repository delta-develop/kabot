def parse_bool(value: str) -> bool:
    """Parse a string into a boolean value.

    Accepts variations such as "sí", "si", "yes", "true", "1" for True,
    and "no", "false", "0", "" for False. Case-insensitive.

    Args:
        value (str): The string to convert.

    Returns:
        bool: Parsed boolean value.
    """
    true_values = {"sí", "si", "yes", "true", "1"}
    false_values = {"no", "false", "0", ""}

    normalized = value.strip().lower()
    if normalized in true_values:
        return True
    if normalized in false_values:
        return False
    return False


def parse_float(value: str, default: float = 0.0) -> float:
    """Convert a string to a float, with fallback.

    Args:
        value (str): The string to convert.
        default (float, optional): Value to return if conversion fails. Defaults to 0.0.

    Returns:
        float: The parsed float or default value.
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
