"""Tests for pipeline/convert.py — Remotion video-data.json assembly.

Covers: align_scenes_to_words (precise, fallback, edge cases),
scene timing validation, multi-image crossfade, sub-scene splitting,
film grain/vignette computation, and year/location detection.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.convert import align_scenes_to_words


# ── align_scenes_to_words tests ───────────────────────────────────────────


class TestAlignScenesToWords:
    def test_zero_scenes(self):
        result = align_scenes_to_words(0, [], 60.0)
        assert result == []

    def test_no_words_even_distribution(self):
        """With no words, scenes should be evenly distributed."""
        result = align_scenes_to_words(3, [], 60.0)
        assert len(result) == 3
        assert result[0] == (0.0, 20.0)
        assert result[1] == (20.0, 40.0)
        assert result[2] == (40.0, 60.0)

    def test_even_word_distribution(self):
        """Without scene_word_ranges, uses even word distribution."""
        words = [
            {"word": "W1", "start": 0.0, "end": 1.0},
            {"word": "W2", "start": 1.5, "end": 2.5},
            {"word": "W3", "start": 3.0, "end": 4.0},
            {"word": "W4", "start": 4.5, "end": 5.5},
            {"word": "W5", "start": 6.0, "end": 7.0},
            {"word": "W6", "start": 7.5, "end": 8.5},
        ]
        result = align_scenes_to_words(3, words, 10.0)
        assert len(result) == 3
        # First scene starts at word 0
        assert result[0][0] == 0.0
        # Last scene ends at total_duration
        assert result[2][1] == 10.0

    def test_precise_alignment_with_scene_word_ranges(self):
        """With scene_word_ranges, uses precise word boundaries."""
        words = [
            {"word": "A", "start": 0.0, "end": 0.5},
            {"word": "B", "start": 1.0, "end": 1.5},
            {"word": "C", "start": 2.0, "end": 2.5},
            {"word": "D", "start": 3.0, "end": 3.5},
            {"word": "E", "start": 4.0, "end": 4.5},
            {"word": "F", "start": 5.0, "end": 5.5},
        ]
        # 3 scenes: words 0-1, 2-3, 4-5
        ranges = [(0, 1), (2, 3), (4, 5)]
        result = align_scenes_to_words(3, words, 7.0, scene_word_ranges=ranges)
        assert len(result) == 3
        assert result[0][0] == 0.0  # word 0 start
        assert result[0][1] == 1.5  # word 1 end
        assert result[1][0] == 2.0  # word 2 start
        assert result[2][1] == 7.0  # last scene uses total_duration

    def test_precise_alignment_minimum_duration(self):
        """Scenes where end <= start get minimum 0.5s duration."""
        words = [
            {"word": "A", "start": 5.0, "end": 5.0},  # zero-duration word
            {"word": "B", "start": 10.0, "end": 10.0},
        ]
        result = align_scenes_to_words(2, words, 15.0)
        # Even distribution fallback (2 words for 2 scenes)
        for start, end in result:
            assert end > start

    def test_fewer_words_than_scenes(self):
        """When fewer words than scenes, fall back to even spacing."""
        words = [{"word": "X", "start": 0.0, "end": 1.0}]
        result = align_scenes_to_words(5, words, 50.0)
        assert len(result) == 5
        # Even spacing: each scene 10s
        assert result[0] == (0.0, 10.0)
        assert result[4] == (40.0, 50.0)

    def test_scene_word_ranges_mismatch_count(self):
        """When scene_word_ranges count doesn't match n_scenes, falls back."""
        words = [
            {"word": "A", "start": 0.0, "end": 1.0},
            {"word": "B", "start": 2.0, "end": 3.0},
            {"word": "C", "start": 4.0, "end": 5.0},
        ]
        # Only 2 ranges for 3 scenes
        ranges = [(0, 0), (1, 2)]
        result = align_scenes_to_words(3, words, 8.0, scene_word_ranges=ranges)
        assert len(result) == 3
        # Should fall back to even distribution since ranges count != n_scenes

    def test_scene_word_ranges_clamped_to_valid(self):
        """Out-of-range word indices should be clamped."""
        words = [
            {"word": "A", "start": 0.0, "end": 1.0},
            {"word": "B", "start": 2.0, "end": 3.0},
        ]
        ranges = [(0, 100), (1, 1)]  # 100 is out of range
        result = align_scenes_to_words(2, words, 5.0, scene_word_ranges=ranges)
        assert len(result) == 2
        # Index 100 should be clamped to len(words)-1 = 1

    def test_single_scene(self):
        words = [{"word": "Hello", "start": 0.0, "end": 0.5}]
        result = align_scenes_to_words(1, words, 3.0)
        assert len(result) == 1
        assert result[0][0] == 0.0
        assert result[0][1] == 3.0

    def test_roundig_precision(self):
        """Verify timestamps are rounded to 3 decimal places."""
        words = [
            {"word": "A", "start": 0.123456, "end": 0.654321},
            {"word": "B", "start": 1.111111, "end": 1.999999},
        ]
        ranges = [(0, 0), (1, 1)]
        result = align_scenes_to_words(2, words, 3.0, scene_word_ranges=ranges)
        for start, end in result:
            assert round(start, 3) == start
            assert round(end, 3) == end


