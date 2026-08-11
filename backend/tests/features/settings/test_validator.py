"""Tests for settings value validation."""

import pytest

from app.core.exceptions import ValidationError
from app.features.settings.validator import validate_setting_value


def test_validate_string():
    assert validate_setting_value("string", "hello") == "hello"


def test_validate_number_range():
    assert validate_setting_value("number", 50, {"min": 1, "max": 100}) == 50
    with pytest.raises(ValidationError):
        validate_setting_value("number", 200, {"min": 1, "max": 100})


def test_validate_enum():
    options = [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}]
    assert validate_setting_value("enum", "a", options=options) == "a"
    with pytest.raises(ValidationError):
        validate_setting_value("enum", "c", options=options)


def test_validate_multiselect():
    options = [{"label": "X", "value": "x"}, {"label": "Y", "value": "y"}]
    assert validate_setting_value("multiselect", ["x"], options=options) == ["x"]


def test_validate_json_object():
    value = {"a": 1}
    assert validate_setting_value("json", value) == value
