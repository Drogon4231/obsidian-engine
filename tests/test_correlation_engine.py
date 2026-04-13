"""Tests for intel.correlation_engine — 7-layer DAG correlation engine."""

from intel.correlation_engine import (
    _safe_float,
    _pearson,
    _pearson_with_p,
    _spearman,
    _correlate,
    _rank_transform,
    _compute_topic_health,
    JoinRegistry,
    CorrelationEngine,
)


# ── Statistical functions ────────────────────────────────────────────────────

class TestSafeFloat:
    def test_normal_value(self):
        assert _safe_float(3.14) == 3.14

    def test_string_number(self):
        assert _safe_float("42.5") == 42.5

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_nan_returns_none(self):
        assert _safe_float(float("nan")) is None

    def test_inf_returns_none(self):
        assert _safe_float(float("inf")) is None

    def test_non_numeric_string(self):
        assert _safe_float("abc") is None

    def test_integer(self):
        assert _safe_float(7) == 7.0


class TestPearson:
    def test_perfect_positive(self):
        r = _pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert r == 1.0

    def test_perfect_negative(self):
        r = _pearson([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])
        assert r == -1.0

    def test_no_correlation(self):
        r = _pearson([1, 2, 3, 4, 5], [5, 1, 4, 2, 3])
        assert r is not None
        assert abs(r) < 0.5

    def test_insufficient_data(self):
        assert _pearson([1, 2], [3, 4]) is None

    def test_nan_in_data(self):
        assert _pearson([1, float("nan"), 3], [4, 5, 6]) is None

    def test_constant_x(self):
        """Constant x values = zero variance, should return None."""
        assert _pearson([5, 5, 5], [1, 2, 3]) is None


class TestPearsonWithP:
    def test_strong_correlation_low_p(self):
        r, p = _pearson_with_p([1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                               [2, 4, 6, 8, 10, 12, 14, 16, 18, 20])
        assert r == 1.0
        assert p == 0.0

    def test_weak_correlation_high_p(self):
        r, p = _pearson_with_p([1, 2, 3, 4, 5], [5, 1, 4, 2, 3])
        assert r is not None
        assert p is not None
        assert p > 0.1  # not significant

    def test_insufficient_data(self):
        r, p = _pearson_with_p([1, 2], [3, 4])
        assert r is None
        assert p is None


class TestRankTransform:
    def test_simple_ranking(self):
        ranks = _rank_transform([30, 10, 20])
        assert ranks == [3.0, 1.0, 2.0]

    def test_ties(self):
        ranks = _rank_transform([10, 20, 20, 30])
        assert ranks[0] == 1.0
        assert ranks[1] == 2.5  # tied
        assert ranks[2] == 2.5  # tied
        assert ranks[3] == 4.0

    def test_empty_list(self):
        assert _rank_transform([]) == []

    def test_single_value(self):
        assert _rank_transform([42]) == [1.0]


class TestSpearman:
    def test_monotonic_increase(self):
        rho, p = _spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50])
        assert rho is not None
        assert abs(rho - 1.0) < 0.01

    def test_monotonic_decrease(self):
        rho, p = _spearman([1, 2, 3, 4, 5], [50, 40, 30, 20, 10])
        assert rho is not None
        assert abs(rho + 1.0) < 0.01

    def test_insufficient_data(self):
        rho, p = _spearman([1, 2], [3, 4])
        assert rho is None


class TestCorrelate:
    def test_small_n_uses_spearman(self):
        """For n < 8, should use Spearman (rank-based)."""
        r, p = _correlate([1, 2, 3, 4, 5], [10, 20, 30, 40, 50])
        assert r is not None
        assert abs(r - 1.0) < 0.01

    def test_large_n_uses_pearson(self):
        """For n >= 8, should use Pearson."""
        xs = list(range(1, 11))
        ys = [x * 2 + 1 for x in xs]
        r, p = _correlate(xs, ys)
        assert r is not None
        assert abs(r - 1.0) < 0.01


# ── Join Registry ────────────────────────────────────────────────────────────

class TestJoinRegistry:
    def setup_method(self):
        self.jr = JoinRegistry()
        self.long_videos = [
            {"youtube_id": "abc123", "topic": "Fall of Rome"},
            {"youtube_id": "def456", "topic": "Viking Invasion"},
        ]

    def test_join_by_youtube_id(self):
        short = {"pipeline_state": {"parent_youtube_id": "abc123", "parent_topic": "Fall of Rome"}}
        result = self.jr.pair(short, self.long_videos)
        assert result is not None
        assert result["join_method"] == "youtube_id"
        assert result["long"]["youtube_id"] == "abc123"

    def test_join_by_topic_exact(self):
        short = {"pipeline_state": {"parent_youtube_id": "", "parent_topic": "Viking Invasion"}}
        result = self.jr.pair(short, self.long_videos)
        assert result is not None
        assert result["join_method"] == "topic_exact"

    def test_no_substring_match(self):
        """Substring matching must NOT be used — Fix 174."""
        short = {"pipeline_state": {"parent_youtube_id": "", "parent_topic": "Viking"}}
        result = self.jr.pair(short, self.long_videos)
        assert result is None  # "Viking" != "Viking Invasion"

    def test_no_match(self):
        short = {"pipeline_state": {"parent_youtube_id": "zzz", "parent_topic": "Unknown Topic"}}
        result = self.jr.pair(short, self.long_videos)
        assert result is None

    def test_case_insensitive_topic(self):
        short = {"pipeline_state": {"parent_youtube_id": "", "parent_topic": "fall of rome"}}
        result = self.jr.pair(short, self.long_videos)
        assert result is not None

    def test_pair_all(self):
        shorts = [
            {"pipeline_state": {"parent_youtube_id": "abc123"}},
            {"pipeline_state": {"parent_youtube_id": "def456"}},
            {"pipeline_state": {"parent_youtube_id": "missing"}},
        ]
        pairs = self.jr.pair_all(shorts, self.long_videos)
        assert len(pairs) == 2


