"""
Configuration loader — reads obsidian.yaml and provides typed access.

Load order (each layer overrides the previous):
1. Hardcoded defaults (in this module)
2. obsidian.yaml (or OBSIDIAN_CONFIG env var)
3. Environment variables (for secrets and deployment overrides)

Usage:
    from core.config import cfg

    cfg.voice.narrator_id      # "JBFqnCBsd6RMkjVDRZzb"
    cfg.models.premium         # "claude-opus-4-6"
    cfg.script.min_words       # 1000
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts."""
    merged = base.copy()
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


class _ConfigSection:
    """Dot-access wrapper around a dict section."""

    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name: str) -> Any:
        try:
            val = self._data[name]
        except KeyError:
            raise AttributeError(f"Config has no key '{name}'")
        if isinstance(val, dict):
            return _ConfigSection(val)
        return val

    def __getitem__(self, key: str) -> Any:
        val = self._data[key]
        if isinstance(val, dict):
            return _ConfigSection(val)
        return val

    def get(self, key: str, default: Any = None) -> Any:
        val = self._data.get(key, default)
        if isinstance(val, dict):
            return _ConfigSection(val)
        return val

    def to_dict(self) -> dict:
        return self._data

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"Config({self._data})"

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()


class ObsidianConfig(_ConfigSection):
    """Root configuration object loaded from obsidian.yaml."""

    def __init__(self, config_path: Path | None = None):
        # Defaults
        defaults = _DEFAULTS.copy()

        # Load YAML
        if config_path is None:
            env_path = os.getenv("OBSIDIAN_CONFIG")
            if env_path:
                config_path = Path(env_path)
            else:
                config_path = BASE_DIR / "obsidian.yaml"

        yaml_data = {}
        if config_path.exists():
            with open(config_path) as f:
                yaml_data = yaml.safe_load(f) or {}

        merged = _deep_merge(defaults, yaml_data)

        # Environment variable overrides for voice IDs
        env_narrator = os.getenv("ELEVENLABS_NARRATOR_VOICE_ID")
        if env_narrator:
            merged.setdefault("voice", {})["narrator_id"] = env_narrator
        env_quote = os.getenv("ELEVENLABS_QUOTE_VOICE_ID")
        if env_quote:
            merged.setdefault("voice", {})["quote_id"] = env_quote

        # Environment variable overrides for image model
        env_image_model = os.getenv("IMAGE_MODEL")
        if env_image_model:
            merged.setdefault("models", {})["image_provider"] = env_image_model

        # Environment variable overrides for budget
        env_budget = os.getenv("COST_BUDGET_MAX_USD")
        if env_budget:
            merged.setdefault("cost", {})["budget_max_usd"] = float(env_budget)

        # Environment variable overrides for WPM gate
        env_wpm = os.getenv("ENFORCE_WPM_GATE")
        if env_wpm:
            merged.setdefault("quality", {})["enforce_wpm_gate"] = env_wpm.lower() == "true"

        # Environment variable overrides for server
        env_port = os.getenv("PORT")
        if env_port:
            merged.setdefault("server", {})["port"] = int(env_port)

        super().__init__(merged)
        self._path = config_path

    @property
    def config_path(self) -> Path:
        return self._path


# ── Defaults ──────────────────────────────────────────────────────────────────
# These match the values that were previously hardcoded across the codebase.
# obsidian.yaml overrides these.

_DEFAULTS: dict = {
    "voice": {
        "narrator_id": "JBFqnCBsd6RMkjVDRZzb",
        "quote_id": "pNInz6obpgDQGcFmaJgB",
        "model": "eleven_v3",
        "body": {"stability": 0.38, "similarity_boost": 0.82, "style": 0.60, "use_speaker_boost": True},
        "hook": {"stability": 0.28, "similarity_boost": 0.85, "style": 0.75, "use_speaker_boost": True},
        "quote": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.40, "use_speaker_boost": True},
        "speed_body": 0.76,
        "speed_hook": 0.82,
        "speed_quote": 0.74,
        "pause_reveal": 1.8,
        "pause_breathing": 1.2,
        "pause_act_transition": 0.9,
        "pause_default": 0.4,
    },
    "models": {
        "premium": "claude-opus-4-6",
        "full": "claude-sonnet-4-6",
        "light": "claude-haiku-4-5-20251001",
        "image_provider": "recraft",
        "image_quality_threshold": 7,
        "image_max_retries": 3,
        "fal_recraft": "fal-ai/recraft/v3/text-to-image",
        "fal_flux": "fal-ai/flux-pro/v1.1-ultra",
        "fal_flux_kontext": "fal-ai/flux-pro/kontext",
        "max_tokens": 4000,
    },
    "agents": {},
    "script": {
        "min_words": 1000,
        "max_words": 2500,
        "short_min_words": 80,
        "short_max_words": 180,
    },
    "video": {
        "fps": 30,
        "crf": 15,
        "long_width": 1920,
        "long_height": 1080,
        "short_width": 1080,
        "short_height": 1920,
        "max_scene_seconds": 12.0,
    },
    "audio": {
        "chunk_max_chars": 500,
        "tail_buffer_sec": 1.5,
        "min_duration": 300,
        "max_duration": 1200,
    },
    "quality": {
        "min_research_facts": 5,
        "min_research_figures": 2,
        "min_tags": 5,
        "min_scenes": 5,
        "min_video_size_mb": 50,
        "enforce_wpm_gate": False,
    },
    "cost": {
        "budget_max_usd": 0.0,
        "cleanup_after_upload": True,
        "cleanup_warn_disk_gb": 50,
    },
    "api": {
        "max_retries": 5,
        "backoff_base": 2,
        "timeout": 120,
    },
    "server": {
        "port": 8080,
        "max_triggers_per_hour": 3,
        "max_calls_per_minute": 10,
    },
    "schedule": {
        "videos_per_week": 1,
        "publish_days": ["tuesday"],
        "publish_time": "09:00",
        "discover_time": "08:00",
        "analytics_hour": 6,
        "topic_discovery": {"day": "monday", "hour": 8},
        "pipeline": {"day": "tuesday", "hour": 9},
    },
    "competitors": {},
    "scoring": {
        "maturity_threshold": 15,
        "max_score": 1.0,
        "min_score": 0.0,
        "default_topic_score": 0.5,
        "max_topics_per_discovery": 20,
        "experiment_cadence_default": 5,
        "experiment_cadence_throttled": 8,
    },
}

# ── Singleton ─────────────────────────────────────────────────────────────────
# Loaded once on first import. Tests can replace with: core.config.cfg = ObsidianConfig(path)

cfg = ObsidianConfig()