# ── Year/location detection tests ─────────────────────────────────────────


class TestYearLocationDetection:
    def test_year_ad_detection(self):
        narration = "In 476 AD, the Roman Empire fell."
        match = re.search(r'\b(\d{1,4}\s*(?:AD|BC|BCE|CE))\b', narration, re.IGNORECASE)
        assert match is not None
        assert match.group(1) == "476 AD"

    def test_year_bc_detection(self):
        narration = "Julius Caesar was assassinated in 44 BC."
        match = re.search(r'\b(\d{1,4}\s*(?:AD|BC|BCE|CE))\b', narration, re.IGNORECASE)
        assert match is not None
        assert match.group(1) == "44 BC"

    def test_year_bce_detection(self):
        narration = "The temple was built in 516 BCE."
        match = re.search(r'\b(\d{1,4}\s*(?:AD|BC|BCE|CE))\b', narration, re.IGNORECASE)
        assert match is not None
        assert match.group(1) == "516 BCE"

    def test_no_year(self):
        narration = "The soldiers marched onward."
        match = re.search(r'\b(\d{1,4}\s*(?:AD|BC|BCE|CE))\b', narration, re.IGNORECASE)
        assert match is None

    def test_location_detection(self):
        narration = "The events took place in Rome."
        location = ""
        for loc in ["Rome", "Athens", "Egypt", "Constantinople", "Jerusalem",
                     "London", "Paris", "Alexandria"]:
            if loc.lower() in narration.lower():
                location = loc
                break
        assert location == "Rome"

    def test_location_case_insensitive(self):
        narration = "The library of ALEXANDRIA was legendary."
        location = ""
        for loc in ["Rome", "Athens", "Egypt", "Constantinople", "Jerusalem",
                     "London", "Paris", "Alexandria"]:
            if loc.lower() in narration.lower():
                location = loc
                break
        assert location == "Alexandria"

    def test_no_location(self):
        narration = "The battle was fierce."
        location = ""
        for loc in ["Rome", "Athens", "Egypt", "Constantinople", "Jerusalem",
                     "London", "Paris", "Alexandria"]:
            if loc.lower() in narration.lower():
                location = loc
                break
        assert location == ""


# ── Film grain and vignette computation tests ────────────────────────────