# ── Layer 3: Topic Health ────────────────────────────────────────────────────

class TestTopicHealth:
    def test_insufficient_topics(self):
        """With only 1 topic, returns insufficient_data."""
        videos = [
            {"topic": "Rome", "views": 1000, "avg_retention_pct": 45},
            {"topic": "Rome", "views": 2000, "avg_retention_pct": 50},
        ]
        result = _compute_topic_health([], videos, JoinRegistry())
        assert result["status"] == "insufficient_data"
        assert result["results"]["topic_ranking"] is not None

    def test_sufficient_topics(self):
        """With 2+ topics having 2+ videos each, returns active."""
        videos = [
            {"topic": "Rome", "views": 1000, "avg_retention_pct": 45},
            {"topic": "Rome", "views": 2000, "avg_retention_pct": 50},
            {"topic": "Vikings", "views": 3000, "avg_retention_pct": 55},
            {"topic": "Vikings", "views": 4000, "avg_retention_pct": 60},
        ]
        result = _compute_topic_health([], videos, JoinRegistry())
        assert result["status"] == "active"
        assert result["results"]["viable_topic_count"] == 2
        # Vikings should rank higher (more views)
        ranking = result["results"]["topic_ranking"]
        assert ranking[0]["topic"] == "Vikings"

    def test_short_pairing(self):
        """Shorts are paired to topics via JoinRegistry."""
        videos = [
            {"topic": "Rome", "youtube_id": "r1", "views": 1000},
            {"topic": "Rome", "youtube_id": "r2", "views": 2000},
            {"topic": "Vikings", "youtube_id": "v1", "views": 3000},
            {"topic": "Vikings", "youtube_id": "v2", "views": 4000},
        ]
        shorts = [
            {"pipeline_state": {"parent_youtube_id": "r1"}, "views": 50000},
            {"pipeline_state": {"parent_youtube_id": "v1"}, "views": 80000},
        ]
        result = _compute_topic_health(shorts, videos, JoinRegistry())
        assert result["status"] == "active"
        rome = next(t for t in result["results"]["topic_ranking"] if t["topic"] == "Rome")
        assert rome["short_count"] == 1
        assert rome["avg_short_views"] == 50000

    def test_empty_data(self):
        result = _compute_topic_health([], [], JoinRegistry())
        assert result["status"] == "insufficient_data"


# ── Correlation Engine ───────────────────────────────────────────────────────

class TestCorrelationEngine:
    def test_phase_a_stubs(self):
        """In Phase A, most layers are inactive stubs."""
        engine = CorrelationEngine()
        result = engine.run([], [], [])
        assert result["maturity"] == "early"
        assert result["layers"]["1"]["status"] == "inactive"
        assert result["layers"]["2"]["status"] == "inactive"
        assert result["layers"]["4"]["status"] == "inactive"
        assert result["layers"]["5"]["status"] == "inactive"
        assert result["layers"]["6"]["status"] == "inactive"
        assert result["layers"]["7"]["status"] == "inactive"
        assert result["recommendations"] == []

    def test_maturity_scales_with_videos(self):
        videos = [{"topic": f"t{i}", "views": 100} for i in range(15)]
        engine = CorrelationEngine()
        result = engine.run(videos, [], [])
        assert result["maturity"] == "established"

    def test_layer_3_active_with_data(self):
        videos = [
            {"topic": "Rome", "views": 1000, "avg_retention_pct": 45},
            {"topic": "Rome", "views": 2000, "avg_retention_pct": 50},
            {"topic": "Vikings", "views": 3000, "avg_retention_pct": 55},
            {"topic": "Vikings", "views": 4000, "avg_retention_pct": 60},
        ]
        engine = CorrelationEngine()
        result = engine.run(videos, [], [])
        assert result["layers"]["3"]["status"] == "active"
        assert result["active_layer_count"] == 1

    def test_generated_at_present(self):
        engine = CorrelationEngine()
        result = engine.run([], [], [])
        assert "generated_at" in result

    def test_all_stubs_have_consistent_schema(self):
        engine = CorrelationEngine()
        result = engine.run([], [], [])
        for layer_id, layer in result["layers"].items():
            assert "status" in layer
            assert "layer" in layer
            assert "reason" in layer
            assert "confidence" in layer
            assert "results" in layer or layer["status"] == "inactive"


# ── Quality Assessment (Phase A simplified) ──────────────────────────────────

class TestQualitySmallPerfectCorrelation:
    def test_pearson_five_perfect_points(self):
        """5 perfectly correlated points — Pearson = 1.0 but sample_sufficiency low."""
        xs = [1, 2, 3, 4, 5]
        ys = [10, 20, 30, 40, 50]
        r = _pearson(xs, ys)
        assert r == 1.0
        # With only 5 points, sample_sufficiency = 5/15 = 0.33
        # This should prevent high-confidence recommendations (tested in Phase B)
