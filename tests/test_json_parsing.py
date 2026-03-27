"""Tests for robust JSON parsing in claude_client.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clients.claude_client import (
    _parse_json_robust,
    _try_parse,
    _extract_first_json,
    _repair_truncated_json,
)


class TestTryParse:
    def test_valid_dict(self):
        assert _try_parse('{"a": 1}') == {"a": 1}

    def test_valid_list(self):
        assert _try_parse('[1, 2]') == [1, 2]

    def test_primitive_wrapped(self):
        assert _try_parse('"hello"') == {"raw": "hello"}

    def test_invalid_returns_none(self):
        assert _try_parse("not json") is None


class TestExtractFirstJson:
    def test_json_with_trailing_text(self):
        text = '{"key": "value"}\n\nHere is some explanation text.'
        assert _extract_first_json(text) == {"key": "value"}

    def test_json_with_trailing_json(self):
        text = '{"first": 1}{"second": 2}'
        assert _extract_first_json(text) == {"first": 1}

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2]}} extra'
        assert _extract_first_json(text) == {"outer": {"inner": [1, 2]}}

    def test_array_with_trailing(self):
        text = '[{"a": 1}, {"b": 2}]\nsome notes'
        assert _extract_first_json(text) == [{"a": 1}, {"b": 2}]

    def test_no_json(self):
        assert _extract_first_json("no json here") is None

    def test_strings_with_braces(self):
        text = '{"msg": "use {var} here"} trailing'
        assert _extract_first_json(text) == {"msg": "use {var} here"}


class TestRepairTruncatedJson:
    def test_truncated_object(self):
        text = '{"key": "value", "key2": "val'
        result = _repair_truncated_json(text)
        assert result is not None
        assert result["key"] == "value"

    def test_truncated_array(self):
        text = '[{"a": 1}, {"b": 2}, {"c":'
        result = _repair_truncated_json(text)
        assert result is not None
        assert len(result) == 2
        assert result[0]["a"] == 1

    def test_truncated_nested(self):
        text = '{"scenes": [{"id": 1}, {"id": 2}, {"id":'
        result = _repair_truncated_json(text)
        assert result is not None
        assert len(result["scenes"]) == 2

    def test_complete_json_returns_none(self):
        """Complete JSON doesn't need repair."""
        assert _repair_truncated_json('{"a": 1}') is None

    def test_no_json(self):
        assert _repair_truncated_json("not json") is None


class TestParseJsonRobust:
    def test_clean_json(self):
        assert _parse_json_robust('{"a": 1}') == {"a": 1}

    def test_markdown_fences(self):
        assert _parse_json_robust('```json\n{"a": 1}\n```') == {"a": 1}

    def test_trailing_text(self):
        result = _parse_json_robust('{"a": 1}\n\nThis is my explanation.')
        assert result == {"a": 1}

    def test_unicode_punctuation(self):
        result = _parse_json_robust('{"msg": "it\u2019s a \u201ctest\u201d"}')
        assert result is not None
        assert "test" in result["msg"]

    def test_truncated_recovery(self):
        text = '{"scores": {"hook": 8, "pacing": 7}, "feedback": "goo'
        result = _parse_json_robust(text)
        assert result is not None
        assert result["scores"]["hook"] == 8

    def test_empty_returns_none(self):
        assert _parse_json_robust("") is None
