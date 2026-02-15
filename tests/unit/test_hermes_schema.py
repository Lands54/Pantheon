from __future__ import annotations

import pytest

from gods.hermes.errors import HermesError, HERMES_SCHEMA_INVALID
from gods.hermes.schema import validate_schema


def test_hermes_schema_validate_success():
    schema = {
        "type": "object",
        "required": ["x"],
        "properties": {"x": {"type": "string"}},
    }
    validate_schema({"x": "ok"}, schema)


def test_hermes_schema_validate_fail_required():
    schema = {
        "type": "object",
        "required": ["x"],
        "properties": {"x": {"type": "string"}},
    }
    with pytest.raises(HermesError) as ei:
        validate_schema({}, schema)
    assert ei.value.code == HERMES_SCHEMA_INVALID
