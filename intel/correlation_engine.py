"""
7-layer DAG correlation engine for parameter tuning.

Architecture:
  Layer 1: LF Param → LF Metrics (Phase B — stub)
  Layer 2: Short Param → Short Metrics (Phase B — stub)
  Layer 3: Topic Health (Phase A — partial: raw metrics only)
  Layer 4: Audience Transformation (Phase B — stub)
  Layer 5: Short Prod → Parent Lift (Phase B/C — stub)
  Layer 6: Era Stratification (Phase C — stub)
  Layer 7: Cross-Format Signal Transfer (Phase C — stub)

The engine is a PURE FUNCTION — no file I/O. Called by the analytics agent,
which writes results to outputs/correlation_results.json.
"""

import math
from datetime import datetime, timezone


# ── Metric families for BH/FDR multiple comparisons correction ──────────────

METRIC_FAMILIES = {
    "engagement": ["avg_view_percentage", "avg_view_duration_seconds", "replay_rate"],
    "retention": ["hook_retention_30s", "midpoint_retention", "end_retention"],
    "reach": ["views", "impressions", "ctr_pct"],
    "conversion": ["subscribers_gained", "engagement_rate"],
}


# ── Statistical functions ────────────────────────────────────────────────────

def _safe_float(val) -> float | None:
    """Return val as float if finite, else None."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _coefficient_of_variation(values: list[float]) -> float:
    """CV = stdev / |mean|. Returns 0 if mean near zero or < 2 values."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    if abs(mean) < 1e-9:
        return 0.0
    stdev = (sum((v - mean) ** 2 for v in values) / n) ** 0.5
    return stdev / abs(mean)


def _pearson(xs: list, ys: list) -> float | None:
    """Pearson correlation. Returns None if < 3 data points or NaN present."""
    n = len(xs)
    if n < 3:
        return None
    if any(math.isnan(v) or math.isinf(v) for v in xs + ys):
        return None
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    denom = den_x * den_y
    if denom < 1e-9:
        return None
    return round(num / denom, 4)


def _pearson_with_p(xs: list, ys: list) -> tuple[float | None, float | None]:
    """Pearson r with approximate two-tailed p-value via t-distribution.
    Returns (r, p) or (None, None) if insufficient data."""
    r = _pearson(xs, ys)
    if r is None:
        return None, None
    n = len(xs)
    if abs(r) >= 1.0:
        return r, 0.0
    t_stat = r * math.sqrt((n - 2) / (1 - r * r))
    p = _t_distribution_p(abs(t_stat), n - 2) * 2  # two-tailed
    return r, round(min(p, 1.0), 6)


def _t_distribution_p(t: float, df: int) -> float:
    """Approximate one-tailed p-value for t-distribution.
    Uses normal approximation with df correction. Accuracy: ±5% for df>=5."""
    if t <= 0:
        return 0.5
    z = t * (1 - 1 / (4 * df)) / math.sqrt(1 + t * t / (2 * df))
    return 0.5 * math.erfc(z / math.sqrt(2))


def _rank_transform(values: list) -> list[float]:
    """Convert values to ranks (1-based), averaging ties."""
    if not values:
        return []
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and indexed[j + 1][1] == indexed[j][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: list, ys: list) -> tuple[float | None, float | None]:
    """Spearman rank correlation. More robust for small n and non-linear.
    Returns (rho, p) or (None, None)."""
    n = len(xs)
    if n < 3:
        return None, None
    rx = _rank_transform(xs)
    ry = _rank_transform(ys)
    return _pearson_with_p(rx, ry)


def _correlate(xs: list, ys: list) -> tuple[float | None, float | None]:
    """Choose correlation method based on sample size.
    Spearman for n < 8 (more robust), Pearson for n >= 8 (more powerful)."""
    if len(xs) < 8:
        return _spearman(xs, ys)
    return _pearson_with_p(xs, ys)


