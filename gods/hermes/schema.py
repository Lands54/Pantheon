"""Minimal JSON-schema-like validator for Hermes."""
from __future__ import annotations

from typing import Any

from gods.hermes.errors import HermesError, HERMES_SCHEMA_INVALID


_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _check_type(value: Any, expected: str) -> bool:
    typ = _TYPE_MAP.get(expected)
    if typ is None:
        return True
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, typ)


def validate_schema(payload: Any, schema: dict, prefix: str = "$"):
    if not isinstance(schema, dict):
        return

    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _check_type(payload, expected_type):
        raise HermesError(
            code=HERMES_SCHEMA_INVALID,
            message=f"Schema type mismatch at {prefix}: expected {expected_type}",
            retryable=False,
            details={"path": prefix, "expected": expected_type, "actual": type(payload).__name__},
        )

    if expected_type == "object" and isinstance(payload, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in payload:
                raise HermesError(
                    code=HERMES_SCHEMA_INVALID,
                    message=f"Missing required key at {prefix}: {key}",
                    retryable=False,
                    details={"path": prefix, "missing": key},
                )

        properties = schema.get("properties", {})
        for key, sub_schema in properties.items():
            if key in payload:
                validate_schema(payload[key], sub_schema, f"{prefix}.{key}")

    if expected_type == "array" and isinstance(payload, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(payload):
                validate_schema(item, item_schema, f"{prefix}[{idx}]")
