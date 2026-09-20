from decimal import Decimal

import pytest
from sqlalchemy.dialects import postgresql

from app.services.search.filters import FILTER_SCHEMAS, filters_to_sql


def test_restaurant_supplies_filter_schema_is_closed():
    schema = FILTER_SCHEMAS["restaurant-supplies"]

    assert set(schema) == {"store", "brand", "unit", "pack_size", "price"}
    assert schema["store"].value_type is str
    assert schema["brand"].value_type is str
    assert schema["unit"].value_type is str
    assert schema["pack_size"].value_type is Decimal
    assert schema["price"].value_type is Decimal
    assert schema["store"].operators == frozenset({"in"})
    assert schema["price"].operators == frozenset({"lte", "gte", "lt", "gt", "in"})


@pytest.mark.parametrize(
    ("filters", "expected_values"),
    [
        ({"store": "abarrotes"}, ["abarrotes"]),
        ({"price": {"lte": 400}}, [Decimal("400")]),
        ({"price": {"gte": "10.5"}}, [Decimal("10.5")]),
        ({"price": {"lt": 400}}, [Decimal("400")]),
        ({"price": {"gt": 10}}, [Decimal("10")]),
        ({"brand": {"in": ["X", "Y"]}}, ["X", "Y"]),
    ],
)
def test_filters_are_parameterized_and_coerced(filters, expected_values):
    expression = filters_to_sql("restaurant-supplies", filters)
    compiled = expression.compile(dialect=postgresql.dialect())

    bound_values = list(compiled.params.values())
    for expected in expected_values:
        assert expected in bound_values or any(
            isinstance(value, list) and expected in value for value in bound_values
        )


def test_top_level_filters_are_combined_with_and():
    expression = filters_to_sql(
        "restaurant-supplies",
        {"store": "abarrotes", "price": {"lte": 400}},
    )

    assert " AND " in str(expression.compile(dialect=postgresql.dialect()))


def test_single_quote_stays_in_a_bound_parameter():
    expression = filters_to_sql("restaurant-supplies", {"brand": "Chef's Choice"})
    compiled = expression.compile(dialect=postgresql.dialect())

    assert "Chef's Choice" not in str(compiled)
    assert "Chef's Choice" in compiled.params.values()


@pytest.mark.parametrize(
    ("namespace", "filters", "message"),
    [
        (
            "unknown",
            {},
            "Unknown namespace 'unknown'. Allowed namespaces: restaurant-supplies",
        ),
        (
            "restaurant-supplies",
            {"unknown": "x"},
            "Unknown filter field 'unknown'. Allowed fields: brand, pack_size, price, store, unit",
        ),
        (
            "restaurant-supplies",
            {"price": {"between": 1}},
            "Unknown operator 'between' for field 'price'. Allowed operators: gt, gte, in, lt, lte",
        ),
        (
            "restaurant-supplies",
            {"store": {"lte": "x"}},
            "Unknown operator 'lte' for field 'store'. Allowed operators: in",
        ),
        (
            "restaurant-supplies",
            {"price": {"lte": 1, "gte": 0}},
            "Filter object for field 'price' must contain exactly one operator",
        ),
        (
            "restaurant-supplies",
            {"brand": {"in": []}},
            "Operator 'in' for field 'brand' requires a non-empty list",
        ),
        (
            "restaurant-supplies",
            {"brand": {"in": [{"nested": "value"}]}},
            "Operator 'in' for field 'brand' requires scalar elements",
        ),
        (
            "restaurant-supplies",
            {"price": {"in": [[10]]}},
            "Operator 'in' for field 'price' requires scalar elements",
        ),
        (
            "restaurant-supplies",
            {"price": True},
            "Invalid value for field 'price': expected numeric",
        ),
        (
            "restaurant-supplies",
            {"price": "not-a-number"},
            "Invalid value for field 'price': expected numeric",
        ),
    ],
)
def test_invalid_filters_are_rejected_explicitly(namespace, filters, message):
    with pytest.raises(ValueError, match="^" + message.replace("'", "\\'") + "$"):
        filters_to_sql(namespace, filters)
