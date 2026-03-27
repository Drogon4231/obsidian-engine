"""Tests for core/feedback_loops.py — feedback loop closers."""

import json

from core.feedback_loops import (
    aggregate_comment_intelligence,
    extract_content_performance_signals,
    compute_era_retention_bands,
    compute_audio_performance_signals,
    _rank,
)


# ── Rank helper ────────────────────────────────────────────────────────────


class TestRank:
    def test_simple_ranking(self):
        assert _rank([3, 1, 2]) == [3.0, 1.0, 2.0]

    def test_ties(self):
        ranks = _rank([1, 2, 2, 3])
        assert ranks[0] == 1.0
        assert ranks[1] == 2.5  # tied
        assert ranks[2] == 2.5  # tied
        assert ranks[3] == 4.0

    def test_all_same(self):
        ranks = _rank([5, 5, 5])
        assert all(r == 2.0 for r in ranks)

    def test_single(self):
        assert _rank([42]) == [1.0]


# ── Comment intelligence ───────────────────────────────────────────────────


class TestCommentIntelligence:
    def test_no_outputs_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = aggregate_comment_intelligence({})
        assert result["videos_analyzed"] == 0
        assert result["trending_requests"] == []

    def test_empty_dir(self, tmp_path, monkeypatch):
        (tmp_path / "outputs").mkdir()
        monkeypatch.chdir(tmp_path)
        result = aggregate_comment_intelligence({})
        assert result["videos_analyzed"] == 0

    def test_aggregates_topics(self, tmp_path, monkeypatch):
        out = tmp_path / "outputs"
        out.mkdir()

        # Two comment analysis files
        (out / "comment_analysis_vid1.json").write_text(json.dumps({
            "status": "complete",
            "comment_count": 10,
            "sentiment": {"overall_sentiment": "positive", "praise": ["great editing"], "criticisms": []},
            "topic_requests": [
                {"topic": "Black holes", "frequency": 5, "total_likes": 20, "sample_comments": []},
                {"topic": "Mars", "frequency": 2, "total_likes": 8, "sample_comments": []},
            ],
        }))
        (out / "comment_analysis_vid2.json").write_text(json.dumps({
            "status": "complete",
            "comment_count": 8,
            "sentiment": {"overall_sentiment": "mixed", "praise": ["cool topic"], "criticisms": ["too long"]},
            "topic_requests": [
                {"topic": "black holes", "frequency": 3, "total_likes": 15, "sample_comments": []},
            ],
        }))

        monkeypatch.chdir(tmp_path)
        result = aggregate_comment_intelligence({})
        assert result["videos_analyzed"] == 2
        # "black holes" merged (case-insensitive)
        bh = [t for t in result["trending_requests"] if t["topic"] == "black holes"]
        assert len(bh) == 1
        assert bh[0]["total_frequency"] == 8
        assert bh[0]["total_likes"] == 35

        assert "great editing" in result["praise_themes"]
        assert "too long" in result["criticism_themes"]
        assert result["sentiment_trajectory"]["positive_pct"] == 50.0

    def test_skips_incomplete(self, tmp_path, monkeypatch):
        out = tmp_path / "outputs"
        out.mkdir()
        (out / "comment_analysis_vid1.json").write_text(json.dumps({
            "status": "no_comments", "comment_count": 0,
        }))
        monkeypatch.chdir(tmp_path)
        result = aggregate_comment_intelligence({})
        assert result["videos_analyzed"] == 0


# ── Content performance signals ────────────────────────────────────────────