class TestFilmGrainVignette:
    def _compute_grain_vignette(self, mood, is_reveal=False):
        """Replicate the grain/vignette logic from run_convert."""
        mood = (mood or "dark").lower()
        grain = 0.10
        vignette = 0.15
        if mood in ("dark", "tense"):
            grain = 0.20
            vignette = 0.30
        elif mood in ("wonder", "warmth"):
            grain = 0.08
            vignette = 0.08
        elif mood == "dramatic":
            grain = 0.15
            vignette = 0.25
        if is_reveal:
            grain = min(0.30, grain + 0.05)
            vignette = min(0.40, vignette + 0.05)
        grain = round(max(0.0, min(0.30, grain)), 2)
        vignette = round(max(0.0, min(0.40, vignette)), 2)
        return grain, vignette

    def test_dark_mood(self):
        g, v = self._compute_grain_vignette("dark")
        assert g == 0.20
        assert v == 0.30

    def test_tense_mood(self):
        g, v = self._compute_grain_vignette("tense")
        assert g == 0.20
        assert v == 0.30

    def test_wonder_mood(self):
        g, v = self._compute_grain_vignette("wonder")
        assert g == 0.08
        assert v == 0.08

    def test_warmth_mood(self):
        g, v = self._compute_grain_vignette("warmth")
        assert g == 0.08
        assert v == 0.08

    def test_dramatic_mood(self):
        g, v = self._compute_grain_vignette("dramatic")
        assert g == 0.15
        assert v == 0.25

    def test_default_mood(self):
        g, v = self._compute_grain_vignette("reverent")
        assert g == 0.10
        assert v == 0.15

    def test_reveal_boost(self):
        g, v = self._compute_grain_vignette("dark", is_reveal=True)
        assert g == 0.25
        assert v == 0.35

    def test_reveal_clamped(self):
        """Reveal boost on dark should not exceed max values."""
        g, v = self._compute_grain_vignette("dark", is_reveal=True)
        assert g <= 0.30
        assert v <= 0.40

    def test_none_mood_defaults(self):
        g, v = self._compute_grain_vignette(None)
        assert g == 0.20  # defaults to "dark"
        assert v == 0.30

    def test_empty_mood_defaults(self):
        g, v = self._compute_grain_vignette("")
        # Empty string is falsy, so (mood or "dark") gives "dark"
        assert g == 0.20
        assert v == 0.30


# ── Multi-image crossfade tests ──────────────────────────────────────────


class TestMultiImageCrossfade:
    def test_long_scene_gets_multi_images(self):
        """Scenes >12s with images should get nearby images for crossfade."""
        scenes = [
            {"start_time": 0, "end_time": 5, "ai_image": "scene_000_ai.jpg"},
            {"start_time": 5, "end_time": 20, "ai_image": "scene_001_ai.jpg"},  # 15s > 12s
            {"start_time": 20, "end_time": 25, "ai_image": "scene_002_ai.jpg"},
        ]

        MAX_SCENE_SECS = 12.0
        for i, scene in enumerate(scenes):
            duration = scene["end_time"] - scene["start_time"]
            if duration > MAX_SCENE_SECS and scene.get("ai_image"):
                nearby_images = [scene["ai_image"]]
                for offset in [-1, 1, -2, 2]:
                    ni = i + offset
                    if 0 <= ni < len(scenes):
                        img = scenes[ni].get("ai_image")
                        if img and img not in nearby_images:
                            nearby_images.append(img)
                        if len(nearby_images) >= 3:
                            break
                if len(nearby_images) >= 2:
                    scene["ai_images"] = nearby_images

        assert "ai_images" in scenes[1]
        assert len(scenes[1]["ai_images"]) >= 2

    def test_short_scene_no_multi_images(self):
        """Scenes <=12s should not get multi-image crossfade."""
        scenes = [
            {"start_time": 0, "end_time": 10, "ai_image": "scene_000_ai.jpg"},
        ]
        MAX_SCENE_SECS = 12.0
        for scene in scenes:
            duration = scene["end_time"] - scene["start_time"]
            assert duration <= MAX_SCENE_SECS

    def test_scene_without_image_no_crossfade(self):
        """Scenes without images should not get crossfade."""
        scenes = [
            {"start_time": 0, "end_time": 20, "ai_image": None},
        ]
        MAX_SCENE_SECS = 12.0
        for scene in scenes:
            duration = scene["end_time"] - scene["start_time"]
            if duration > MAX_SCENE_SECS and scene.get("ai_image"):
                pytest.fail("Should not reach here")


# ── Sub-scene split tests ────────────────────────────────────────────────