def _benjamini_hochberg(p_values: list[tuple[str, float]], q: float = 0.10) -> list[str]:
    """Benjamini-Hochberg FDR correction.
    Input: list of (test_name, p_value). Returns test_names significant after correction."""
    if not p_values:
        return []
    sorted_pv = sorted(p_values, key=lambda x: x[1])
    m = len(sorted_pv)
    last_significant_k = -1
    for k, (name, p) in enumerate(sorted_pv, 1):
        threshold = (k / m) * q
        if p <= threshold:
            last_significant_k = k
    if last_significant_k > 0:
        return [name for name, p in sorted_pv[:last_significant_k]]
    return []


# ── Join Registry ────────────────────────────────────────────────────────────

class JoinRegistry:
    """Resolves short-to-long pairings with priority chain.
    No substring matching — false positives are worse than missed pairs."""

    def pair(self, short: dict, long_videos: list[dict]) -> dict | None:
        """Find the parent long-form video for a short.
        Priority: parent_youtube_id exact > parent_topic exact."""
        ps = short.get("pipeline_state") or {}

        # Priority 1: parent_youtube_id (exact, reliable)
        parent_id = ps.get("parent_youtube_id")
        if parent_id:
            match = next((v for v in long_videos if v.get("youtube_id") == parent_id), None)
            if match:
                return {"short": short, "long": match, "join_method": "youtube_id"}

        # Priority 2: parent_topic exact match
        topic = (ps.get("parent_topic") or "").strip().lower()
        if topic:
            match = next(
                (v for v in long_videos if (v.get("topic") or "").strip().lower() == topic),
                None,
            )
            if match:
                return {"short": short, "long": match, "join_method": "topic_exact"}

        return None

    def pair_all(self, shorts: list[dict], long_videos: list[dict]) -> list[dict]:
        """Pair all shorts with their parent long-form videos."""
        pairs = []
        for short in shorts:
            result = self.pair(short, long_videos)
            if result:
                pairs.append(result)
        return pairs


# ── Layer base ───────────────────────────────────────────────────────────────

def _layer_envelope(layer_id: int, status: str, reason: str,
                    confidence: float = 0.0, results: dict | None = None,
                    tests_run: int = 0, tests_significant: int = 0) -> dict:
    """Consistent envelope for all layer outputs."""
    return {
        "status": status,
        "layer": layer_id,
        "reason": reason,
        "confidence": confidence,
        "results": results,
        "tests_run": tests_run,
        "tests_significant": tests_significant,
    }


# ── Layer 3: Topic Health (partially active in Phase A) ──────────────────────

def _compute_topic_health(shorts: list, long_videos: list,
                          join_registry: JoinRegistry) -> dict:
    """Per-topic raw metrics. No composite score until n >= 10 per topic.
    Requires >= 2 topics with >= 2 videos each to produce comparisons."""
    pairs = join_registry.pair_all(shorts, long_videos)

    # Group by topic
    by_topic: dict[str, dict] = {}
    for lv in long_videos:
        topic = (lv.get("topic") or "unknown").strip()
        if topic not in by_topic:
            by_topic[topic] = {"long_videos": [], "shorts": [], "metrics": {}}
        by_topic[topic]["long_videos"].append(lv)

    for pair in pairs:
        topic = (pair["long"].get("topic") or "unknown").strip()
        if topic in by_topic:
            by_topic[topic]["shorts"].append(pair["short"])

    # Compute per-topic metrics
    topic_ranking = []
    for topic, data in by_topic.items():
        long_views = [_safe_float(v.get("views")) for v in data["long_videos"]]
        long_views = [v for v in long_views if v is not None]
        long_retention = [_safe_float(v.get("avg_retention_pct")) for v in data["long_videos"]]
        long_retention = [v for v in long_retention if v is not None]
        long_subs = [_safe_float(v.get("subscribers_gained")) for v in data["long_videos"]]
        long_subs = [v for v in long_subs if v is not None]
        short_views = [_safe_float(s.get("views")) for s in data["shorts"]]
        short_views = [v for v in short_views if v is not None]

        topic_ranking.append({
            "topic": topic,
            "long_count": len(data["long_videos"]),
            "short_count": len(data["shorts"]),
            "avg_long_views": round(sum(long_views) / len(long_views), 1) if long_views else None,
            "avg_long_retention": round(sum(long_retention) / len(long_retention), 2) if long_retention else None,
            "avg_long_subs": round(sum(long_subs) / len(long_subs), 1) if long_subs else None,
            "avg_short_views": round(sum(short_views) / len(short_views), 1) if short_views else None,
        })

    # Check activation: need >= 2 topics with >= 2 videos each
    viable_topics = [t for t in topic_ranking if t["long_count"] >= 2]
    if len(viable_topics) < 2:
        return _layer_envelope(
            3, "insufficient_data",
            f"Need 2+ topics with 2+ videos each. Have {len(viable_topics)} viable topic(s).",
            results={"topic_ranking": sorted(topic_ranking, key=lambda t: t["long_count"], reverse=True)},
        )

    return _layer_envelope(
        3, "active",
        f"Raw per-topic metrics for {len(viable_topics)} topics.",
        confidence=0.0,  # No composite score in Phase A
        results={
            "topic_ranking": sorted(topic_ranking, key=lambda t: t["avg_long_views"] or 0, reverse=True),
            "viable_topic_count": len(viable_topics),
        },
    )


