from typing import List, Generator, TypeVar

T = TypeVar("T")

def chunk_records(records: List[T], chunk_size: int = 100) -> Generator[List[T], None, None]:
    """
    Split a list of records into smaller chunks of a specified size.

    Args:
        records (List[T]): The list of records to chunk.
        chunk_size (int, optional): The maximum size of each chunk. Defaults to 100.

    Yields:
        Generator[List[T], None, None]: A generator yielding chunks of the original list.
    """
    for i in range(0, len(records), chunk_size):
        yield records[i:i + chunk_size]
        

def parse_bool(value: str) -> bool:
    """
    Convert a string representation of a boolean to a Python bool.

    Accepts variations like "sí", "si", "yes", "true", "1" as True, and
    "no", "false", "0" as False. Case-insensitive and ignores leading/trailing spaces.

    Args:
        value (str): The string to interpret as a boolean.

    Returns:
        bool: The boolean interpretation of the input.
    """
    true_values = {"sí", "si", "yes", "true", "1"}
    false_values = {"no", "false", "0",""}

    normalized = value.strip().lower()
    if normalized in true_values:
        return True
    if normalized in false_values:
        return False
    return False

def parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default