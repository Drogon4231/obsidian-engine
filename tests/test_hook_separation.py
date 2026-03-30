"""Tests for extract_acts() in agents/04_script_writer.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_extract_acts():
    """Load extract_acts without triggering side effects from module-level code."""
    from unittest.mock import MagicMock, patch

    # The module imports intel.dna_loader and core.agent_wrapper at top level.
    # Patch them so we can import the function without API dependencies.
    mock_dna = MagicMock()
    mock_dna.get_dna = MagicMock(return_value="")
    mock_dna.get_agent_guidance = MagicMock(return_value="")

    saved_modules = {}
    for mod_name in ("intel.dna_loader", "core.agent_wrapper"):
        saved_modules[mod_name] = sys.modules.get(mod_name)

    sys.modules["intel.dna_loader"] = mock_dna
    sys.modules["core.agent_wrapper"] = MagicMock()

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_script_writer_04",
            str(Path(__file__).parent.parent / "agents" / "04_script_writer.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.extract_acts
    finally:
        # Restore original modules
        for mod_name, original in saved_modules.items():
            if original is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = original


extract_acts = _load_extract_acts()


class TestExtractActs:
    @pytest.mark.unit
    def test_cold_open_is_3_percent(self):
        """Cold open should be ~3% of words (0% to 3%)."""
        words = ["word"] * 1000
        text = " ".join(words)
        acts = extract_acts(text)
        cold_open_words = len(acts["cold_open"].split())
        # 3% of 1000 = 30 words (int(1000 * 0.03) - int(1000 * 0.00) = 30)
        assert cold_open_words == 30

    @pytest.mark.unit
    def test_hook_is_4_percent(self):
        """Hook should be ~4% of words (3% to 7%)."""
        words = ["word"] * 1000
        text = " ".join(words)
        acts = extract_acts(text)
        hook_words = len(acts["hook"].split())
        # 7% - 3% = 4% of 1000 = 40 words
        assert hook_words == 40

    @pytest.mark.unit
    def test_act_structure_percentages_1000_words(self):
        """Verify act structure percentages with a 1000-word script."""
        words = ["word"] * 1000
        text = " ".join(words)
        acts = extract_acts(text)

        cold_open_len = len(acts["cold_open"].split())
        hook_len = len(acts["hook"].split())
        act1_len = len(acts["act1"].split())
        act2_len = len(acts["act2"].split())
        act3_len = len(acts["act3"].split())
        ending_len = len(acts["ending"].split())

        # cold_open: 0-3% = 30 words
        assert cold_open_len == int(1000 * 0.03) - int(1000 * 0.00)
        # hook: 3-7% = 40 words
        assert hook_len == int(1000 * 0.07) - int(1000 * 0.03)
        # act1: 7-28% = 210 words
        assert act1_len == int(1000 * 0.28) - int(1000 * 0.07)
        # act2: 28-67% = 390 words
        assert act2_len == int(1000 * 0.67) - int(1000 * 0.28)
        # act3: 67-90% = 230 words
        assert act3_len == int(1000 * 0.90) - int(1000 * 0.67)
        # ending: 90-100% = 100 words
        assert ending_len == int(1000 * 1.00) - int(1000 * 0.90)

    @pytest.mark.unit
    def test_all_acts_present(self):
        """extract_acts should return all 6 keys."""
        text = " ".join(["word"] * 100)
        acts = extract_acts(text)
        expected_keys = {"cold_open", "hook", "act1", "act2", "act3", "ending"}
        assert set(acts.keys()) == expected_keys

    @pytest.mark.unit
    def test_very_short_script(self):
        """Should handle a very short script (10 words) without crashing."""
        text = " ".join(["word"] * 10)
        acts = extract_acts(text)
        # All keys should exist
        assert "cold_open" in acts
        assert "hook" in acts
        assert "act1" in acts
        assert "act2" in acts
        assert "act3" in acts
        assert "ending" in acts
        # Total words across acts should not exceed original
        total = sum(len(v.split()) for v in acts.values() if v)
        assert total <= 10

    @pytest.mark.unit
    def test_no_words_lost(self):
        """All words from the original should appear in one of the acts."""
        words = [f"w{i}" for i in range(1000)]
        text = " ".join(words)
        acts = extract_acts(text)
        reconstructed = []
        for key in ["cold_open", "hook", "act1", "act2", "act3", "ending"]:
            if acts[key]:
                reconstructed.extend(acts[key].split())
        assert len(reconstructed) == 1000
