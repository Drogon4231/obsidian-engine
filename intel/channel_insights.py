"""
channel_insights.py — Intelligence hub for The Obsidian Archive pipeline.

Reads channel_insights.json (written by 12_analytics_agent.py) and formats
data-backed intelligence for injection into agent prompts.

All functions are READ-ONLY. Never write to channel_insights.json from here.
Returns empty strings when data is unavailable — agents degrade gracefully.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

INSIGHTS_FILE = Path(__file__).resolve().parent.parent / "channel_insights.json"
_MAX_AGE_HOURS = 72  # insights older than this are flagged as stale
_MATURITY_THRESHOLD = 15  # videos needed before own data is trusted fully


def load_insights() -> dict:
    """Load channel_insights.json. Returns {} if missing or corrupt."""
    if not INSIGHTS_FILE.exists():
        return {}
    try:
        return json.loads(INSIGHTS_FILE.read_text())
    except Exception:
        return {}


def get_confidence_level() -> str:
    """Returns 'none', 'low', or 'sufficient'."""
    return load_insights().get("data_quality", {}).get("confidence_level", "none")


def is_insights_fresh(max_age_hours: int = _MAX_AGE_HOURS) -> bool:
    insights = load_insights()
    ts_str = insights.get("generated_at", "")
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        return age.total_seconds() < max_age_hours * 3600
    except Exception:
        return False


def _truncate(text: str, max_words: int = 250) -> str:
    words = str(text).split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [...]"


def _get_video_count(insights: dict) -> int:
    """Return the number of videos analyzed."""
    return insights.get("data_quality", {}).get("videos_analyzed", 0)


def _get_base_knowledge_note(video_count: int) -> str:
    """Return a note about base knowledge blending when video count is low."""
    if video_count == 0:
        return "(Using YouTube base knowledge — no own data yet)"
    ratio = min(video_count / _MATURITY_THRESHOLD, 1.0)
    pct = int(ratio * 100)
    return f"(Blending base knowledge with own data — {pct}% own data weight, {video_count} videos)"


# ── Base knowledge helpers ────────────────────────────────────────────────────

def _blend_base_seo(lines: list, video_count: int) -> None:
    """Prepend base SEO knowledge if video count is below maturity threshold."""
    try:
        from intel.youtube_knowledge_base import get_base_seo_intel
        if video_count < _MATURITY_THRESHOLD:
            base_intel = get_base_seo_intel()
            if base_intel:
                lines.append(f"\nBASE KNOWLEDGE {_get_base_knowledge_note(video_count)}:")
                lines.append(base_intel)
    except ImportError:
        pass
    except Exception:
        pass


def _blend_base_topic(lines: list, video_count: int) -> None:
    """Prepend base topic discovery knowledge if below threshold."""
    try:
        from intel.youtube_knowledge_base import get_base_topic_discovery_intel
        if video_count < _MATURITY_THRESHOLD:
            base_intel = get_base_topic_discovery_intel()
            if base_intel:
                lines.append(f"\nBASE KNOWLEDGE {_get_base_knowledge_note(video_count)}:")
                lines.append(base_intel)
    except ImportError:
        pass
    except Exception:
        pass


def _blend_base_narrative(lines: list, video_count: int) -> None:
    """Prepend base narrative knowledge if below threshold."""
    try:
        from intel.youtube_knowledge_base import get_base_narrative_intel
        if video_count < _MATURITY_THRESHOLD:
            base_intel = get_base_narrative_intel()
            if base_intel:
                lines.append(f"\nBASE KNOWLEDGE {_get_base_knowledge_note(video_count)}:")
                lines.append(base_intel)
    except ImportError:
        pass
    except Exception:
        pass


def _blend_base_script(lines: list, video_count: int) -> None:
    """Prepend base script writing knowledge if below threshold."""
    try:
        from intel.youtube_knowledge_base import get_base_script_intel
        if video_count < _MATURITY_THRESHOLD:
            base_intel = get_base_script_intel()
            if base_intel:
                lines.append(f"\nBASE KNOWLEDGE {_get_base_knowledge_note(video_count)}:")
                lines.append(base_intel)
    except ImportError:
        pass
    except Exception:
        pass


def _blend_base_retention(lines: list, video_count: int) -> None:
    """Prepend base retention knowledge if below threshold."""
    try:
        from intel.youtube_knowledge_base import get_base_retention_intel
        if video_count < _MATURITY_THRESHOLD:
            base_intel = get_base_retention_intel()
            if base_intel:
                lines.append(f"\nBASE KNOWLEDGE {_get_base_knowledge_note(video_count)}:")
                lines.append(base_intel)
    except ImportError:
        pass
    except Exception:
        pass


def _blend_base_content_quality(lines: list, video_count: int) -> None:
    """Prepend base content quality knowledge if below threshold."""
    try:
        from intel.youtube_knowledge_base import get_base_content_quality_intel
        if video_count < _MATURITY_THRESHOLD:
            base_intel = get_base_content_quality_intel()
            if base_intel:
                lines.append(f"\nBASE KNOWLEDGE {_get_base_knowledge_note(video_count)}:")
                lines.append(base_intel)
    except ImportError:
        pass
    except Exception:
        pass


# ── Global intelligence block ─────────────────────────────────────────────────

def get_global_intelligence_block() -> str:
    """
    Concise intelligence block for injection into ANY agent's system prompt.
    Returns '' if confidence is 'none'. Targets ~300 words.
    """
    insights = load_insights()
    confidence = insights.get("data_quality", {}).get("confidence_level", "none")
    if confidence == "none":
        return ""

    n        = insights.get("data_quality", {}).get("videos_analyzed", 0)
    health   = insights.get("channel_health", {})
    era_perf = insights.get("era_performance", {})
    dna_conf = insights.get("dna_confidence_updates", {})
    ret      = insights.get("retention_analysis", {})

    stale_note = "" if is_insights_fresh() else " (NOTE: data is over 72 hours old)"
    prefix = f"Based on {n} published videos{stale_note}."
    if confidence == "low":
        prefix = f"EARLY DATA ({n} videos — treat as directional, not definitive)."

    lines = [
        "=== CHANNEL PERFORMANCE INTELLIGENCE ===",
        prefix,
        "",
    ]

    # What's working
    working = []
    if era_perf:
        best = max(era_perf, key=lambda e: era_perf[e].get("avg_views", 0))
        be   = era_perf[best]
        if be.get("video_count", 0) >= 1:
            working.append(
                f"{best.replace('_', ' ').title()} content averages "
                f"{int(be.get('avg_views',0)):,} views / {be.get('avg_ctr',0):.1f}% CTR"
                f" (channel avg: {int(health.get('avg_views_per_video',0)):,} / {health.get('avg_ctr_pct',0):.1f}%)"
            )
    title_patterns = insights.get("title_pattern_analysis", {})
    if title_patterns.get("high_ctr_patterns"):
        working.append(f"High-CTR title patterns: {title_patterns['high_ctr_patterns'][0]}")
    if ret.get("retention_verdict") == "shorter_wins" and ret.get("optimal_length_minutes"):
        working.append(f"Optimal length: ~{ret['optimal_length_minutes']:.0f} min ({ret.get('retention_note','')})")

    if working:
        lines.append("WHAT'S WORKING:")
        for w in working:
            lines.append(f"- {w}")
        lines.append("")

    # What's not working
    not_working = []
    if era_perf:
        eras_sorted = sorted(era_perf.items(), key=lambda x: x[1].get("avg_views", 0))
        worst = eras_sorted[0]
        we    = worst[1]
        if we.get("video_count", 0) >= 2:
            not_working.append(
                f"{worst[0].replace('_', ' ').title()} topics average "
                f"{int(we.get('avg_views',0)):,} views — below channel average"
            )
    if title_patterns.get("low_ctr_patterns"):
        not_working.append(f"Low-CTR title patterns: {title_patterns['low_ctr_patterns'][0]}")
    if ret.get("retention_verdict") == "shorter_wins":
        band = insights.get("retention_analysis", {}).get("retention_by_length_band", {})
        over = band.get("over_16min", {})
        if over.get("avg_retention") is not None:
            not_working.append(f"Videos over 16 min retain only {over['avg_retention']:.0f}% avg viewers")

    if not_working:
        lines.append("WHAT'S NOT WORKING:")
        for w in not_working:
            lines.append(f"- {w}")
        lines.append("")

    # DNA confidence (data-backed scores)
    if dna_conf:
        lines.append("DNA CONFIDENCE (data-backed):")
        labels = {
            "open_mid_action_hook":      "Open mid-action hook",
            "twist_reveal_ending":       "Twist reveal ending",
            "ancient_medieval_priority": "Ancient/Medieval priority",
            "10_15_min_standard_length": "10–15 min standard length",
            "present_tense_narration":   "Present tense narration",
            "dark_thumbnail_aesthetic":  "Dark thumbnail aesthetic",
        }
        for key, label in labels.items():
            score = dna_conf.get(key)
            if score is not None:
                pct = int(score * 100)
                flag = "VALIDATED" if score >= 0.7 else ("WEAKENING" if score < 0.4 else "neutral")
                lines.append(f"- {label}: {pct}% — {flag}")
        lines.append("")

    lines.append("=========================================")
    return _truncate("\n".join(lines), max_words=350)


# ── Agent-specific intelligence: Topic Discovery (Agent 00) ───────────────────

def get_topic_discovery_intelligence() -> str:
    """Targeted intelligence for Agent 00 (Topic Discovery)."""
    insights = load_insights()
    if insights.get("data_quality", {}).get("confidence_level", "none") == "none":
        return ""
    video_count = _get_video_count(insights)
    intel = insights.get("agent_intelligence", {}).get("topic_discovery", "")
    if not intel:
        return ""
    era_perf = insights.get("era_performance", {})
    lines = ["PERFORMANCE DATA FOR TOPIC SELECTION:"]

    # Base knowledge blending
    _blend_base_topic(lines, video_count)

    lines.append(intel)
    if era_perf:
        lines.append("\nERA RANKINGS BY AVG VIEWS:")
        for era, data in sorted(era_perf.items(), key=lambda x: x[1].get("avg_views", 0), reverse=True):
            if data.get("video_count", 0) >= 1:
                lines.append(
                    f"  {era.replace('_',' ').title()}: "
                    f"{int(data['avg_views']):,} avg views, "
                    f"{data.get('avg_ctr',0):.1f}% CTR "
                    f"({data['video_count']} video{'s' if data['video_count']!=1 else ''})"
                )
    # Shorts-informed signals
    shorts = insights.get("shorts_intelligence", {})
    shorts_era = shorts.get("era_performance", {})
    if shorts_era:
        lines.append("\nSHORTS ERA PERFORMANCE (subscriber generation):")
        for era, data in sorted(shorts_era.items(),
                                 key=lambda x: x[1].get("total_subs", 0), reverse=True):
            if data.get("short_count", 0) >= 1:
                lines.append(
                    f"  {era.replace('_', ' ').title()}: "
                    f"{data['total_subs']} subs from {data['short_count']} shorts "
                    f"({data.get('sub_conversion_rate', 0):.3f}% conversion)"
                )

    correlation = insights.get("shorts_long_correlation", {})
    if correlation and correlation.get("topics_with_shorts", 0) > 0:
        lift = correlation.get("view_lift_pct", 0)
        lines.append(f"\nSHORTS BOOST: Topics with a matching short get {lift:+.1f}% more long-form views "
                     f"({correlation.get('sample_size_note', '')})")

    # Traffic source insight
    traffic = insights.get("traffic_sources", {})
    if traffic:
        search_pct = traffic.get("search", {}).get("pct", 0)
        browse_pct = traffic.get("browse", {}).get("pct", 0)
        if search_pct > browse_pct:
            lines.append(f"\nTRAFFIC INSIGHT: Channel is search-dependent ({search_pct:.0f}% search vs {browse_pct:.0f}% browse) "
                         "— prioritize topics with strong search demand")
        elif browse_pct > 0:
            lines.append(f"\nTRAFFIC INSIGHT: Channel is browse-driven ({browse_pct:.0f}% browse vs {search_pct:.0f}% search) "
                         "— prioritize topics with strong curiosity hooks")

    # Audience demographics hint
    demographics = insights.get("audience_demographics", {})
    top_countries = demographics.get("top_countries", [])
    if top_countries:
        country_str = ", ".join(
            f"{c.get('country', '?')} ({c.get('pct', 0):.0f}%)"
            for c in top_countries[:3]
        )
        lines.append(f"\nAUDIENCE GEO: Top regions: {country_str} — consider topics that resonate with these audiences")

    # Content pattern winners
    try:
        content_patterns = _get_content_pattern_summary(insights)
        if content_patterns:
            lines.append(f"\nCONTENT PATTERNS: {content_patterns}")
    except Exception:
        pass

    # Comment sentiment intelligence
    sentiment_intel = get_comment_sentiment_intelligence()
    if sentiment_intel:
        lines.append(f"\n{sentiment_intel}")

    return _truncate("\n".join(lines), max_words=500)


def get_comment_sentiment_intelligence() -> str:
    """Format comment sentiment data for prompt injection.

    Surfaces high-engagement topics, debate topics, content opportunities,
    and recurring criticism from audience comments.
    """
    insights = load_insights()
    sentiment = insights.get("comment_sentiment", {})
    if not sentiment:
        return ""

    lines = []

    # Engagement signals — topics that drive passionate discussion
    engagement = sentiment.get("engagement_signals", {})
    high_topics = engagement.get("high_engagement_topics", [])
    if high_topics:
        lines.append("HIGH-ENGAGEMENT TOPICS (drive the most discussion):")
        for t in high_topics[:5]:
            lines.append(f"  - {t}")

    debate_topics = engagement.get("debate_topics", [])
    if debate_topics:
        lines.append("DEBATE TOPICS (viewers disagree — drives watch time):")
        for t in debate_topics[:3]:
            lines.append(f"  - {t}")

    # Content opportunities from comment patterns
    opportunities = sentiment.get("content_opportunities", [])
    if opportunities:
        lines.append("CONTENT OPPORTUNITIES (derived from comment patterns):")
        for o in opportunities[:3]:
            lines.append(f"  - {o}")

    # Recurring criticism — avoid these pitfalls
    criticism = sentiment.get("recurring_criticism", [])
    if criticism:
        lines.append("AUDIENCE CRITICISM (avoid these):")
        for c in criticism[:3]:
            lines.append(f"  - {c}")

    return "\n".join(lines) if lines else ""


def get_shorts_intelligence() -> str:
    """Intelligence about shorts performance for agents that generate short content."""
    insights = load_insights()
    shorts = insights.get("shorts_intelligence", {})
    if not shorts or shorts.get("total_shorts", 0) == 0:
        return ""

    lines = [
        "SHORTS PERFORMANCE INTELLIGENCE:",
        f"Total shorts: {shorts.get('total_shorts', 0)} | "
        f"Avg views: {shorts.get('avg_views_per_short', 0):.0f} | "
        f"Total subs: {shorts.get('total_subs_from_shorts', 0)} | "
        f"Conversion: {shorts.get('sub_conversion_rate_pct', 0):.3f}%",
    ]

    era_perf = shorts.get("era_performance", {})
    if era_perf:
        lines.append("\nSHORTS ERA RANKINGS BY SUBS:")
        for era, data in sorted(era_perf.items(),
                                 key=lambda x: x[1].get("total_subs", 0), reverse=True):
            lines.append(
                f"  {era.replace('_', ' ').title()}: "
                f"{data.get('total_subs', 0)} subs from {data.get('short_count', 0)} shorts, "
                f"{data.get('avg_views', 0):.0f} avg views, "
                f"{data.get('sub_conversion_rate', 0):.3f}% conversion"
            )

    top_hooks = shorts.get("top_hooks", [])
    if top_hooks:
        lines.append("\nTOP SHORT HOOKS (by views):")
        for h in top_hooks[:3]:
            lines.append(f"  [{h.get('views', 0):,} views, {h.get('subs', 0)} subs] \"{h.get('hook', '')}\"")


    correlation = insights.get("shorts_long_correlation", {})
    if correlation and correlation.get("topics_with_shorts", 0) > 0:
        lift = correlation.get("view_lift_pct", 0)
        lines.append("\nSHORTS→LONG CORRELATION:")
        lines.append(f"  View lift: {lift:+.1f}% when topic has a matching short")
        lines.append(f"  Sample: {correlation.get('sample_size_note', 'N/A')}")

    return _truncate("\n".join(lines), max_words=300)


# ── Agent-specific intelligence: SEO (Agent 06) ──────────────────────────────

def get_seo_intelligence() -> str:
    """Targeted intelligence for Agent 06 (SEO)."""
    insights = load_insights()
    if insights.get("data_quality", {}).get("confidence_level", "none") == "none":
        return ""
    video_count = _get_video_count(insights)
    intel      = insights.get("agent_intelligence", {}).get("seo_agent", "")
    title_pat  = insights.get("title_pattern_analysis", {})
    tags       = insights.get("tag_performance", {})
    top_videos = insights.get("top_performing_videos", [])

    lines = ["SEO PERFORMANCE INTELLIGENCE:"]

    # Base knowledge blending
    _blend_base_seo(lines, video_count)

    if intel:
        lines.append(intel)
    if title_pat.get("high_ctr_patterns"):
        lines.append("\nHIGH-CTR TITLE PATTERNS:")
        for p in title_pat["high_ctr_patterns"][:3]:
            lines.append(f"  + {p}")
    if title_pat.get("low_ctr_patterns"):
        lines.append("LOW-CTR PATTERNS TO AVOID:")
        for p in title_pat["low_ctr_patterns"][:2]:
            lines.append(f"  - {p}")
    ctr_by_len = {k: v for k, v in title_pat.get("avg_ctr_by_title_length", {}).items()
                  if isinstance(v, (int, float))}
    if ctr_by_len:
        try:
            best_len_key = max(ctr_by_len, key=ctr_by_len.get)
            lines.append(f"\nBEST TITLE LENGTH: {best_len_key.replace('_',' ')} ({ctr_by_len[best_len_key]:.1f}% CTR)")
        except Exception:
            pass
    if title_pat.get("best_opening_words"):
        lines.append(f"STRONG OPENING WORDS: {', '.join(title_pat['best_opening_words'][:4])}")
    if top_videos:
        lines.append("\nTOP PERFORMING TITLES (by CTR):")
        for v in top_videos[:3]:
            lines.append(f"  [{v.get('ctr_pct',0):.1f}% CTR] {v.get('title','')}")
    if tags.get("high_performing_tags"):
        lines.append(f"\nRECOMMENDED TAGS: {', '.join(tags['high_performing_tags'][:8])}")
    if tags.get("recommended_tag_mix"):
        lines.append(f"TAG STRATEGY: {tags['recommended_tag_mix']}")

    # Search terms that drive traffic
    search_intel = insights.get("search_intelligence", {})
    top_terms = search_intel.get("top_search_terms", [])
    if top_terms:
        terms_str = ", ".join(
            t.get("term", "") for t in top_terms[:10] if t.get("term")
        )
        if terms_str:
            lines.append(f"\nTOP SEARCH TERMS DRIVING TRAFFIC: {terms_str}")

    # Engagement metrics insight
    engagement = insights.get("engagement_metrics", {})
    if engagement.get("avg_engagement_rate"):
        lines.append(f"\nENGAGEMENT: {engagement['avg_engagement_rate']:.2f}% avg engagement rate")

    # Title attribute correlation data from content classifier
    try:
        per_video = insights.get("per_video_stats", [])
        title_corr = _get_title_attribute_correlation(per_video)
        if title_corr:
            lines.append(f"\nTITLE ATTRIBUTE INSIGHTS: {title_corr}")
    except Exception:
        pass

    return _truncate("\n".join(lines), max_words=350)


# ── Agent-specific intelligence: Narrative (Agent 03) ─────────────────────────

def get_narrative_intelligence() -> str:
    """Targeted intelligence for Agent 03 (Narrative Architect)."""
    insights = load_insights()
    if insights.get("data_quality", {}).get("confidence_level", "none") == "none":
        return ""
    video_count = _get_video_count(insights)
    intel  = insights.get("agent_intelligence", {}).get("narrative_architect", "")
    ret    = insights.get("retention_analysis", {})
    bands  = ret.get("retention_by_length_band", {})

    lines = ["LENGTH & RETENTION DATA:"]

    # Base knowledge blending
    _blend_base_narrative(lines, video_count)

    if intel:
        lines.append(intel)
    if ret.get("optimal_length_minutes"):
        lines.append(f"\nDATA-BACKED OPTIMAL LENGTH: {ret['optimal_length_minutes']:.0f} minutes")
    if ret.get("retention_note"):
        lines.append(f"RETENTION INSIGHT: {ret['retention_note']}")
    if bands:
        lines.append("\nRETENTION BY VIDEO LENGTH:")
        band_labels = {
            "under_8min": "< 8 min", "8_to_12min": "8-12 min",
            "12_to_16min": "12-16 min", "over_16min": "> 16 min"
        }
        for band, label in band_labels.items():
            d = bands.get(band, {})
            if d.get("sample_count", 0) > 0 and d.get("avg_retention") is not None:
                lines.append(
                    f"  {label}: {d['avg_retention']:.0f}% retention, "
                    f"{int(d.get('avg_views',0) or 0):,} avg views "
                    f"({d['sample_count']} videos)"
                )
    # Concrete examples for the narrative architect
    top_vids = insights.get("top_performing_videos", [])
    if top_vids:
        lines.append("\nBEST RETENTION EXAMPLES (emulate these structures):")
        for v in top_vids[:2]:
            ret_val = v.get('avg_retention_pct') if v.get('avg_retention_pct') is not None else v.get('avg_view_percentage')
            ret_pct = f"{ret_val:.0f}%" if ret_val is not None else '?'
            lines.append(f"  - \"{v.get('title', '?')[:55]}\" -- {ret_pct} retention")

    # Retention curve insights
    curves = insights.get("retention_curves", {})
    if curves:
        hook_ret = curves.get("avg_hook_retention_30s")
        if hook_ret is not None:
            lines.append(f"\nHOOK RETENTION (30s mark): {hook_ret:.0f}% average")
        mid_ret = curves.get("avg_midpoint_retention")
        if mid_ret is not None:
            lines.append(f"MIDPOINT RETENTION: {mid_ret:.0f}%")
        end_ret = curves.get("avg_end_retention")
        if end_ret is not None:
            lines.append(f"END RETENTION: {end_ret:.0f}%")

    # Retention by hook type from content classifier
    try:
        hook_retention = _get_hook_type_retention(insights)
        if hook_retention:
            lines.append(f"\nHOOK TYPE RETENTION: {hook_retention}")
    except Exception:
        pass

    # Pacing correlation
    try:
        pacing_corr = _get_pacing_correlation(insights)
        if pacing_corr:
            lines.append(f"\nPACING INSIGHT: {pacing_corr}")
    except Exception:
        pass

    return _truncate("\n".join(lines), max_words=350)


# ── Agent-specific intelligence: Script Writer (Agent 04) ─────────────────────

def get_script_intelligence() -> str:
    """Targeted intelligence for Agent 04 (Script Writer)."""
    insights = load_insights()
    if insights.get("data_quality", {}).get("confidence_level", "none") == "none":
        return ""
    video_count = _get_video_count(insights)
    intel   = insights.get("agent_intelligence", {}).get("script_writer", "")
    exp_rec = insights.get("experiment_recommendations", [])
    top_vids = insights.get("top_performing_videos", [])
    bottom_vids = insights.get("bottom_performing_videos", [])

    lines = ["SCRIPT PERFORMANCE INTELLIGENCE:"]

    # Base knowledge blending
    _blend_base_script(lines, video_count)

    if intel:
        lines.append(intel)
    # Concrete examples of what worked vs what didn't
    if top_vids:
        lines.append("\nTOP PERFORMING VIDEOS (study these hooks & pacing):")
        for v in top_vids[:3]:
            ret_val = v.get('avg_retention_pct') if v.get('avg_retention_pct') is not None else v.get('avg_view_percentage')
            ret = f"{ret_val:.0f}% retention" if ret_val is not None else ''
            views = f"{int(v.get('views', 0)):,} views" if v.get('views') else ''
            lines.append(f"  - \"{v.get('title', '?')[:60]}\" -- {views}, {ret}")
    if bottom_vids:
        lines.append("\nWEAK PERFORMERS (avoid these patterns):")
        for v in bottom_vids[:2]:
            ret_val = v.get('avg_retention_pct') if v.get('avg_retention_pct') is not None else v.get('avg_view_percentage')
            ret = f"{ret_val:.0f}% retention" if ret_val is not None else ''
            views = f"{int(v.get('views', 0)):,} views" if v.get('views') else ''
            lines.append(f"  - \"{v.get('title', '?')[:60]}\" -- {views}, {ret}")
    if exp_rec:
        lines.append(f"\nEXPERIMENT TO TRY: {exp_rec[0]}")

    # Hook type ranking by retention
    try:
        hook_ranking = _get_hook_type_retention(insights)
        if hook_ranking:
            lines.append(f"\nHOOK TYPE RANKING: {hook_ranking}")
    except Exception:
        pass

    # Pacing analysis summary
    try:
        pacing = _get_pacing_correlation(insights)
        if pacing:
            lines.append(f"\nPACING DATA: {pacing}")
    except Exception:
        pass

    # Engagement correlation
    engagement = insights.get("engagement_metrics", {})
    if engagement.get("avg_engagement_rate"):
        lines.append(f"\nENGAGEMENT RATE: {engagement['avg_engagement_rate']:.2f}% avg")
        like_ratio = engagement.get("avg_like_ratio")
        if like_ratio:
            lines.append(f"AVG LIKE RATIO: {like_ratio:.2f}%")

    return _truncate("\n".join(lines), max_words=400)


# ── New intelligence functions ────────────────────────────────────────────────

def get_traffic_intelligence() -> str:
    """Format traffic source data for agents."""
    try:
        insights = load_insights()
        traffic = insights.get("traffic_sources", {})
        if not traffic:
            return ""

        lines = ["TRAFFIC SOURCE INTELLIGENCE:"]

        # Channel traffic mix
        browse_pct = traffic.get("browse", {}).get("pct", 0)
        search_pct = traffic.get("search", {}).get("pct", 0)
        suggested_pct = traffic.get("suggested", {}).get("pct", 0)
        external_pct = traffic.get("external", {}).get("pct", 0)

        lines.append(f"Traffic mix: Browse {browse_pct:.0f}% | Search {search_pct:.0f}% | "
                     f"Suggested {suggested_pct:.0f}% | External {external_pct:.0f}%")

        # Classification
        if search_pct > browse_pct and search_pct > suggested_pct:
            lines.append("Channel type: SEARCH-DEPENDENT — viewers find you via search queries")
            lines.append("Strategy: Optimize titles/tags for search, target high-volume keywords")
        elif browse_pct > search_pct and browse_pct > suggested_pct:
            lines.append("Channel type: BROWSE-DRIVEN — YouTube homepage recommends your content")
            lines.append("Strategy: Focus on high CTR thumbnails and curiosity-gap titles")
        elif suggested_pct > search_pct and suggested_pct > browse_pct:
            lines.append("Channel type: SUGGESTED-DRIVEN — your content appears as suggested videos")
            lines.append("Strategy: Create content that pairs well with popular videos in your niche")
        else:
            lines.append("Channel type: BALANCED — traffic is evenly distributed")
            lines.append("Strategy: Maintain strong SEO while optimizing CTR for browse/suggested")

        return _truncate("\n".join(lines), max_words=200)
    except Exception:
        return ""


def get_retention_intelligence() -> str:
    """Expanded retention intelligence including retention curves."""
    try:
        insights = load_insights()
        video_count = _get_video_count(insights)
        ret = insights.get("retention_analysis", {})
        curves = insights.get("retention_curves", {})
        if not ret and not curves:
            return ""

        lines = ["RETENTION INTELLIGENCE:"]

        # Base knowledge blending
        _blend_base_retention(lines, video_count)

        # Standard retention analysis
        if ret.get("optimal_length_minutes"):
            lines.append(f"Optimal length: {ret['optimal_length_minutes']:.0f} minutes")
        if ret.get("retention_note"):
            lines.append(f"Insight: {ret['retention_note']}")

        bands = ret.get("retention_by_length_band", {})
        if bands:
            lines.append("\nRetention by length:")
            band_labels = {
                "under_8min": "< 8 min", "8_to_12min": "8-12 min",
                "12_to_16min": "12-16 min", "over_16min": "> 16 min"
            }
            for band, label in band_labels.items():
                d = bands.get(band, {})
                if d.get("sample_count", 0) > 0 and d.get("avg_retention") is not None:
                    lines.append(f"  {label}: {d['avg_retention']:.0f}% ({d['sample_count']} videos)")

        # Retention curve data
        if curves:
            hook_ret = curves.get("avg_hook_retention_30s")
            if hook_ret is not None:
                lines.append(f"\nHook retention (30s): {hook_ret:.0f}%")
            mid_ret = curves.get("avg_midpoint_retention")
            if mid_ret is not None:
                lines.append(f"Midpoint retention: {mid_ret:.0f}%")
            end_ret = curves.get("avg_end_retention")
            if end_ret is not None:
                lines.append(f"End retention: {end_ret:.0f}%")

        # Retention by hook type (from content classifier)
        try:
            hook_ret_str = _get_hook_type_retention(insights)
            if hook_ret_str:
                lines.append(f"\nRetention by hook type: {hook_ret_str}")
        except Exception:
            pass

        return _truncate("\n".join(lines), max_words=250)
    except Exception:
        return ""


def get_engagement_intelligence() -> str:
    """Format engagement data for agents."""
    try:
        insights = load_insights()
        engagement = insights.get("engagement_metrics", {})
        if not engagement:
            return ""

        lines = ["ENGAGEMENT INTELLIGENCE:"]

        avg_rate = engagement.get("avg_engagement_rate")
        if avg_rate is not None:
            lines.append(f"Avg engagement rate: {avg_rate:.2f}%")

        like_ratio = engagement.get("avg_like_ratio")
        if like_ratio is not None:
            lines.append(f"Avg like ratio: {like_ratio:.2f}%")

        total_likes = engagement.get("total_likes", 0)
        total_comments = engagement.get("total_comments", 0)
        total_shares = engagement.get("total_shares", 0)
        sample = engagement.get("sample_count", 0)
        if total_likes or total_comments:
            lines.append(f"Totals across {sample} videos: {total_likes:,} likes, "
                         f"{total_comments:,} comments, {total_shares:,} shares")

        return _truncate("\n".join(lines), max_words=200)
    except Exception:
        return ""


def get_search_intelligence() -> str:
    """Format search term data for SEO agent."""
    try:
        insights = load_insights()
        search = insights.get("search_intelligence", {})
        if not search:
            return ""

        lines = ["SEARCH INTELLIGENCE:"]

        # Top search terms
        top_terms = search.get("top_search_terms", [])
        if top_terms:
            lines.append("\nTop search terms driving traffic:")
            for t in top_terms[:30]:
                term = t.get("term", "")
                views = t.get("views", 0)
                if term:
                    lines.append(f"  \"{term}\" -- {int(views):,} views")

        return _truncate("\n".join(lines), max_words=350)
    except Exception:
        return ""


def get_first_48h_intelligence() -> str:
    """Format early performance data."""
    try:
        insights = load_insights()
        benchmarks = insights.get("first_48h_benchmarks", {})
        if not benchmarks:
            return ""

        lines = ["FIRST 48H PERFORMANCE INTELLIGENCE:"]

        avg_velocity = benchmarks.get("avg_velocity")
        if avg_velocity is not None:
            lines.append(f"Average first-48h velocity: {avg_velocity:.2f}")

        sample = benchmarks.get("sample_count", 0)
        if sample:
            lines.append(f"Sample size: {sample} videos")

        # Best performer
        best = benchmarks.get("best_performer")
        if best:
            title = best.get("title", "?")[:50]
            velocity = best.get("velocity", 0)
            lines.append(f"\nBest first-48h: \"{title}\" -- velocity {velocity:.2f}")

        # Worst performer
        worst = benchmarks.get("worst_performer")
        if worst:
            title = worst.get("title", "?")[:50]
            velocity = worst.get("velocity", 0)
            lines.append(f"Worst first-48h: \"{title}\" -- velocity {velocity:.2f}")

        return _truncate("\n".join(lines), max_words=250)
    except Exception:
        return ""


def get_endscreen_intelligence() -> str:
    """Format endscreen/card data."""
    try:
        insights = load_insights()
        endscreen = insights.get("endscreen_performance", {})
        if not endscreen:
            return ""

        lines = ["ENDSCREEN INTELLIGENCE:"]

        avg_card_ctr = endscreen.get("avg_card_ctr")
        if avg_card_ctr is not None:
            lines.append(f"Average card CTR: {avg_card_ctr:.2f}%")

        avg_es_ctr = endscreen.get("avg_endscreen_ctr")
        if avg_es_ctr is not None:
            lines.append(f"Average endscreen CTR: {avg_es_ctr:.2f}%")

        with_cards = endscreen.get("videos_with_cards", 0)
        with_es = endscreen.get("videos_with_endscreens", 0)
        if with_cards or with_es:
            lines.append(f"Videos with cards: {with_cards}, with endscreens: {with_es}")

        return _truncate("\n".join(lines), max_words=150)
    except Exception:
        return ""


def get_content_pattern_intelligence() -> str:
    """Cross-reference content attributes with performance."""
    try:
        insights = load_insights()
        per_video = insights.get("per_video_stats", [])
        if not per_video:
            return ""

        # Filter to videos that have content_classification
        classified = [v for v in per_video if v.get("content_classification")]
        if not classified:
            return ""

        lines = ["CONTENT PATTERN INTELLIGENCE:"]

        # Hook type vs retention
        hook_groups = {}
        for v in classified:
            cc = v.get("content_classification", {})
            hook_type = cc.get("hook_type", "unknown")
            ret_val = v.get("avg_retention_pct") or v.get("avg_view_percentage")
            if ret_val is not None:
                hook_groups.setdefault(hook_type, []).append(ret_val)

        if hook_groups:
            lines.append("\nHook type vs retention:")
            for hook, rets in sorted(hook_groups.items(), key=lambda x: -(sum(x[1]) / len(x[1]))):
                avg = sum(rets) / len(rets)
                lines.append(f"  {hook}: {avg:.0f}% avg retention ({len(rets)} videos)")

        # Title structure vs CTR
        title_groups = {}
        for v in classified:
            cc = v.get("content_classification", {})
            title_attr = cc.get("title_structure", "unknown")
            ctr = v.get("ctr_pct")
            if ctr is not None:
                title_groups.setdefault(title_attr, []).append(ctr)

        if title_groups:
            lines.append("\nTitle structure vs CTR:")
            for structure, ctrs in sorted(title_groups.items(), key=lambda x: -(sum(x[1]) / len(x[1]))):
                avg = sum(ctrs) / len(ctrs)
                lines.append(f"  {structure}: {avg:.1f}% avg CTR ({len(ctrs)} videos)")

        # Pacing vs watch time
        pacing_groups = {}
        for v in classified:
            cc = v.get("content_classification", {})
            pacing = cc.get("pacing_profile", "unknown")
            watch_time = v.get("avg_view_duration_seconds") or v.get("avg_watch_time_seconds")
            if watch_time is not None:
                pacing_groups.setdefault(pacing, []).append(watch_time)

        if pacing_groups:
            lines.append("\nPacing profile vs avg watch time:")
            for pacing, times in sorted(pacing_groups.items(), key=lambda x: -(sum(x[1]) / len(x[1]))):
                avg = sum(times) / len(times)
                lines.append(f"  {pacing}: {avg:.0f}s avg watch time ({len(times)} videos)")

        return _truncate("\n".join(lines), max_words=300)
    except Exception:
        return ""


def get_demographic_intelligence() -> str:
    """Format audience data for topic selection."""
    try:
        insights = load_insights()
        demographics = insights.get("audience_demographics", {})
        if not demographics:
            return ""

        lines = ["AUDIENCE DEMOGRAPHIC INTELLIGENCE:"]

        # Top countries
        top_countries = demographics.get("top_countries", [])
        if top_countries:
            lines.append("\nTop countries:")
            for c in top_countries[:5]:
                country = c.get("country", "?")
                pct = c.get("pct", 0)
                lines.append(f"  {country}: {pct:.1f}%")
            # Infer topic preference
            india_pct = sum(c.get("pct", 0) for c in top_countries if c.get("country", "").lower() in ("india", "in"))
            western_pct = sum(c.get("pct", 0) for c in top_countries
                             if c.get("country", "").lower() in ("united states", "us", "uk", "united kingdom",
                                                                    "canada", "ca", "australia", "au"))
            if india_pct > 40:
                lines.append("Topic hint: Strong Indian audience -- Indian/South Asian history topics will resonate")
            elif western_pct > 40:
                lines.append("Topic hint: Strong Western audience -- European/American history may perform better")

        # Age distribution
        age_dist = demographics.get("age_distribution", {})
        if age_dist:
            lines.append("\nAge distribution:")
            for age_range, pct in sorted(age_dist.items()):
                lines.append(f"  {age_range}: {pct:.1f}%")
            # Tone inference
            young_pct = sum(pct for age, pct in age_dist.items()
                           if any(y in age.lower() for y in ("13-17", "18-24")))
            mature_pct = sum(pct for age, pct in age_dist.items()
                            if any(y in age.lower() for y in ("35-44", "45-54", "55-64", "65+")))
            if young_pct > 50:
                lines.append("Tone hint: Younger skew -- keep language accessible, faster pacing")
            elif mature_pct > 40:
                lines.append("Tone hint: Mature audience -- can use more complex vocabulary and slower pacing")

        # Gender distribution
        gender = demographics.get("gender_split", {})
        if gender:
            lines.append(f"\nGender: {', '.join(f'{g}: {p:.0f}%' for g, p in gender.items())}")

        return _truncate("\n".join(lines), max_words=200)
    except Exception:
        return ""


# ── Content quality intelligence ──────────────────────────────────────────────

def get_content_quality_intelligence() -> str:
    """Format content quality correlation data for agent consumption.
    Returns structured intelligence about which content structures drive performance.
    Returns '' if no data available."""
    try:
        insights = load_insights()
        video_count = _get_video_count(insights)
        cqc = insights.get("content_quality_correlation", {})
        if not cqc or cqc.get("sample_size", 0) < 2:
            # No own data yet — return base knowledge priors
            lines = []
            _blend_base_content_quality(lines, video_count)
            return "\n".join(lines) if lines else ""

        lines = ["CONTENT QUALITY INTELLIGENCE (pipeline structure vs performance):"]

        correlations = cqc.get("feature_correlations", {})
        claude = cqc.get("claude_analysis", {})

        # Structure type performance
        struct_perf = correlations.get("structure_type_vs_retention", {})
        if struct_perf:
            lines.append("\nNarrative structure vs retention:")
            for stype, data in sorted(struct_perf.items(),
                                       key=lambda x: x[1].get("avg_retention", 0), reverse=True):
                lines.append(f"  {stype}: {data['avg_retention']:.0f}% retention, "
                             f"{data.get('avg_views', 0):.0f} avg views ({data['count']} videos)")

        # Hook type performance
        hook_perf = correlations.get("hook_type_vs_retention", {})
        if hook_perf:
            lines.append("\nHook type vs retention:")
            for htype, data in sorted(hook_perf.items(),
                                       key=lambda x: x[1].get("avg_retention", 0), reverse=True):
                lines.append(f"  {htype}: {data['avg_retention']:.0f}% retention ({data['count']} videos)")

        # Script quality correlations
        script_corr = correlations.get("script_quality_correlations", {})
        if script_corr:
            strong = [(k, v) for k, v in script_corr.items()
                      if v is not None and abs(v) > 0.3]
            if strong:
                lines.append("\nScript features correlated with retention:")
                for feat, r in sorted(strong, key=lambda x: abs(x[1]), reverse=True):
                    direction = "positively" if r > 0 else "negatively"
                    lines.append(f"  {feat.replace('_', ' ')}: r={r:.2f} ({direction} correlated)")

        # Claude's strongest signals
        strongest = claude.get("strongest_signals", [])
        if strongest:
            lines.append("\nSTRONGEST SIGNALS:")
            for signal in strongest[:5]:
                lines.append(f"  - {signal}")

        sample = cqc.get("sample_size", 0)
        lines.append(f"\n(Based on {sample} videos with full pipeline data)")

        # Blend base knowledge if still below maturity threshold
        _blend_base_content_quality(lines, video_count)

        return _truncate("\n".join(lines), max_words=500)
    except Exception:
        return ""


def get_content_quality_recommendation(agent_key: str) -> str:
    """Extract content quality recommendation for a specific agent.
    agent_key: 'narrative_architect', 'script_writer', 'scene_breakdown', or 'thumbnail'."""
    try:
        insights = load_insights()
        cqc = insights.get("content_quality_correlation", {})
        claude = cqc.get("claude_analysis", {})
        recs = claude.get("agent_recommendations", {})
        return recs.get(agent_key, "")
    except Exception:
        return ""


def get_music_intelligence() -> str:
    """Data-backed music selection guidance from performance analytics.

    Injected into agent 07 (scene breakdown) and convert.py music selection.
    Returns empty string if insufficient data.
    """
    try:
        insights = load_insights()
        mp = insights.get("music_performance", {})
        if not mp or mp.get("sample_size", 0) < 3:
            return ""

        lines = ["MUSIC INTELLIGENCE (data-backed):"]

        mood_perf = mp.get("mood_performance", {})
        if mood_perf:
            best = max(mood_perf, key=lambda m: mood_perf[m].get("avg_retention", 0))
            d = mood_perf[best]
            lines.append(f"  Best mood: {best} ({d['avg_retention']}% avg retention, "
                         f"{d['video_count']} videos)")

        bpm_perf = mp.get("bpm_performance", {})
        if bpm_perf:
            best_bpm = max(bpm_perf, key=lambda k: bpm_perf[k].get("avg_retention", 0))
            lines.append(f"  Best BPM range: {best_bpm} "
                         f"({bpm_perf[best_bpm]['avg_retention']}% retention)")

        adapt = mp.get("adaptation_impact", {})
        if adapt:
            lift = adapt.get("adapted_avg_retention", 0) - adapt.get("looped_avg_retention", 0)
            if abs(lift) > 0.5:
                lines.append(f"  Adapted vs looped: {lift:+.1f}% retention")

        stems = mp.get("stems_impact", {})
        if stems:
            lift = stems.get("stems_avg_retention", 0) - stems.get("no_stems_avg_retention", 0)
            if abs(lift) > 0.5:
                lines.append(f"  Stem ducking impact: {lift:+.1f}% retention")

        recs = mp.get("recommendations", [])
        if recs:
            lines.append("  Recommendations:")
            for r in recs[:3]:
                lines.append(f"    - {r}")

        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception:
        return ""


def get_scene_retention_intelligence() -> str:
    """Data-backed per-scene retention insights from scene manifest correlation.

    Tells agents which scene types, moods, and narrative functions retain
    viewers best. Injected into scene breakdown and script agents.
    """
    try:
        insights = load_insights()
        corr = insights.get("scene_retention_correlation", {})
        if not corr:
            return ""

        lines = ["SCENE RETENTION INTELLIGENCE (data-backed):"]

        # Silence beat effect
        sb = corr.get("silence_beat_effect", {})
        if sb.get("sample_with", 0) >= 3:
            delta = sb["avg_drop_without"] - sb["avg_drop_with"]
            if abs(delta) > 0.3:
                direction = "LESS" if delta > 0 else "MORE"
                lines.append(f"  Silence beats: {abs(delta):.1f}% {direction} drop than non-silence scenes ({sb['sample_with']} samples)")

        # Best/worst moods
        mood_ret = corr.get("mood_retention", {})
        if len(mood_ret) >= 3:
            sorted_moods = sorted(mood_ret.items(), key=lambda x: x[1].get("avg_drop", 99))
            best = sorted_moods[0]
            worst = sorted_moods[-1]
            if best[1].get("sample", 0) >= 5:
                lines.append(f"  Best-retaining mood: {best[0]} ({best[1]['avg_drop']:.1f}% avg drop, {best[1]['sample']} scenes)")
            if worst[1].get("sample", 0) >= 5:
                lines.append(f"  Worst-retaining mood: {worst[0]} ({worst[1]['avg_drop']:.1f}% avg drop, {worst[1]['sample']} scenes)")

        # Best/worst narrative functions
        fn_ret = corr.get("function_retention", {})
        if len(fn_ret) >= 3:
            sorted_fns = sorted(fn_ret.items(), key=lambda x: x[1].get("avg_drop", 99))
            best = sorted_fns[0]
            if best[1].get("sample", 0) >= 3:
                lines.append(f"  Best-retaining function: {best[0]} ({best[1]['avg_drop']:.1f}% avg drop)")

        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception:
        return ""


# ── Content pattern helpers (used by multiple functions) ──────────────────────

def _get_content_pattern_summary(insights: dict) -> str:
    """Return a one-line summary of best content patterns."""
    try:
        per_video = insights.get("per_video_stats", [])
        classified = [v for v in per_video if v.get("content_classification")]
        if not classified:
            return ""

        # Best hook type by retention
        hook_groups = {}
        for v in classified:
            cc = v.get("content_classification", {})
            hook_type = cc.get("hook_type", "unknown")
            ret_val = v.get("avg_retention_pct") or v.get("avg_view_percentage")
            if ret_val is not None:
                hook_groups.setdefault(hook_type, []).append(ret_val)

        if hook_groups:
            best_hook = max(hook_groups.items(), key=lambda x: sum(x[1]) / len(x[1]))
            avg = sum(best_hook[1]) / len(best_hook[1])
            return f"Best hook type: {best_hook[0]} ({avg:.0f}% avg retention)"
        return ""
    except Exception:
        return ""


def _get_hook_type_retention(insights: dict) -> str:
    """Return hook type retention ranking as a formatted string."""
    try:
        per_video = insights.get("per_video_stats", [])
        classified = [v for v in per_video if v.get("content_classification")]
        if not classified:
            return ""

        hook_groups = {}
        for v in classified:
            cc = v.get("content_classification", {})
            hook_type = cc.get("hook_type", "unknown")
            ret_val = v.get("avg_retention_pct") or v.get("avg_view_percentage")
            if ret_val is not None:
                hook_groups.setdefault(hook_type, []).append(ret_val)

        if not hook_groups:
            return ""

        ranked = sorted(hook_groups.items(), key=lambda x: -(sum(x[1]) / len(x[1])))
        parts = [f"{hook}: {sum(rets) / len(rets):.0f}%" for hook, rets in ranked]
        return " > ".join(parts)
    except Exception:
        return ""


def _get_pacing_correlation(insights: dict) -> str:
    """Return pacing profile correlation with watch time."""
    try:
        per_video = insights.get("per_video_stats", [])
        classified = [v for v in per_video if v.get("content_classification")]
        if not classified:
            return ""

        pacing_groups = {}
        for v in classified:
            cc = v.get("content_classification", {})
            pacing = cc.get("pacing_profile", "")
            ret_val = v.get("avg_retention_pct") or v.get("avg_view_percentage")
            if pacing and ret_val is not None:
                pacing_groups.setdefault(pacing, []).append(ret_val)

        if not pacing_groups:
            return ""

        ranked = sorted(pacing_groups.items(), key=lambda x: -(sum(x[1]) / len(x[1])))
        best = ranked[0]
        avg = sum(best[1]) / len(best[1])
        return f"Best pacing: {best[0]} ({avg:.0f}% avg retention, {len(best[1])} videos)"
    except Exception:
        return ""


def _get_title_attribute_correlation(per_video: list) -> str:
    """Return title attribute correlation with CTR."""
    try:
        classified = [v for v in per_video if v.get("content_classification")]
        if not classified:
            return ""

        title_groups = {}
        for v in classified:
            cc = v.get("content_classification", {})
            title_attr = cc.get("title_structure", "")
            ctr = v.get("ctr_pct")
            if title_attr and ctr is not None:
                title_groups.setdefault(title_attr, []).append(ctr)

        if not title_groups:
            return ""

        ranked = sorted(title_groups.items(), key=lambda x: -(sum(x[1]) / len(x[1])))
        best = ranked[0]
        avg = sum(best[1]) / len(best[1])
        return f"Best title structure: {best[0]} ({avg:.1f}% avg CTR, {len(best[1])} videos)"
    except Exception:
        return ""


# ── DNA confidence block ──────────────────────────────────────────────────────

def get_dna_confidence_block() -> str:
    """
    Returns live DNA confidence scores formatted for dna_loader injection.
    Falls back to the static 30% block if no data.
    """
    insights = load_insights()
    dna_conf = insights.get("dna_confidence_updates", {})
    n        = insights.get("data_quality", {}).get("videos_analyzed", 0)

    if not dna_conf or n < 2:
        return ""  # dna_loader will use the static confidence_scores section

    lines = [f"=== DNA CONFIDENCE SCORES (data-backed, {n} videos) ==="]
    labels = {
        "open_mid_action_hook":      "Open mid-action hook",
        "twist_reveal_ending":       "Twist reveal ending",
        "ancient_medieval_priority": "Ancient/Medieval priority",
        "10_15_min_standard_length": "10-15 min standard length",
        "present_tense_narration":   "Present tense narration",
        "dark_thumbnail_aesthetic":  "Dark thumbnail aesthetic",
    }
    for key, label in labels.items():
        score = dna_conf.get(key, 0.3)
        pct   = int(score * 100)
        if score >= 0.7:
            flag = "VALIDATED -- strong evidence supports this rule"
        elif score >= 0.5:
            flag = "supported -- evidence trending positive"
        elif score >= 0.3:
            flag = "neutral -- no conclusive data yet"
        else:
            flag = "WEAKENING -- data suggests reconsider"
        lines.append(f"- {label}: {pct}% confidence -- {flag}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Exemplar hooks
# ══════════════════════════════════════════════════════════════════════════════

def get_exemplar_hooks(max_exemplars: int = 5) -> str:
    """
    Return the opening hooks from top-performing videos, formatted for
    injection into script writer / narrative architect prompts.

    Extracts first ~30 words of each top video's script (the hook/cold open)
    paired with the hook type and retention data.

    Returns '' when no data available.
    """
    insights = load_insights()
    if insights.get("data_quality", {}).get("confidence_level", "none") == "none":
        return ""

    top_vids = insights.get("top_performing_videos", [])
    per_video = insights.get("per_video_stats", [])

    if not top_vids:
        return ""

    # Build lookup of hook types from per_video_stats
    hook_types = {}
    for v in per_video:
        title = v.get("title", "")
        cc = v.get("content_classification", {})
        if title and cc.get("hook_type"):
            hook_types[title] = cc["hook_type"]

    lines = ["EXEMPLAR HOOKS (top-performing openings — emulate patterns, don't copy):"]

    count = 0
    for v in top_vids:
        if count >= max_exemplars:
            break

        title = v.get("title", "")
        hook_words = v.get("hook_words", "")
        if not hook_words:
            # Fallback: use first 30 words of the narration if available
            narration = v.get("narration_opening", "")
            if narration:
                hook_words = " ".join(narration.split()[:30])

        if not hook_words and not title:
            continue

        hook_type = hook_types.get(title, "unknown")
        ret_val = v.get("avg_retention_pct") or v.get("avg_view_percentage")
        ret_str = f"{ret_val:.0f}% retention" if ret_val is not None else ""
        views = f"{int(v.get('views', 0)):,} views" if v.get("views") else ""
        stats = ", ".join(filter(None, [views, ret_str]))

        if hook_words:
            lines.append(f"  [{hook_type.upper()}] \"{hook_words[:150]}...\"")
            if stats:
                lines.append(f"    → {stats}")
        else:
            lines.append(f"  [{hook_type.upper()}] Title: \"{title[:80]}\"")
            if stats:
                lines.append(f"    → {stats}")

        count += 1

    if count == 0:
        return ""

    # Add hook type ranking summary
    try:
        ranking = _get_hook_type_retention(insights)
        if ranking:
            lines.append(f"\nHOOK TYPE RANKING BY RETENTION: {ranking}")
    except Exception:
        pass

    return "\n".join(lines)
