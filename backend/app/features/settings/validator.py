"""Validate setting values against definition metadata."""

import json
import re
from typing import Any

from app.core.exceptions import ValidationError


def parse_json_field(raw: str | None) -> dict | list | None:
    if not raw:
        return None
    return json.loads(raw)


def validate_setting_value(
    value_type: str,
    value: Any,
    validation: dict | None = None,
    options: list[dict] | None = None,
) -> Any:
    """Validate and normalize a setting value. Raises ValidationError on failure."""
    validation = validation or {}

    if value_type == "string":
        if not isinstance(value, str):
            raise ValidationError("Expected string value")
        if validation.get("required") and not value.strip():
            raise ValidationError("Value is required")
        min_len = validation.get("min_length")
        max_len = validation.get("max_length")
        if min_len is not None and len(value) < min_len:
            raise ValidationError(f"Minimum length is {min_len}")
        if max_len is not None and len(value) > max_len:
            raise ValidationError(f"Maximum length is {max_len}")
        pattern = validation.get("pattern")
        if pattern and not re.match(pattern, value):
            raise ValidationError("Value does not match required pattern")
        return value

    if value_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError("Expected numeric value")
        num = float(value)
        if num != int(num) and validation.get("integer_only"):
            raise ValidationError("Expected integer value")
        if "min" in validation and num < validation["min"]:
            raise ValidationError(f"Minimum value is {validation['min']}")
        if "max" in validation and num > validation["max"]:
            raise ValidationError(f"Maximum value is {validation['max']}")
        return int(num) if num == int(num) else num

    if value_type == "boolean":
        if not isinstance(value, bool):
            raise ValidationError("Expected boolean value")
        return value

    if value_type == "enum":
        if options is None:
            raise ValidationError("Enum options not configured")
        allowed = {opt["value"] for opt in options}
        if value not in allowed:
            raise ValidationError(f"Value must be one of: {', '.join(str(v) for v in allowed)}")
        return value

    if value_type == "multiselect":
        if not isinstance(value, list):
            raise ValidationError("Expected list value")
        if options is not None:
            allowed = {opt["value"] for opt in options}
            for item in value:
                if item not in allowed:
                    raise ValidationError(f"Invalid option: {item}")
        min_items = validation.get("min_items", 0)
        max_items = validation.get("max_items")
        if len(value) < min_items:
            raise ValidationError(f"Select at least {min_items} item(s)")
        if max_items is not None and len(value) > max_items:
            raise ValidationError(f"Select at most {max_items} item(s)")
        return value

    if value_type == "json":
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as e:
                raise ValidationError("Invalid JSON") from e
        if not isinstance(value, (dict, list)):
            raise ValidationError("Expected JSON object or array")
        return value

    raise ValidationError(f"Unsupported value type: {value_type}")
