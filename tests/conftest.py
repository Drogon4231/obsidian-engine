"""
Shared test fixtures for the Obsidian Archive test suite.

Provides:
- Mock data factories for scenes, video_data, channel_insights
- Temp directory isolation for filesystem-writing tests
- Mock API fixtures for call_agent and external services
- Pytest markers for test categorization
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Pytest Configuration ────────────────────────────────────────────────────────

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: fast isolated unit tests")
    config.addinivalue_line("markers", "integration: tests that verify cross-module contracts")
    config.addinivalue_line("markers", "slow: tests that take >2 seconds (e.g. stress tests)")


# ── Temp Outputs Fixture ────────────────────────────────────────────────────────

@pytest.fixture
def tmp_outputs(tmp_path):
    """Redirect OUTPUTS_DIR to a temp directory for filesystem isolation.

    Use this fixture in any test that writes to diagnostic logs, TTS cache,
    re-hook log, exemplars, or any other file under outputs/.
    """
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    with patch("core.pipeline_config.OUTPUTS_DIR", outputs_dir):
        yield outputs_dir


# ── Scene & Video Data Factories ────────────────────────────────────────────────

SAMPLE_MOODS = ["dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"]

SAMPLE_NARRATIVE_FUNCTIONS = [
    "hook", "exposition", "exposition", "rising_action",
    "complication", "climax", "reveal", "reflection",
    "falling_action", "resolution",
]


def make_scene(
    index: int = 0,
    text: str = "This is a test narration sentence for the scene.",
    mood: str = "dark",
    narrative_function: str = "exposition",
    **overrides,
) -> dict:
    """Create a single scene dict with sensible defaults."""
    scene = {
        "scene_number": index + 1,
        "text": text,
        "mood": mood,
        "narrative_function": narrative_function,
        "image_prompt": f"A dark scene depicting {text[:30]}",
        "duration_seconds": 6.0,
    }
    scene.update(overrides)
    return scene


def make_scenes(count: int = 10) -> list[dict]:
    """Create a list of scenes covering diverse moods and narrative functions."""
    scenes = []
    for i in range(count):
        mood = SAMPLE_MOODS[i % len(SAMPLE_MOODS)]
        nf = SAMPLE_NARRATIVE_FUNCTIONS[i] if i < len(SAMPLE_NARRATIVE_FUNCTIONS) else "exposition"
        word_count = 8 if nf == "hook" else 15 if nf == "reflection" else 12
        text = " ".join(["word"] * word_count)
        scenes.append(make_scene(index=i, text=text, mood=mood, narrative_function=nf))
    return scenes


def make_video_data(scenes: list[dict] | None = None, **overrides) -> dict:
    """Create a complete video_data dict with all fields."""
    if scenes is None:
        scenes = make_scenes()
    data = {
        "topic": "The Mysterious Disappearance of Flight 19",
        "era": "cold_war",
        "title": "The Night 5 Planes Vanished Without a Trace",
        "description": "In December 1945, five Navy bombers took off from Fort Lauderdale...",
        "scenes": scenes,
        "music_file": "epidemic_dark_01_shadows.mp3",
        "music_start_offset": 5.0,
        "music_secondary": "epidemic_tense_02_pursuit.mp3",
        "music_secondary_start_offset": 12.0,
        "total_duration": 480.0,
        "fps": 30,
    }
    data.update(overrides)
    return data


def make_channel_insights(**overrides) -> dict:
    """Create a channel_insights dict with realistic test data."""
    insights = {
        "channel_stats": {
            "total_videos": 25,
            "total_subscribers": 12000,
            "total_views": 450000,
            "avg_views_per_video": 18000,
        },
        "era_performance": {
            "cold_war": {"avg_views": 22000, "video_count": 5, "avg_retention": 0.45},
            "ww2": {"avg_views": 25000, "video_count": 4, "avg_retention": 0.48},
            "ancient": {"avg_views": 15000, "video_count": 3, "avg_retention": 0.40},
        },
        "audience_sentiment": {
            "voice": {"rolling_avg": 7.5, "trend": "stable"},
            "music": {"rolling_avg": 8.0, "trend": "improving"},
            "pacing": {"rolling_avg": 6.5, "trend": "declining"},
            "visuals": {"rolling_avg": 7.0, "trend": "stable"},
            "topic": {"rolling_avg": 8.5, "trend": "stable"},
        },
        "recent_videos": [
            {"title": "Test Video 1", "views": 20000, "era": "cold_war"},
            {"title": "Test Video 2", "views": 15000, "era": "ww2"},
        ],
    }
    insights.update(overrides)
    return insights


def make_word_timestamps(scene_count: int = 10, words_per_scene: int = 12) -> dict:
    """Create a word_timestamps structure matching TTS output format."""
    words = []
    current_time = 0.0
    scene_word_ranges = {}

    for s in range(scene_count):
        scene_start_word = len(words)
        for w in range(words_per_scene):
            start = current_time
            end = current_time + 0.3
            words.append({
                "word": f"word_{s}_{w}",
                "start": round(start, 3),
                "end": round(end, 3),
            })
            current_time = end + 0.05  # small gap between words
        scene_word_ranges[str(s)] = [scene_start_word, len(words) - 1]

    return {
        "words": words,
        "scene_word_ranges": scene_word_ranges,
        "total_duration": round(current_time, 3),
    }


def make_music_analysis() -> dict:
    """Create a music_analysis.json structure with track features."""
    return {
        "generated_at": "2026-03-20T10:00:00+00:00",
        "track_count": 3,
        "tracks": {
            "epidemic_dark_01_shadows.mp3": {
                "duration_seconds": 240.0,
                "tempo_bpm": 85.0,
                "key": "D",
                "mode": "minor",
                "energy_curve": [0.2, 0.3, 0.5, 0.7, 1.0, 0.9, 0.8, 0.6, 0.4, 0.3],
                "sections": [
                    {"label": "intro", "start": 0.0, "end": 30.0},
                    {"label": "build", "start": 30.0, "end": 80.0},
                    {"label": "climax", "start": 80.0, "end": 160.0},
                    {"label": "resolution", "start": 160.0, "end": 240.0},
                ],
                "peak_moments": [95.0, 125.0],
                "_file_size": 5000000,
            },
            "epidemic_tense_02_pursuit.mp3": {
                "duration_seconds": 180.0,
                "tempo_bpm": 120.0,
                "key": "A",
                "mode": "minor",
                "energy_curve": [0.4, 0.6, 0.8, 1.0, 0.9, 0.7, 0.5, 0.3],
                "sections": [
                    {"label": "build", "start": 0.0, "end": 60.0},
                    {"label": "climax", "start": 60.0, "end": 120.0},
                    {"label": "resolution", "start": 120.0, "end": 180.0},
                ],
                "peak_moments": [75.0],
                "_file_size": 3500000,
            },
            "epidemic_reverent_03_dawn.mp3": {
                "duration_seconds": 300.0,
                "tempo_bpm": 70.0,
                "key": "G",
                "mode": "major",
                "energy_curve": [0.1, 0.2, 0.3, 0.4, 0.5, 0.5, 0.4, 0.3, 0.2, 0.1],
                "sections": [
                    {"label": "intro", "start": 0.0, "end": 60.0},
                    {"label": "build", "start": 60.0, "end": 150.0},
                    {"label": "climax", "start": 150.0, "end": 210.0},
                    {"label": "resolution", "start": 210.0, "end": 300.0},
                ],
                "peak_moments": [175.0],
                "_file_size": 6000000,
            },
        },
    }


# ── Fixture File Loaders ────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_scenes():
    """Provide a 10-scene script covering all moods and narrative functions."""
    return make_scenes(10)


@pytest.fixture
def sample_video_data(sample_scenes):
    """Provide a complete video_data dict with all fields."""
    return make_video_data(sample_scenes)


@pytest.fixture
def sample_channel_insights():
    """Provide a channel_insights dict with realistic data."""
    return make_channel_insights()


@pytest.fixture
def sample_word_timestamps():
    """Provide word timestamps matching a 10-scene, 12-words-per-scene video."""
    return make_word_timestamps(10, 12)


@pytest.fixture
def sample_music_analysis():
    """Provide music analysis data for 3 test tracks."""
    return make_music_analysis()


# ── Mock API Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_anthropic():
    """Mock the anthropic module to prevent real API calls."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"result": "mocked"}')]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
    mock_client.messages.create.return_value = mock_response
    with patch.dict("sys.modules", {"anthropic": MagicMock()}):
        yield mock_client


@pytest.fixture
def mock_external_apis():
    """Blanket mock for all external API modules.

    Use this in integration tests where you want real pipeline code to run
    but don't want any external API calls.
    """
    mocks = {
        "anthropic": MagicMock(),
        "elevenlabs": MagicMock(),
        "fal_client": MagicMock(),
        "supabase": MagicMock(),
    }
    with patch.dict("sys.modules", mocks):
        yield mocks
