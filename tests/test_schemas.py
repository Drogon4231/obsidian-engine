"""
Schema structural validation tests.

Validates that mock fixtures and factory functions produce data matching
the structural contracts expected by the pipeline. These tests are
CI-safe (no API calls, no filesystem writes beyond tmp).
"""
from __future__ import annotations

import json
from pathlib import Path

import sys

import pytest

# conftest factories are auto-loaded by pytest but not directly importable;
# add tests/ to path so we can import them for direct use in test code.
sys.path.insert(0, str(Path(__file__).parent))
from conftest import (
    make_scene,
    make_scenes,
    make_video_data,
    make_channel_insights,
    make_word_timestamps,
    make_music_analysis,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MOCK_RESPONSES_DIR = FIXTURES_DIR / "mock_responses"


# ── Stage output required keys (mirrors run_pipeline.validate_stage_output) ──

STAGE_REQUIRED_KEYS = {
    1: ["core_facts", "key_figures"],
    2: ["chosen_angle"],
    3: ["hook", "act1", "act2", "act3"],
    4: ["full_script"],
    5: ["overall_verdict"],
    6: ["recommended_title"],
    7: ["scenes"],
}


# ── Scene Schema ─────────────────────────────────────────────────────────────

VALID_MOODS = {"dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"}

from core.schema_validator import VALID_NARRATIVE_FUNCTIONS


class TestSceneSchema:
    """Validate scene dicts produced by factories and fixtures."""

    @pytest.mark.unit
    def test_scene_has_required_keys(self):
        scene = make_scene()
        required = {"scene_number", "text", "mood", "narrative_function", "image_prompt"}
        assert required.issubset(scene.keys()), f"Missing: {required - scene.keys()}"

    @pytest.mark.unit
    def test_scene_mood_is_valid(self):
        for i in range(20):
            scene = make_scenes(20)[i]
            assert scene["mood"] in VALID_MOODS, f"Scene {i}: invalid mood '{scene['mood']}'"

    @pytest.mark.unit
    def test_scene_narrative_function_is_valid(self):
        for scene in make_scenes(10):
            assert scene["narrative_function"] in VALID_NARRATIVE_FUNCTIONS, (
                f"Scene {scene['scene_number']}: invalid narrative_function '{scene['narrative_function']}'"
            )

    @pytest.mark.unit
    def test_scene_number_is_1_indexed(self):
        scenes = make_scenes(5)
        numbers = [s["scene_number"] for s in scenes]
        assert numbers == [1, 2, 3, 4, 5]

    @pytest.mark.unit
    def test_scene_overrides_work(self):
        scene = make_scene(mood="wonder", text="custom text", custom_field=42)
        assert scene["mood"] == "wonder"
        assert scene["text"] == "custom text"
        assert scene["custom_field"] == 42


# ── Video Data Schema ────────────────────────────────────────────────────────

class TestVideoDataSchema:
    """Validate video_data dicts produced by factory."""

    REQUIRED_KEYS = {
        "topic", "era", "title", "scenes", "music_file",
        "music_start_offset", "total_duration", "fps",
    }

    @pytest.mark.unit
    def test_video_data_has_required_keys(self):
        vd = make_video_data()
        assert self.REQUIRED_KEYS.issubset(vd.keys()), f"Missing: {self.REQUIRED_KEYS - vd.keys()}"

    @pytest.mark.unit
    def test_video_data_scenes_is_list(self):
        vd = make_video_data()
        assert isinstance(vd["scenes"], list)
        assert len(vd["scenes"]) == 10

    @pytest.mark.unit
    def test_video_data_fps_is_positive_int(self):
        vd = make_video_data()
        assert isinstance(vd["fps"], int)
        assert vd["fps"] > 0

    @pytest.mark.unit
    def test_video_data_overrides(self):
        vd = make_video_data(fps=60, era="ww2")
        assert vd["fps"] == 60
        assert vd["era"] == "ww2"


# ── Channel Insights Schema ─────────────────────────────────────────────────

class TestChannelInsightsSchema:
    """Validate channel_insights dicts."""

    @pytest.mark.unit
    def test_has_required_top_level_keys(self):
        ci = make_channel_insights()
        required = {"channel_stats", "era_performance", "audience_sentiment", "recent_videos"}
        assert required.issubset(ci.keys())

    @pytest.mark.unit
    def test_era_performance_has_expected_fields(self):
        ci = make_channel_insights()
        for era, data in ci["era_performance"].items():
            assert "avg_views" in data, f"Era '{era}' missing avg_views"
            assert "video_count" in data, f"Era '{era}' missing video_count"
            assert "avg_retention" in data, f"Era '{era}' missing avg_retention"

    @pytest.mark.unit
    def test_audience_sentiment_categories(self):
        ci = make_channel_insights()
        expected = {"voice", "music", "pacing", "visuals", "topic"}
        assert expected.issubset(ci["audience_sentiment"].keys())
        for cat, data in ci["audience_sentiment"].items():
            assert "rolling_avg" in data
            assert "trend" in data


# ── Word Timestamps Schema ───────────────────────────────────────────────────

class TestWordTimestampsSchema:
    """Validate word_timestamps structure."""

    @pytest.mark.unit
    def test_has_required_keys(self):
        wt = make_word_timestamps()
        assert "words" in wt
        assert "scene_word_ranges" in wt
        assert "total_duration" in wt

    @pytest.mark.unit
    def test_words_have_timing(self):
        wt = make_word_timestamps(scene_count=2, words_per_scene=5)
        for w in wt["words"]:
            assert "word" in w
            assert "start" in w
            assert "end" in w
            assert w["end"] > w["start"]

    @pytest.mark.unit
    def test_words_are_chronological(self):
        wt = make_word_timestamps()
        for i in range(1, len(wt["words"])):
            assert wt["words"][i]["start"] >= wt["words"][i - 1]["start"]

    @pytest.mark.unit
    def test_scene_word_ranges_cover_all_scenes(self):
        wt = make_word_timestamps(scene_count=10, words_per_scene=12)
        assert len(wt["scene_word_ranges"]) == 10
        for s in range(10):
            assert str(s) in wt["scene_word_ranges"]


# ── Music Analysis Schema ────────────────────────────────────────────────────

class TestMusicAnalysisSchema:
    """Validate music_analysis structure."""

    @pytest.mark.unit
    def test_has_required_keys(self):
        ma = make_music_analysis()
        assert "tracks" in ma
        assert "track_count" in ma
        assert ma["track_count"] == len(ma["tracks"])

    @pytest.mark.unit
    def test_track_has_required_fields(self):
        ma = make_music_analysis()
        required_track_keys = {
            "duration_seconds", "tempo_bpm", "key", "mode",
            "energy_curve", "sections", "peak_moments",
        }
        for name, track in ma["tracks"].items():
            missing = required_track_keys - track.keys()
            assert not missing, f"Track '{name}' missing: {missing}"

    @pytest.mark.unit
    def test_sections_are_contiguous(self):
        ma = make_music_analysis()
        for name, track in ma["tracks"].items():
            sections = track["sections"]
            for i in range(1, len(sections)):
                assert sections[i]["start"] == sections[i - 1]["end"], (
                    f"Track '{name}': gap between section {i-1} and {i}"
                )

    @pytest.mark.unit
    def test_peak_moments_within_duration(self):
        ma = make_music_analysis()
        for name, track in ma["tracks"].items():
            for peak in track["peak_moments"]:
                assert 0 <= peak <= track["duration_seconds"], (
                    f"Track '{name}': peak {peak} outside duration {track['duration_seconds']}"
                )


# ── Fixture JSON Files ───────────────────────────────────────────────────────

class TestFixtureFiles:
    """Validate that JSON fixture files are valid and structurally correct."""

    @pytest.mark.unit
    def test_script_fixture_loads(self):
        path = FIXTURES_DIR / "mock_script_10_scenes.json"
        data = json.loads(path.read_text())
        assert "scenes" in data
        assert len(data["scenes"]) == 10
        for scene in data["scenes"]:
            assert "scene_number" in scene
            assert "text" in scene
            assert "mood" in scene

    @pytest.mark.unit
    def test_channel_insights_fixture_loads(self):
        path = FIXTURES_DIR / "mock_channel_insights.json"
        data = json.loads(path.read_text())
        assert "channel_stats" in data
        assert "era_performance" in data

    @pytest.mark.unit
    def test_word_timestamps_fixture_loads(self):
        path = FIXTURES_DIR / "mock_word_timestamps.json"
        data = json.loads(path.read_text())
        assert "words" in data
        assert len(data["words"]) > 0

    @pytest.mark.unit
    def test_music_analysis_fixture_loads(self):
        path = FIXTURES_DIR / "mock_music_analysis.json"
        data = json.loads(path.read_text())
        assert "tracks" in data
        assert len(data["tracks"]) == 3


# ── Mock Response Files ──────────────────────────────────────────────────────

class TestMockResponseFiles:
    """Validate that agent mock responses match pipeline stage contracts."""

    def _load(self, name: str) -> dict:
        path = MOCK_RESPONSES_DIR / name
        return json.loads(path.read_text())

    @pytest.mark.unit
    def test_research_response_has_stage1_keys(self):
        data = self._load("research_agent.json")
        for key in STAGE_REQUIRED_KEYS[1]:
            assert key in data, f"research_agent.json missing '{key}'"

    @pytest.mark.unit
    def test_originality_response_has_stage2_keys(self):
        data = self._load("originality_agent.json")
        for key in STAGE_REQUIRED_KEYS[2]:
            assert key in data, f"originality_agent.json missing '{key}'"

    @pytest.mark.unit
    def test_seo_response_has_stage6_keys(self):
        data = self._load("seo_agent.json")
        for key in STAGE_REQUIRED_KEYS[6]:
            assert key in data, f"seo_agent.json missing '{key}'"

    @pytest.mark.unit
    def test_scene_breakdown_response_has_stage7_keys(self):
        data = self._load("scene_breakdown_agent.json")
        for key in STAGE_REQUIRED_KEYS[7]:
            assert key in data, f"scene_breakdown_agent.json missing '{key}'"

    @pytest.mark.unit
    def test_fact_verification_response_has_stage5_keys(self):
        data = self._load("fact_verification_agent.json")
        for key in STAGE_REQUIRED_KEYS[5]:
            assert key in data, f"fact_verification_agent.json missing '{key}'"

    @pytest.mark.unit
    def test_short_script_response_structure(self):
        data = self._load("short_script_agent.json")
        required = {"hook", "full_script", "word_count", "estimated_seconds", "short_title"}
        missing = required - data.keys()
        assert not missing, f"short_script_agent.json missing: {missing}"