class TestContentPerformance:
    def test_empty_insights(self):
        result = extract_content_performance_signals({})
        assert result["best_structure_types"] == []
        assert result["optimal_scene_count_range"] is None

    def test_extracts_structure_ranking(self):
        insights = {
            "content_quality_correlation": {
                "feature_correlations": {
                    "structure_type_vs_retention": {
                        "three_act": {"avg_retention": 45.0, "count": 5},
                        "linear": {"avg_retention": 38.0, "count": 3},
                    },
                    "hook_type_vs_retention": {
                        "question": {"avg_retention": 48.0},
                        "statement": {"avg_retention": 40.0},
                    },
                    "scene_count_bands": {
                        "20-25": {"avg_retention": 46.0},
                        "25-30": {"avg_retention": 42.0},
                    },
                    "has_twist_impact": {
                        "with": {"avg_retention": 47.0},
                        "without": {"avg_retention": 40.0},
                    },
                    "has_hook_moment_impact": {
                        "with": {"avg_retention": 50.0},
                        "without": {"avg_retention": 42.0},
                    },
                    "script_quality_correlations": {
                        "word_count": 0.35,
                        "readability": -0.22,
                        "tiny_feature": 0.05,  # below threshold
                    },
                },
            },
        }
        result = extract_content_performance_signals(insights)
        assert result["best_structure_types"][0]["type"] == "three_act"
        assert result["best_hook_types"][0]["type"] == "question"
        assert result["optimal_scene_count_range"] == "20-25"
        assert result["twist_impact"] == 7.0
        assert result["hook_moment_impact"] == 8.0
        assert len(result["script_quality_signals"]) == 2  # tiny_feature excluded


# ── Era retention bands ────────────────────────────────────────────────────


class TestEraRetention:
    def test_empty_stats(self):
        assert compute_era_retention_bands({}) == {}
        assert compute_era_retention_bands({"per_video_stats": []}) == {}

    def test_groups_by_era_and_band(self):
        insights = {
            "per_video_stats": [
                {
                    "content_classification": {"era": "mythology"},
                    "avg_retention_pct": 50.0,
                    "avg_view_duration_seconds": 300,  # 300s watched / 50% = 600s total = 10min
                },
                {
                    "content_classification": {"era": "mythology"},
                    "avg_retention_pct": 40.0,
                    "avg_view_duration_seconds": 240,  # 240s / 40% = 600s = 10min
                },
                {
                    "content_classification": {"era": "space"},
                    "avg_retention_pct": 60.0,
                    "avg_view_duration_seconds": 180,  # 180s / 60% = 300s = 5min
                },
            ],
        }
        result = compute_era_retention_bands(insights)
        assert "mythology" in result
        assert "space" in result
        assert result["mythology"]["8_to_12min"]["sample_count"] == 2
        assert result["mythology"]["8_to_12min"]["avg_retention"] == 45.0
        assert result["space"]["under_8min"]["sample_count"] == 1


# ── Audio performance signals ──────────────────────────────────────────────


class TestAudioPerformance:
    def test_insufficient_data(self):
        result = compute_audio_performance_signals([])
        assert result["sample_size"] == 0
        assert result["param_correlations"] == []

    def test_computes_correlations(self):
        # Create observations with clear correlation: higher pause.reveal → higher retention
        observations = []
        for i in range(10):
            observations.append({
                "params": {"pause.reveal": 1.0 + i * 0.3},
                "metrics": {"retention_pct": 30.0 + i * 2.0},
            })
        result = compute_audio_performance_signals(observations)
        assert result["sample_size"] == 10

        # Should find positive correlation for pause.reveal
        pr_corr = [c for c in result["param_correlations"] if c["param"] == "pause.reveal"]
        assert len(pr_corr) == 1
        assert pr_corr[0]["correlation"] > 0.5
        assert pr_corr[0]["direction"] == "higher_is_better"

    def test_best_configs_from_top_quartile(self):
        observations = []
        for i in range(12):
            observations.append({
                "params": {"pause.reveal": 1.0 + i * 0.1, "ducking.speech_volume": 0.08},
                "metrics": {"retention_pct": 20.0 + i * 5.0},
            })
        result = compute_audio_performance_signals(observations)
        assert len(result["best_performing_configs"]) <= 3
        # Best config should have highest retention
        if result["best_performing_configs"]:
            assert result["best_performing_configs"][0]["avg_retention"] >= 60.0

    def test_skips_missing_metrics(self):
        observations = [
            {"params": {"pause.reveal": 1.5}, "metrics": None},
            {"params": {"pause.reveal": 1.5}, "metrics": {}},
        ] + [
            {"params": {"pause.reveal": 1.0 + i * 0.2}, "metrics": {"retention_pct": 30 + i}}
            for i in range(6)
        ]
        result = compute_audio_performance_signals(observations)
        assert result["sample_size"] == 6
