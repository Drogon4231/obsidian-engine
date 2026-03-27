"""Tests for core/config.py — YAML configuration loader."""

import sys
import tempfile
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import ObsidianConfig, _deep_merge


class TestDeepMerge:
    def test_flat_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        assert _deep_merge(base, override) == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3}}
        assert _deep_merge(base, override) == {"x": {"a": 1, "b": 3}}

    def test_override_replaces_non_dict_with_dict(self):
        base = {"x": 1}
        override = {"x": {"nested": True}}
        assert _deep_merge(base, override) == {"x": {"nested": True}}

    def test_empty_override(self):
        base = {"a": 1}
        assert _deep_merge(base, {}) == {"a": 1}

    def test_empty_base(self):
        override = {"a": 1}
        assert _deep_merge({}, override) == {"a": 1}


class TestObsidianConfig:
    def test_loads_defaults_without_yaml(self):
        """Config works even if no YAML file exists."""
        cfg = ObsidianConfig(config_path=Path("/nonexistent/obsidian.yaml"))
        assert cfg.voice.narrator_id == "JBFqnCBsd6RMkjVDRZzb"
        assert cfg.models.premium == "claude-opus-4-6"
        assert cfg.script.min_words == 1000
        assert cfg.video.fps == 30
        assert cfg.audio.chunk_max_chars == 500
        assert cfg.quality.min_research_facts == 5
        assert cfg.cost.budget_max_usd == 0.0
        assert cfg.api.max_retries == 5
        assert cfg.server.port == 8080

    def test_yaml_overrides_defaults(self):
        """Values in YAML override defaults."""
        yaml_content = {
            "voice": {"narrator_id": "custom-voice-123"},
            "script": {"min_words": 2000},
            "video": {"fps": 60},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            f.flush()
            cfg = ObsidianConfig(config_path=Path(f.name))

        assert cfg.voice.narrator_id == "custom-voice-123"
        assert cfg.script.min_words == 2000
        assert cfg.video.fps == 60
        # Non-overridden values keep defaults
        assert cfg.voice.speed_body == 0.76
        assert cfg.models.premium == "claude-opus-4-6"

    def test_partial_nested_override(self):
        """Partial override of nested section preserves unset keys."""
        yaml_content = {
            "voice": {
                "body": {"stability": 0.99},
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            f.flush()
            cfg = ObsidianConfig(config_path=Path(f.name))

        assert cfg.voice.body.stability == 0.99
        # Other body keys preserved
        assert cfg.voice.body.similarity_boost == 0.82
        assert cfg.voice.body.style == 0.60

    def test_dot_access_nested(self):
        cfg = ObsidianConfig(config_path=Path("/nonexistent.yaml"))
        assert cfg.voice.hook.stability == 0.28
        assert cfg.schedule.topic_discovery.day == "monday"

    def test_get_with_default(self):
        cfg = ObsidianConfig(config_path=Path("/nonexistent.yaml"))
        assert cfg.get("nonexistent_key", "fallback") == "fallback"
        assert cfg.get("voice") is not None

    def test_contains(self):
        cfg = ObsidianConfig(config_path=Path("/nonexistent.yaml"))
        assert "voice" in cfg
        assert "nonexistent" not in cfg

    def test_to_dict(self):
        cfg = ObsidianConfig(config_path=Path("/nonexistent.yaml"))
        d = cfg.voice.body.to_dict()
        assert isinstance(d, dict)
        assert d["stability"] == 0.38

    def test_attribute_error_on_missing_key(self):
        cfg = ObsidianConfig(config_path=Path("/nonexistent.yaml"))
        with pytest.raises(AttributeError, match="no key"):
            _ = cfg.nonexistent_section

    def test_env_var_override_voice_id(self, monkeypatch):
        """Environment variables override YAML values."""
        monkeypatch.setenv("ELEVENLABS_NARRATOR_VOICE_ID", "env-voice-id")
        cfg = ObsidianConfig(config_path=Path("/nonexistent.yaml"))
        assert cfg.voice.narrator_id == "env-voice-id"

    def test_env_var_override_budget(self, monkeypatch):
        monkeypatch.setenv("COST_BUDGET_MAX_USD", "25.50")
        cfg = ObsidianConfig(config_path=Path("/nonexistent.yaml"))
        assert cfg.cost.budget_max_usd == 25.50

    def test_env_var_override_image_model(self, monkeypatch):
        monkeypatch.setenv("IMAGE_MODEL", "flux")
        cfg = ObsidianConfig(config_path=Path("/nonexistent.yaml"))
        assert cfg.models.image_provider == "flux"

    def test_items_iteration(self):
        cfg = ObsidianConfig(config_path=Path("/nonexistent.yaml"))
        keys = list(cfg.voice.body.keys())
        assert "stability" in keys
        assert "similarity_boost" in keys


class TestConfigIntegrationWithPipelineConfig:
    def test_pipeline_config_reads_from_yaml(self):
        """pipeline_config module-level constants should match YAML values."""
        from core.pipeline_config import (
            NARRATOR_VOICE_ID,
            SCRIPT_MIN_WORDS,
            VIDEO_FPS,
            API_MAX_RETRIES,
        )
        # These should be the defaults from obsidian.yaml
        assert NARRATOR_VOICE_ID == "JBFqnCBsd6RMkjVDRZzb"
        assert SCRIPT_MIN_WORDS == 1000
        assert VIDEO_FPS == 30
        assert API_MAX_RETRIES == 5

    def test_scoring_config_populated(self):
        from core.pipeline_config import SCORING_CONFIG
        assert SCORING_CONFIG["maturity_threshold"] == 15
        assert SCORING_CONFIG["max_score"] == 1.0

    def test_voice_dicts_are_real_dicts(self):
        """Voice settings must be plain dicts, not _ConfigSection objects."""
        from core.pipeline_config import VOICE_BODY, VOICE_HOOK, VOICE_QUOTE
        assert isinstance(VOICE_BODY, dict)
        assert isinstance(VOICE_HOOK, dict)
        assert isinstance(VOICE_QUOTE, dict)
        assert "stability" in VOICE_BODY
