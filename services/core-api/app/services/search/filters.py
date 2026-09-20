from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import Numeric, String, and_, cast, true

from app.models.catalog_item import CatalogItem


@dataclass(frozen=True)
class FilterField:
    expression: Any
    value_type: type[str] | type[Decimal]
    operators: frozenset[str]


FILTER_SCHEMAS = {
    "restaurant-supplies": {
        "store": FilterField(
            cast(CatalogItem.attributes["store"].astext, String),
            str,
            frozenset({"in"}),
        ),
        "brand": FilterField(
            cast(CatalogItem.attributes["brand"].astext, String),
            str,
            frozenset({"in"}),
        ),
        "unit": FilterField(
            cast(CatalogItem.attributes["unit"].astext, String),
            str,
            frozenset({"in"}),
        ),
        "pack_size": FilterField(
            cast(CatalogItem.attributes["pack_size"].astext, Numeric),
            Decimal,
            frozenset({"lte", "gte", "lt", "gt", "in"}),
        ),
        "price": FilterField(
            cast(CatalogItem.attributes["price"].astext, Numeric),
            Decimal,
            frozenset({"lte", "gte", "lt", "gt", "in"}),
        ),
    }
}


def _coerce(field_name: str, field: FilterField, value: Any) -> str | Decimal:
    if field.value_type is str:
        return str(value)
    if isinstance(value, bool):
        raise ValueError(f"Invalid value for field '{field_name}': expected numeric")
    try:
        return Decimal(str(value))
    except InvalidOperation, ValueError:
        raise ValueError(
            f"Invalid value for field '{field_name}': expected numeric"
        ) from None


def filters_to_sql(namespace: str, filters: dict[str, Any]):
    if namespace not in FILTER_SCHEMAS:
        allowed = ", ".join(sorted(FILTER_SCHEMAS))
        raise ValueError(
            f"Unknown namespace '{namespace}'. Allowed namespaces: {allowed}"
        )

    schema = FILTER_SCHEMAS[namespace]
    conditions = []
    for field_name, value in filters.items():
        if field_name not in schema:
            allowed = ", ".join(sorted(schema))
            raise ValueError(
                f"Unknown filter field '{field_name}'. Allowed fields: {allowed}"
            )

        field = schema[field_name]
        if not isinstance(value, dict):
            if isinstance(value, list):
                raise ValueError(
                    f"Invalid value for field '{field_name}': expected scalar"
                )
            conditions.append(field.expression == _coerce(field_name, field, value))
            continue

        if len(value) != 1:
            raise ValueError(
                f"Filter object for field '{field_name}' must contain exactly one operator"
            )
        operator, operand = next(iter(value.items()))
        if operator not in field.operators:
            allowed = ", ".join(sorted(field.operators))
            raise ValueError(
                f"Unknown operator '{operator}' for field '{field_name}'. "
                f"Allowed operators: {allowed}"
            )

        if operator == "in":
            if not isinstance(operand, list) or not operand:
                raise ValueError(
                    f"Operator 'in' for field '{field_name}' requires a non-empty list"
                )
            if any(isinstance(item, (dict, list)) for item in operand):
                raise ValueError(
                    f"Operator 'in' for field '{field_name}' requires scalar elements"
                )
            conditions.append(
                field.expression.in_(
                    [_coerce(field_name, field, item) for item in operand]
                )
            )
        else:
            coerced = _coerce(field_name, field, operand)
            conditions.append(
                {
                    "lte": field.expression <= coerced,
                    "gte": field.expression >= coerced,
                    "lt": field.expression < coerced,
                    "gt": field.expression > coerced,
                }[operator]
            )

    return and_(*conditions) if conditions else true()
