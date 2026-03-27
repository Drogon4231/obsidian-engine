"""
Tests for core/compliance_checker.py — monetization compliance scanner.

Tests the run() pipeline, check_compliance(), suggest_alternatives(),
and apply_safe_alternatives() — all without making real API calls.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.compliance_checker import (
    run,
    check_compliance,
    suggest_alternatives,
    apply_safe_alternatives,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

CLEAN_SCRIPT = (
    "In 1969, humanity achieved a remarkable milestone when Apollo 11 "
    "landed on the Moon. Neil Armstrong took the first steps on the "
    "lunar surface, watched by millions on television."
)

YELLOW_RESPONSE = {
    "risk_level": "yellow",
    "flags": [
        {
            "category": "controversial_claims",
            "text_excerpt": "some governments allegedly covered up",
            "suggestion": "Add sourcing or soften language",
            "severity": "medium",
        }
    ],
    "overall_recommendation": "Minor issues — add disclaimers.",
}

RED_RESPONSE = {
    "risk_level": "red",
    "flags": [
        {
            "category": "graphic_violence",
            "text_excerpt": "blood pooled on the concrete floor",
            "suggestion": "Remove graphic detail, use implication",
            "severity": "high",
        },
        {
            "category": "child_endangerment",
            "text_excerpt": "the children were forced into",
            "suggestion": "Reframe without explicit detail",
            "severity": "high",
        },
    ],
    "overall_recommendation": "Major rewrites needed before production.",
}

GREEN_RESPONSE = {
    "risk_level": "green",
    "flags": [],
    "overall_recommendation": "No issues found. Safe to produce.",
}


# ── check_compliance() ──────────────────────────────────────────────────────

class TestCheckCompliance:
    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_green_script_returns_green(self, mock_agent):
        mock_agent.return_value = GREEN_RESPONSE
        result = check_compliance(CLEAN_SCRIPT, "Apollo 11")
        assert result["risk_level"] == "green"
        assert result["flags"] == []
        assert mock_agent.called

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_yellow_script_returns_flags(self, mock_agent):
        mock_agent.return_value = YELLOW_RESPONSE
        result = check_compliance("some governments allegedly covered up", "Conspiracy")
        assert result["risk_level"] == "yellow"
        assert len(result["flags"]) == 1
        flag = result["flags"][0]
        assert flag["category"] == "controversial_claims"
        assert flag["severity"] == "medium"
        assert "text_excerpt" in flag
        assert "suggestion" in flag

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_red_script_returns_multiple_flags(self, mock_agent):
        mock_agent.return_value = RED_RESPONSE
        result = check_compliance("graphic violent content here", "Dark History")
        assert result["risk_level"] == "red"
        assert len(result["flags"]) == 2
        categories = {f["category"] for f in result["flags"]}
        assert "graphic_violence" in categories
        assert "child_endangerment" in categories

    @pytest.mark.unit
    def test_empty_script_returns_green(self):
        result = check_compliance("", "Topic")
        assert result["risk_level"] == "green"
        assert result["flags"] == []
        assert "No script content" in result["overall_recommendation"]

    @pytest.mark.unit
    def test_whitespace_only_script_returns_green(self):
        result = check_compliance("   \n\t  ", "Topic")
        assert result["risk_level"] == "green"

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_defaults_missing_fields(self, mock_agent):
        """When API returns partial dict, defaults are filled in."""
        mock_agent.return_value = {"risk_level": "green"}
        result = check_compliance("some script", "Topic")
        assert "flags" in result
        assert "overall_recommendation" in result

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_non_dict_response_returns_yellow(self, mock_agent):
        """When API returns unexpected type, falls back to yellow."""
        mock_agent.return_value = "unexpected string"
        result = check_compliance("some script", "Topic")
        assert result["risk_level"] == "yellow"
        assert "Could not parse" in result["overall_recommendation"]

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_api_exception_returns_yellow(self, mock_agent):
        """When API raises, returns yellow with error message."""
        mock_agent.side_effect = RuntimeError("API down")
        result = check_compliance("some script", "Topic")
        assert result["risk_level"] == "yellow"
        assert "API down" in result["overall_recommendation"]

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_call_agent_receives_correct_params(self, mock_agent):
        mock_agent.return_value = GREEN_RESPONSE
        check_compliance("test script", "MKUltra")
        args, kwargs = mock_agent.call_args
        assert args[0] == "compliance_checker"
        assert "MKUltra" in kwargs["user_prompt"]
        assert "test script" in kwargs["user_prompt"]
        assert kwargs["max_tokens"] == 4000


# ── suggest_alternatives() ───────────────────────────────────────────────────

class TestSuggestAlternatives:
    @pytest.mark.unit
    def test_empty_flags_returns_empty(self):
        result = suggest_alternatives([])
        assert result == []

    @pytest.mark.unit
    def test_low_severity_flags_skipped(self):
        """Only medium/high severity flags are actionable."""
        flags = [
            {
                "category": "controversial_claims",
                "text_excerpt": "some text",
                "suggestion": "fix it",
                "severity": "low",
            }
        ]
        result = suggest_alternatives(flags)
        assert result == []

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_returns_alternatives_list(self, mock_agent):
        mock_agent.return_value = [
            {
                "original_text": "blood pooled on the floor",
                "alternative_text": "the aftermath was devastating",
                "category": "graphic_violence",
                "reasoning": "Removed graphic detail",
            }
        ]
        flags = [
            {
                "category": "graphic_violence",
                "text_excerpt": "blood pooled on the floor",
                "suggestion": "Remove graphic detail",
                "severity": "high",
            }
        ]
        result = suggest_alternatives(flags)
        assert len(result) == 1
        assert result[0]["alternative_text"] == "the aftermath was devastating"

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_handles_dict_with_alternatives_key(self, mock_agent):
        """API may return {alternatives: [...]} instead of bare list."""
        mock_agent.return_value = {
            "alternatives": [
                {
                    "original_text": "x",
                    "alternative_text": "y",
                    "category": "drug_content",
                    "reasoning": "softened",
                }
            ]
        }
        flags = [
            {
                "category": "drug_content",
                "text_excerpt": "x",
                "suggestion": "fix",
                "severity": "medium",
            }
        ]
        result = suggest_alternatives(flags)
        assert len(result) == 1

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_api_error_returns_empty(self, mock_agent):
        mock_agent.side_effect = RuntimeError("API error")
        flags = [
            {
                "category": "graphic_violence",
                "text_excerpt": "text",
                "suggestion": "fix",
                "severity": "high",
            }
        ]
        result = suggest_alternatives(flags)
        assert result == []

    @pytest.mark.unit
    def test_flags_without_text_excerpt_skipped(self):
        flags = [
            {
                "category": "graphic_violence",
                "suggestion": "fix",
                "severity": "high",
            }
        ]
        result = suggest_alternatives(flags)
        assert result == []


# ── apply_safe_alternatives() ────────────────────────────────────────────────

class TestApplySafeAlternatives:
    @pytest.mark.unit
    def test_empty_alternatives_returns_original(self):
        assert apply_safe_alternatives("original text", []) == "original text"

    @pytest.mark.unit
    def test_exact_match_replacement(self):
        script = "The blood pooled on the floor. The investigation continued."
        alts = [
            {
                "original_text": "The blood pooled on the floor.",
                "alternative_text": "The aftermath was devastating.",
            }
        ]
        result = apply_safe_alternatives(script, alts)
        assert "The aftermath was devastating." in result
        assert "blood pooled" not in result

    @pytest.mark.unit
    def test_multiple_replacements(self):
        script = "First bad part. Second bad part."
        alts = [
            {"original_text": "First bad part.", "alternative_text": "First safe part."},
            {"original_text": "Second bad part.", "alternative_text": "Second safe part."},
        ]
        result = apply_safe_alternatives(script, alts)
        assert "First safe part." in result
        assert "Second safe part." in result

    @pytest.mark.unit
    def test_skips_missing_original_or_replacement(self):
        script = "unchanged text"
        alts = [
            {"original_text": "", "alternative_text": "something"},
            {"original_text": "something", "alternative_text": ""},
        ]
        result = apply_safe_alternatives(script, alts)
        assert result == "unchanged text"

    @pytest.mark.unit
    def test_fuzzy_match_by_prefix(self):
        """Fuzzy matching by first 8 words when exact match fails."""
        script = "The experiment began in the cold dark chambers of Block Five. Next paragraph."
        alts = [
            {
                "original_text": "The experiment began in the cold dark chambers of Block Five and more text that differs",
                "alternative_text": "The conditions were harsh.",
            }
        ]
        result = apply_safe_alternatives(script, alts)
        # Fuzzy match should find the prefix and replace up to the period
        assert "The conditions were harsh." in result


# ── run() full pipeline ──────────────────────────────────────────────────────

class TestRun:
    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_green_result_no_alternatives(self, mock_agent):
        mock_agent.return_value = GREEN_RESPONSE
        result = run({"full_script": CLEAN_SCRIPT}, "Apollo 11")
        assert result["risk_level"] == "green"
        assert result["flags"] == []
        assert result["alternatives"] == []
        assert result["safe_script"] == CLEAN_SCRIPT
        assert result["topic"] == "Apollo 11"
        assert result["script_length"] == len(CLEAN_SCRIPT)

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_red_result_generates_alternatives_and_safe_script(self, mock_agent):
        original_text = "blood pooled on the concrete floor"
        script = f"The {original_text}. The investigation continued."
        alt_response = [
            {
                "original_text": original_text,
                "alternative_text": "aftermath was devastating",
                "category": "graphic_violence",
                "reasoning": "removed graphic detail",
            }
        ]
        # First call: compliance check returns red
        # Second call: alternatives generation
        mock_agent.side_effect = [RED_RESPONSE, alt_response]

        result = run({"full_script": script}, "Dark History")
        assert result["risk_level"] == "red"
        assert len(result["flags"]) == 2
        assert len(result["alternatives"]) == 1
        # safe_script should have the replacement applied
        assert "aftermath was devastating" in result["safe_script"]

    @pytest.mark.unit
    def test_empty_script_data(self):
        result = run({"full_script": ""}, "Topic")
        assert result["risk_level"] == "green"
        assert result["safe_script"] == ""

    @pytest.mark.unit
    def test_none_script_data(self):
        result = run({}, "Topic")
        assert result["risk_level"] == "green"

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_string_input_accepted(self, mock_agent):
        mock_agent.return_value = GREEN_RESPONSE
        result = run("plain string script", "Topic")
        assert result["risk_level"] == "green"
        assert result["script_length"] == len("plain string script")

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_yellow_with_no_actionable_flags(self, mock_agent):
        """Yellow flags with low severity produce no alternatives."""
        low_severity_response = {
            "risk_level": "yellow",
            "flags": [
                {
                    "category": "controversial_claims",
                    "text_excerpt": "allegedly",
                    "suggestion": "add sourcing",
                    "severity": "low",
                }
            ],
            "overall_recommendation": "Minor issues.",
        }
        mock_agent.return_value = low_severity_response
        result = run({"full_script": "script with allegedly"}, "Topic")
        assert result["risk_level"] == "yellow"
        assert len(result["flags"]) == 1
        assert result["alternatives"] == []
        assert result["safe_script"] == "script with allegedly"

    @pytest.mark.unit
    @patch("core.compliance_checker.call_agent")
    def test_flag_structure_is_correct(self, mock_agent):
        """Verify flags have the expected keys."""
        mock_agent.return_value = YELLOW_RESPONSE
        result = run({"full_script": "test script"}, "Topic")
        for flag in result["flags"]:
            assert "category" in flag
            assert "severity" in flag
            assert "text_excerpt" in flag
            assert "suggestion" in flag
