

import pytest
from app.utils.helpers import chunk_records, parse_bool, parse_float


def test_chunk_records_basic():
    data = list(range(10))
    chunks = list(chunk_records(data, chunk_size=3))
    assert chunks == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_parse_bool_true():
    true_inputs = ["sí", "si", "yes", "true", "1", "  Sí  ", "YeS"]
    for val in true_inputs:
        assert parse_bool(val) is True


def test_parse_bool_false():
    false_inputs = ["no", "false", "0", "", "   ", "maybe", "not sure"]
    for val in false_inputs:
        assert parse_bool(val) is False


def test_parse_float_valid():
    assert parse_float("3.14") == 3.14
    assert parse_float("0") == 0.0
    assert parse_float("100") == 100.0


def test_parse_float_invalid():
    assert parse_float("abc") == 0.0
    assert parse_float(None) == 0.0
    assert parse_float("", default=1.23) == 1.23