"""Tests for core/json_compat.py — lenient JSON parsing monkey-patch."""
import json
import pytest

from core.json_compat import apply_lenient_json, _original_json_loads, _original_json_load


@pytest.mark.unit
class TestApplyLenientJson:
    """Verify that apply_lenient_json patches json.loads/json.load."""

    def test_patched_loads_accepts_control_chars(self):
        """Control characters inside strings should parse without error."""
        apply_lenient_json()
        raw = '{"key": "value with \\n newline and \t tab"}'
        result = json.loads(raw)
        assert result["key"].startswith("value with")

    def test_patched_loads_still_parses_normal_json(self):
        apply_lenient_json()
        assert json.loads('{"a": 1}') == {"a": 1}

    def test_patched_loads_handles_arrays(self):
        apply_lenient_json()
        assert json.loads('[1, 2, 3]') == [1, 2, 3]

    def test_patched_load_reads_file(self, tmp_path):
        """json.load should also use strict=False after patching."""
        apply_lenient_json()
        f = tmp_path / "test.json"
        f.write_text('{"msg": "hello"}')
        with open(f) as fp:
            result = json.load(fp)
        assert result == {"msg": "hello"}

    def test_idempotent_apply(self):
        """Calling apply_lenient_json multiple times should not stack patches."""
        apply_lenient_json()
        apply_lenient_json()
        assert json.loads('{"a": 1}') == {"a": 1}

    def test_originals_preserved(self):
        """The original functions should be preserved for reference."""
        assert callable(_original_json_loads)
        assert callable(_original_json_load)