# ── Correlation Engine ───────────────────────────────────────────────────────

class CorrelationEngine:
    """7-layer DAG correlation engine. Called by analytics agent.
    Pure function — returns dict, does NO file I/O."""

    def __init__(self):
        self.join_registry = JoinRegistry()

    def run(self, videos: list, shorts: list, analytics_rows: list,
            youtube_analytics=None) -> dict:
        """Run all correlation layers. Returns full results dict.

        Args:
            videos: Long-form video records (from Supabase per_video_stats)
            shorts: Short video records
            analytics_rows: Raw YouTube analytics rows
            youtube_analytics: YouTube Analytics API handle (optional, for Layer 4 Phase B)
        """
        # Phase A: Independent layers
        l3 = _compute_topic_health(shorts, videos, self.join_registry)

        # Phase A stubs
        l1 = _layer_envelope(1, "inactive", "Requires param variation from manual overrides (Phase B)")
        l2 = _layer_envelope(2, "inactive", "Requires param variation from manual overrides (Phase B)")
        l4 = _layer_envelope(4, "inactive", "Requires youtube_analytics handle and ≥3 paired topics (Phase B)")
        l5 = _layer_envelope(5, "inactive", "Requires Layers 2+4 at moderate confidence (Phase B/C)")
        l6 = _layer_envelope(6, "inactive", "Requires ≥5 videos per era with varied params (Phase C)")
        l7 = _layer_envelope(7, "inactive", "Requires Layers 1+2 at moderate confidence (Phase C)")

        layers = {"1": l1, "2": l2, "3": l3, "4": l4, "5": l5, "6": l6, "7": l7}

        return self._synthesize(layers, videos, shorts)

    def _synthesize(self, layers: dict, videos: list, shorts: list) -> dict:
        """Merge layer outputs into final results."""
        active_layers = {k: v for k, v in layers.items() if v["status"] == "active"}

        # Maturity assessment
        n_videos = len(videos)
        n_shorts = len(shorts)
        if n_videos < 3:
            maturity = "early"
            maturity_desc = f"Only {n_videos} video(s). Collecting data — manual overrides only."
        elif n_videos < 10:
            maturity = "emerging"
            maturity_desc = f"{n_videos} videos. Some topic patterns emerging."
        elif n_videos < 20:
            maturity = "established"
            maturity_desc = f"{n_videos} videos. Topic health analysis active."
        else:
            maturity = "mature"
            maturity_desc = f"{n_videos} videos. Full correlation analysis available."

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "maturity": maturity,
            "maturity_description": maturity_desc,
            "video_count": n_videos,
            "short_count": n_shorts,
            "layers": layers,
            "active_layer_count": len(active_layers),
            "recommendations": [],  # Phase B — no recommendations yet
        }