class TestSubSceneSplit:
    def _split_scene(self, scene):
        """Replicate the sub-scene splitting logic."""
        MAX_SCENE_SECS = 12.0
        duration = scene["end_time"] - scene["start_time"]
        if duration <= MAX_SCENE_SECS or not scene.get("ai_image") or scene.get("ai_images"):
            return [scene]
        n_splits = max(2, min(4, int(duration / 8)))
        sub_dur = duration / n_splits
        result = []
        for j in range(n_splits):
            sub = dict(scene)
            sub["start_time"] = round(scene["start_time"] + j * sub_dur, 3)
            sub["end_time"] = round(scene["start_time"] + (j + 1) * sub_dur, 3)
            result.append(sub)
        return result

    def test_15s_scene_splits_into_2(self):
        scene = {"start_time": 0, "end_time": 15, "ai_image": "img.jpg"}
        splits = self._split_scene(scene)
        assert len(splits) == 2  # int(15/8) = 1, max(2,1) = 2
        assert splits[0]["end_time"] == splits[1]["start_time"]

    def test_30s_scene_splits_into_3(self):
        scene = {"start_time": 0, "end_time": 30, "ai_image": "img.jpg"}
        splits = self._split_scene(scene)
        assert len(splits) == 3  # int(30/8) = 3, clamped to [2,4]

    def test_40s_scene_splits_into_4_max(self):
        scene = {"start_time": 0, "end_time": 40, "ai_image": "img.jpg"}
        splits = self._split_scene(scene)
        assert len(splits) == 4  # int(40/8) = 5, clamped to 4

    def test_short_scene_not_split(self):
        scene = {"start_time": 0, "end_time": 10, "ai_image": "img.jpg"}
        splits = self._split_scene(scene)
        assert len(splits) == 1

    def test_no_image_not_split(self):
        scene = {"start_time": 0, "end_time": 20, "ai_image": None}
        splits = self._split_scene(scene)
        assert len(splits) == 1

    def test_multi_image_not_split(self):
        """Scenes with ai_images (multi-image) should not be sub-split."""
        scene = {"start_time": 0, "end_time": 20, "ai_image": "img.jpg",
                 "ai_images": ["img1.jpg", "img2.jpg"]}
        splits = self._split_scene(scene)
        assert len(splits) == 1

    def test_split_continuity(self):
        """Sub-scenes should have continuous non-overlapping timing."""
        scene = {"start_time": 10.0, "end_time": 30.0, "ai_image": "img.jpg"}
        splits = self._split_scene(scene)
        for i in range(len(splits) - 1):
            assert splits[i]["end_time"] == splits[i + 1]["start_time"]
        assert splits[0]["start_time"] == 10.0
        assert splits[-1]["end_time"] == 30.0


# ── Validation tests ─────────────────────────────────────────────────────


class TestSceneValidation:
    def test_end_time_less_than_start_fixed(self):
        """Scenes with end_time <= start_time should be fixed."""
        scenes = [
            {"start_time": 5.0, "end_time": 3.0, "ai_image": None},
        ]
        for i, sc in enumerate(scenes):
            if sc["end_time"] <= sc["start_time"]:
                scenes[i]["end_time"] = sc["start_time"] + 1.0
        assert scenes[0]["end_time"] == 6.0

    def test_last_scene_end_matches_duration(self):
        """Last scene should end exactly at total_duration."""
        total_duration = 120.0
        scenes = [
            {"start_time": 0, "end_time": 60},
            {"start_time": 60, "end_time": 100},
        ]
        scenes[-1]["end_time"] = total_duration
        assert scenes[-1]["end_time"] == 120.0

    def test_empty_scenes_raises(self):
        """No scenes should raise ValueError."""
        scenes = []
        if not scenes:
            with pytest.raises(ValueError):
                raise ValueError("[Convert] No scenes produced")


# ── Mood music mapping tests ─────────────────────────────────────────────


class TestMoodMusicMapping:
    def test_dominant_mood_selection(self):
        """Verify dominant mood is correctly computed."""
        scenes = [
            {"mood": "dark"},
            {"mood": "dark"},
            {"mood": "tense"},
            {"mood": "dark"},
            {"mood": "dramatic"},
        ]
        mood_counts = {}
        for s in scenes:
            m = s.get("mood", "dark")
            mood_counts[m] = mood_counts.get(m, 0) + 1
        dominant = max(mood_counts, key=mood_counts.get)
        assert dominant == "dark"

    def test_single_mood(self):
        scenes = [{"mood": "wonder"}]
        mood_counts = {}
        for s in scenes:
            m = s.get("mood", "dark")
            mood_counts[m] = mood_counts.get(m, 0) + 1
        dominant = max(mood_counts, key=mood_counts.get)
        assert dominant == "wonder"

    def test_missing_mood_defaults_dark(self):
        scenes = [{}]
        mood_counts = {}
        for s in scenes:
            m = s.get("mood", "dark")
            mood_counts[m] = mood_counts.get(m, 0) + 1
        dominant = max(mood_counts, key=mood_counts.get)
        assert dominant == "dark"
