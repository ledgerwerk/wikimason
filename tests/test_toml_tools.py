from __future__ import annotations

import pytest

from wikimason.config import _toml_value as config_toml_value
from wikimason.errors import UsageError
from wikimason.toml_tools import toml_bool, toml_string, toml_string_array, toml_value


def test_toml_string_escapes_backslashes_and_quotes() -> None:
    assert toml_string('path\\name "quote"') == '"path\\\\name \\"quote\\""'


def test_toml_string_array_supports_empty_and_values() -> None:
    assert toml_string_array([]) == "[]"
    assert toml_string_array(["alpha", "beta"]) == '["alpha", "beta"]'


def test_toml_bool_serialization() -> None:
    assert toml_bool(True) == "true"
    assert toml_bool(False) == "false"


def test_toml_value_supports_core_types() -> None:
    assert toml_value("demo") == '"demo"'
    assert toml_value(True) == "true"
    assert toml_value(["a", "b"]) == '["a", "b"]'
    assert toml_value(("x",)) == '["x"]'


def test_toml_value_rejects_unsupported_values() -> None:
    with pytest.raises(ValueError, match="unsupported TOML value"):
        toml_value(123)


def test_config_toml_value_raises_usage_error_for_unsupported_values() -> None:
    with pytest.raises(UsageError, match="unsupported TOML value"):
        config_toml_value(123)
