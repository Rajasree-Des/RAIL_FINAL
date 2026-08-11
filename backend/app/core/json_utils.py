"""JSON field serialization helpers."""

import json
from typing import Any


def serialize_json(value: Any) -> str:
    return json.dumps(value)


def deserialize_json(raw: str | None, default: Any = None) -> Any:
    if raw is None:
        return default
    return json.loads(raw)
