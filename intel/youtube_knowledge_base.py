"""
youtube_knowledge_base.py — Bayesian prior knowledge layer for The Obsidian Archive.

Provides structured YouTube strategy knowledge tuned for dark history documentary
content. Acts as a base layer of priors that get gradually overwritten by the
channel's own data as it accumulates (via the confidence blending function).

All functions are READ-ONLY and return strings or dicts. Never crashes — returns
safe defaults on any error. Importable without side effects.

Used by: channel_insights.py, 06_seo_agent.py, 00_topic_discovery.py,
         03_narrative_architect.py, 04_script_writer.py, thumbnail_agent.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. NICHE BENCHMARKS — History / Educational YouTube channels
# ---------------------------------------------------------------------------

BASE_BENCHMARKS: dict[str, float] = {
    # CTR % by channel size tier
    "ctr_0_1k":         4.5,    # new channels, low brand recognition
    "ctr_1k_10k":       5.5,    # growing, building niche audience
    "ctr_10k_100k":     6.5,    # established niche authority
    "ctr_100k_plus":    7.5,    # brand recognition lifts CTR

    # Average retention % by video length
    "retention_under_8min":   55.0,
    "retention_8_12min":      48.0,
    "retention_12_16min":     42.0,
    "retention_16_20min":     37.0,
    "retention_over_20min":   30.0,

    # Subscriber conversion (subs gained per view)
    "sub_conversion_rate":    0.003,   # 0.3% — typical for educational
    "sub_conversion_shorts":  0.001,   # 0.1% — shorts are lower intent

    # Views per impression (overall funnel efficiency)
    "views_per_impression":   0.045,   # ~4.5% click-through on average

    # RPM ranges for educational/history (USD)
    "rpm_low":          4.0,
    "rpm_mid":          7.0,
    "rpm_high":        12.0,

    # Shorts-specific
    "shorts_avg_retention_pct":  70.0,
    "shorts_avg_views":         800.0,

    # Average views per video for a new history channel (<10K subs)
    "avg_views_per_video":     500.0,
    "avg_likes_per_view":      0.04,
    "avg_comments_per_view":   0.005,
}

BENCHMARK_TIERS: dict[str, dict] = {
    "0_1k": {
        "label": "0 – 1K subscribers",
        "avg_ctr_pct": 4.5,
        "avg_retention_pct": 45.0,
        "avg_views_per_video": 200,
        "expected_impressions_per_video": 4_000,
        "note": "Algorithm tests content with small batches. CTR and retention "
                "matter more than raw numbers at this stage.",
    },
    "1k_10k": {
        "label": "1K – 10K subscribers",
        "avg_ctr_pct": 5.5,
        "avg_retention_pct": 47.0,
        "avg_views_per_video": 2_000,
        "expected_impressions_per_video": 35_000,
        "note": "Channel enters Browse/Suggested feed more regularly. "
                "Consistency becomes critical for algorithmic trust.",
    },
    "10k_100k": {
        "label": "10K – 100K subscribers",
        "avg_ctr_pct": 6.5,
        "avg_retention_pct": 44.0,
        "avg_views_per_video": 15_000,
        "expected_impressions_per_video": 250_000,
        "note": "Subscriber base provides reliable initial push. "
                "Suggested traffic begins to dominate.",
    },
    "100k_plus": {
        "label": "100K+ subscribers",
        "avg_ctr_pct": 7.5,
        "avg_retention_pct": 42.0,
        "avg_views_per_video": 80_000,
        "expected_impressions_per_video": 1_000_000,
        "note": "Brand recognition lifts CTR. Algorithm actively promotes "
                "new uploads. Risk of audience fatigue on repetitive topics.",
    },
}


# ---------------------------------------------------------------------------
# 2. TITLE PATTERN INTELLIGENCE — Dark history niche
# ---------------------------------------------------------------------------

TITLE_PATTERNS: dict = {
    "high_ctr_structures": [
        {
            "pattern": "The [Adjective] [Noun] That [Shocking Outcome]",
            "example": "The Forgotten Emperor That Erased an Entire Civilization",
            "why": "Mystery + scale + emotional weight. 'Forgotten' implies hidden knowledge.",
        },
        {
            "pattern": "Why [Historical Event] Was Far Worse Than You Think",
            "example": "Why The Black Death Was Far Worse Than You Think",
            "why": "Challenges existing knowledge — viewers click to close the gap.",
        },
        {
            "pattern": "The [Darkest/Deadliest/Most Brutal] [Noun] in History",
            "example": "The Deadliest Siege in History Nobody Talks About",
            "why": "Superlative + exclusivity. 'Nobody talks about' adds hidden-gem appeal.",
        },
        {
            "pattern": "[Number] [Horrifying/Disturbing] Facts About [Topic]",
            "example": "7 Horrifying Facts About Medieval Torture",
            "why": "Listicle format sets clear expectations. Numbers promise structured payoff.",
        },
        {
            "pattern": "What Really Happened at [Place/Event]",
            "example": "What Really Happened at the Library of Alexandria",
            "why": "Implies the popular narrative is wrong — curiosity gap.",
        },
        {
            "pattern": "The [Person/Group] Who [Did Something Unbelievable]",
            "example": "The Slave Who Became the Most Feared Gladiator in Rome",
            "why": "Character-driven underdog arc — viewers invest emotionally.",
        },
    ],
    "power_words": {
        "mystery_intrigue": [
            "forgotten", "hidden", "secret", "lost", "buried", "erased",
            "unknown", "mysterious", "vanished", "untold",
        ],
        "darkness_severity": [
            "darkest", "deadliest", "brutal", "horrifying", "terrifying",
            "cursed", "haunted", "forbidden", "sinister", "gruesome",
        ],
        "scale_impact": [
            "empire", "civilization", "dynasty", "kingdom", "ancient",
            "apocalyptic", "catastrophic", "unstoppable", "legendary",
        ],
        "exclusivity": [
            "nobody talks about", "they don't teach you", "you never learned",
            "history forgot", "the truth about", "what really happened",
        ],
    },
    "title_length": {
        "sweet_spot_chars": (45, 65),
        "sweet_spot_words": (7, 11),
        "note": "Titles 45-65 characters perform best. Long enough to build "
                "intrigue, short enough to display fully on mobile.",
    },
    "words_to_avoid": [
        "Part 1", "Part 2",       # Signals commitment — kills casual clicks
        "Episode",                 # Same as above
        "Documentary",             # Viewers expect entertainment, not lectures
        "Explained",               # Feels generic, overused in edu-YouTube
        "A Brief History",         # 'Brief' undersells the content
        "Review",                  # Wrong format signal for documentary content
        "Update",                  # Suggests ephemeral, not evergreen
    ],
    "framing_effectiveness": {
        "mystery_statement":  {"ctr_multiplier": 1.25, "note": "Best for dark history. 'The Forgotten City That...'"},
        "question":           {"ctr_multiplier": 1.10, "note": "Good for debunking. 'Did the Romans Really...'"},
        "direct_statement":   {"ctr_multiplier": 1.00, "note": "Baseline. 'The Fall of Constantinople'"},
        "listicle":           {"ctr_multiplier": 1.15, "note": "Works for compilations. '5 Most Brutal...'"},
        "challenge_belief":   {"ctr_multiplier": 1.20, "note": "Strong. 'Everything You Know About X Is Wrong'"},
    },
}


# ---------------------------------------------------------------------------
# 3. ALGORITHM MECHANICS
# ---------------------------------------------------------------------------

ALGORITHM_KNOWLEDGE: dict = {
    "first_24h_window": {
        "importance": "critical",
        "description": (
            "YouTube evaluates new uploads primarily in the first 24-48 hours. "
            "The algorithm shows the video to a small % of subscribers and "
            "measures CTR + average view duration. Strong early signals unlock "
            "broader distribution to Browse and Suggested feeds."
        ),
        "dark_history_tip": (
            "Publish when your core audience is online (typically 5-8 PM local). "
            "Use community posts 12-24h before to prime interest."
        ),
    },
    "traffic_sources": {
        "browse_features": {
            "share_pct": 40,
            "description": "Homepage and subscription feed. Dominated by CTR.",
            "how_to_win": "Strong thumbnails + titles. This is where brand recognition matters.",
        },
        "suggested_videos": {
            "share_pct": 30,
            "description": "Sidebar and end-screen recommendations. Driven by watch-time overlap.",
            "how_to_win": "Make content that shares audience DNA with bigger channels "
                          "(Kings and Generals, Historia Civilis, etc.).",
        },
        "youtube_search": {
            "share_pct": 20,
            "description": "Direct search results. Critical for small channels.",
            "how_to_win": "Target long-tail keywords early. Search traffic is the most "
                          "reliable growth lever below 10K subs.",
        },
        "external": {
            "share_pct": 10,
            "description": "Reddit, Twitter/X, forums, embeds.",
            "how_to_win": "Dark history content does well on r/history, r/todayilearned. "
                          "Share with genuine context, not spam.",
        },
    },
    "recommendation_factors": {
        "watch_time": {
            "weight": "very high",
            "note": "Total minutes watched is the single strongest signal. "
                    "A 12-min video with 50% retention beats a 6-min video with 80%.",
        },
        "session_time": {
            "weight": "high",
            "note": "If your video leads viewers to watch MORE YouTube (not leave), "
                    "the algorithm rewards you. End cards and series playlists help.",
        },
        "ctr": {
            "weight": "high",
            "note": "Click-through rate from impressions. Below 3% is concerning. "
                    "Above 8% is excellent for educational content.",
        },
        "engagement": {
            "weight": "medium",
            "note": "Likes, comments, shares. Comments with high reply rates "
                    "signal active discussion — algorithm loves this.",
        },
        "subscriber_velocity": {
            "weight": "medium",
            "note": "New subs gained from a video signal high value content.",
        },
    },
    "subscriber_impact_on_distribution": {
        "0_1k": "Algorithm tests with ~500-2000 impressions initially.",
        "1k_10k": "Initial push of ~5K-20K impressions. Subscriber activity matters.",
        "10k_100k": "Reliable 50K-200K impressions for on-brand content.",
        "100k_plus": "Can see 500K+ impressions day one. Brand carries weight.",
    },
    "reupload_strategy": (
        "Never delete and re-upload (kills URL equity). Instead: update thumbnail, "
        "title, and description. YouTube re-evaluates updated metadata. Wait 2-4 "
        "weeks between major changes to measure impact."
    ),
}


# ---------------------------------------------------------------------------
# 4. RETENTION PSYCHOLOGY — Dark history documentary style
# ---------------------------------------------------------------------------

RETENTION_PSYCHOLOGY: dict = {
    "hook_structure": {
        "first_5_seconds": (
            "Open with a visceral, mid-action moment. Drop the viewer into the "
            "most dramatic point of the story. Example: 'The screams echoed "
            "through the stone corridors as the last defenders realized the "
            "walls had been breached.' Never open with channel branding or "
            "'Hey guys, welcome back.'"
        ),
        "first_30_seconds": (
            "Establish the stakes and promise within 30 seconds. The viewer "
            "should know: (1) what era/event this covers, (2) why it matters, "
            "(3) what they will learn that they didn't know. End the hook with "
            "an open loop: 'But what nobody expected was what happened next.'"
        ),
        "cold_open_formula": (
            "DRAMATIC MOMENT -> QUICK CONTEXT -> PROMISE -> OPEN LOOP. "
            "This maps to: Emotion -> Orientation -> Value prop -> Curiosity."
        ),
    },
    "rehook_intervals": {
        "frequency_minutes": 3.5,
        "technique": (
            "Every 3-4 minutes, introduce a new sub-mystery or escalation. "
            "'But this was only the beginning...' or 'What historians didn't "
            "realize was...' These prevent the natural drop-off points."
        ),
        "visual_rehook": (
            "Pair narrative re-hooks with a visual change: new map, close-up "
            "of artifact, dramatic reenactment still. Pattern interrupt + "
            "narrative hook = retention spike."
        ),
    },
    "open_loop_technique": {
        "description": (
            "Plant a question early that won't be answered until later. "
            "The brain craves closure and will keep watching to get it."
        ),
        "examples": [
            "Mention a mysterious figure in the first minute, but don't reveal their role until minute 8.",
            "'There was one detail the archaeologists overlooked...' — reveal at the climax.",
            "Foreshadow a twist: 'The empire seemed unstoppable. It wasn't.'",
        ],
        "max_concurrent_loops": 2,
        "note": "More than 2 open loops feels chaotic. Resolve one before opening another.",
    },
    "pattern_interrupts": {
        "types": [
            "Visual: Switch from wide landscape to close-up artifact detail",
            "Audio: Drop music to silence before a key revelation",
            "Pacing: Speed up narration for action, slow down for gravity",
            "Format: Insert a 'modern parallel' or viewer question mid-narrative",
            "Text overlay: Flash a date, death count, or key name on screen",
        ],
        "frequency": "Every 60-90 seconds for subtle interrupts. Major interrupts every 3-4 minutes.",
    },
    "pacing_for_narrated_docs": {
        "narration_speed_wpm": (150, 170),
        "note": (
            "Dark history benefits from measured, deliberate pacing. Not too fast "
            "(loses gravitas), not too slow (loses engagement). 150-170 WPM is "
            "the sweet spot. Slow down to ~130 WPM for dramatic reveals."
        ),
        "silence_beats": (
            "Use 1-2 second pauses after major revelations. Silence is a powerful "
            "tool in dark narration — it lets the weight of information sink in."
        ),
        "act_structure": (
            "3-act structure works best for 10-15 min docs: "
            "Act 1 (setup, 0-3 min): Hook + world-building. "
            "Act 2 (escalation, 3-10 min): Deepening mystery, rising stakes. "
            "Act 3 (payoff, 10-end): Revelation + aftermath + lingering question."
        ),
    },
    "end_card_timing": {
        "placement_seconds_before_end": 20,
        "note": (
            "Place end cards 15-20 seconds before the video ends. Don't cut the "
            "narrative short — finish the story first, then add a brief 'If you "
            "want to go deeper...' transition to the next video."
        ),
        "best_practice": (
            "End with a cliffhanger or lingering question that connects to another "
            "video. 'The empire fell, but its darkest secret survived for centuries. "
            "That story is here.' This drives session time."
        ),
    },
}


# ---------------------------------------------------------------------------
# 5. THUMBNAIL BEST PRACTICES — Dark history niche
# ---------------------------------------------------------------------------

THUMBNAIL_KNOWLEDGE: dict = {
    "color_psychology": {
        "primary_palette": ["deep crimson (#8B0000)", "charcoal (#333333)", "aged gold (#C9A84C)", "bone white (#F5F0E1)"],
        "mood": "Dark, moody, high contrast. Backgrounds should feel ancient and weathered.",
        "contrast_rule": (
            "Ensure strong value contrast (light vs dark) so thumbnails read clearly "
            "at small sizes (mobile). Test at 168x94px — if the focal point isn't "
            "immediately clear, redesign."
        ),
        "avoid": "Bright pastels, neon colors, white backgrounds. These signal lifestyle/comedy, not dark history.",
    },
    "composition": {
        "rule_of_thirds": "Place the primary subject at a power point (intersection of thirds lines).",
        "focal_point": (
            "One clear focal point per thumbnail. For dark history: a face with "
            "intense expression, a dramatic artifact, or a ruined structure. "
            "Never split attention between two equal elements."
        ),
        "depth_layering": (
            "Use 3 layers: blurred/dark background, mid-ground subject, "
            "foreground text or element. This creates cinematic depth."
        ),
        "negative_space": "Leave room for the title text overlay on the left or top third.",
    },
    "text_overlay": {
        "max_words": 4,
        "font_style": "Bold, condensed sans-serif. Slight perspective tilt adds dynamism.",
        "placement": "Upper-left or lower-right. Never center — YouTube UI elements overlap center.",
        "color": "White or gold text with dark stroke/shadow for readability.",
        "when_to_use": (
            "Only add text if it significantly boosts the curiosity gap beyond "
            "what the title provides. 'ERASED' or 'FORBIDDEN' can work. "
            "Don't repeat the title in the thumbnail."
        ),
    },
    "face_and_emotion": {
        "impact": (
            "Thumbnails with human faces get ~30% higher CTR on average. "
            "For dark history: use paintings, statues, or artistic renderings "
            "of historical figures. Expression should convey intensity — fear, "
            "determination, madness, or stoic resolve."
        ),
        "eye_direction": "Subject's eyes should look toward the viewer or toward the text element.",
        "stylization": (
            "Apply slight color grading to faces: desaturate, add grain, or use "
            "a painterly effect. This signals 'historical' rather than 'modern vlog.'"
        ),
    },
    "ab_testing": {
        "approach": (
            "Always prepare 2-3 thumbnail variants. Test the primary for 48 hours, "
            "then swap if CTR is below the channel average. YouTube's built-in A/B "
            "test feature (if available) is ideal."
        ),
        "what_to_test": [
            "Face vs no face",
            "Text overlay vs clean image",
            "Warm tones (fire, gold) vs cold tones (blue, grey)",
            "Close-up vs wide shot",
        ],
        "minimum_impressions": 2000,
        "note": "Don't swap before 2000 impressions — small samples are noisy.",
    },
}


# ---------------------------------------------------------------------------
# 6. SHORTS STRATEGY
# ---------------------------------------------------------------------------

SHORTS_STRATEGY: dict = {
    "hook_first_second": (
        "The first frame must arrest scrolling. Use a dramatic visual + a bold "
        "text overlay or opening line. 'In 1347, a ship docked in Sicily carrying "
        "something that would kill half of Europe.' No intros, no branding."
    ),
    "optimal_duration": {
        "sweet_spot_seconds": (30, 45),
        "note": (
            "30-45 seconds is ideal for dark history shorts. Under 30s feels "
            "rushed for historical context. Over 50s loses the casual scroll audience."
        ),
    },
    "loop_endings": {
        "technique": (
            "End the short in a way that connects back to the opening. The last "
            "frame should feel like it leads into the first frame, encouraging "
            "rewatches. 'And that cycle... started all over again.' Loop = more "
            "watch time = more impressions."
        ),
        "examples": [
            "End with the same location/image shown at the start, but with new context.",
            "Pose a question at the end that the opening line answers.",
            "Circular narrative: 'And so, just like before, the empire crumbled.'",
        ],
    },
    "shorts_to_longform_funnel": {
        "strategy": (
            "Each short should be a 'teaser' for a long-form video. End with: "
            "'The full story of [topic] is on our channel.' Pin a comment linking "
            "to the long-form video. Shorts build subscribers; long-form builds "
            "watch time and revenue."
        ),
        "conversion_expectation": (
            "Expect 1-3% of shorts viewers to check the channel. Of those, "
            "~10% will watch a long-form video. Volume is the game."
        ),
    },
    "vertical_composition": {
        "framing": (
            "Use center-weighted composition for vertical. Place the key visual "
            "element in the middle 60% of the frame. Text overlays at top or bottom."
        ),
        "motion": (
            "Slow pans across paintings, maps, or artifacts work well vertically. "
            "Ken Burns effect (slow zoom + pan) is your primary tool."
        ),
        "text_size": "Minimum 48pt equivalent. Must be readable on a phone screen.",
    },
}


# ---------------------------------------------------------------------------
# 7. SEO FUNDAMENTALS — For small/growing channels
# ---------------------------------------------------------------------------

SEO_KNOWLEDGE: dict = {
    "long_tail_strategy": {
        "principle": (
            "Small channels cannot rank for 'Roman Empire' or 'World War 2'. "
            "Target long-tail keywords with lower competition: "
            "'what happened to the lost 9th legion' or 'most brutal medieval "
            "punishments for treason'. Search volume is lower but conversion "
            "(view-through) is much higher."
        ),
        "examples": [
            "ancient roman torture methods",
            "what really happened at pompeii",
            "forgotten african empires before colonization",
            "most brutal medieval siege tactics",
            "unsolved mysteries of ancient egypt",
        ],
    },
    "search_to_browse_transition": {
        "phase_1": "0-1K subs: Optimize for search. Target specific long-tail queries. "
                   "This builds a catalog of evergreen content.",
        "phase_2": "1K-10K subs: Mix search-targeted + trending topics. "
                   "Use Community posts to gauge interest before producing.",
        "phase_3": "10K+ subs: Browse/Suggested dominates. Focus on CTR and "
                   "retention optimization. Search becomes supplementary.",
    },
    "tag_strategy": {
        "total_tags": (8, 15),
        "mix": {
            "broad": ["dark history", "history documentary", "ancient history"],
            "medium": ["roman empire documentary", "medieval history explained"],
            "specific": ["fall of constantinople 1453", "siege of masada", "vlad the impaler true story"],
        },
        "note": (
            "Tags have less weight than they used to, but still matter for "
            "search disambiguation. Always include the primary keyword as the "
            "first tag. Mix 2-3 broad, 3-5 medium, and 3-5 specific long-tail tags."
        ),
    },
    "description_keywords": {
        "first_2_lines": (
            "The first 2 lines of the description appear above the fold. "
            "Front-load the primary keyword naturally: 'The siege of Masada "
            "is one of the most haunting events in ancient history...'"
        ),
        "keyword_density": (
            "Mention the primary keyword 2-3 times in the first 200 characters. "
            "Include 2-3 related keywords naturally throughout. "
            "Never keyword-stuff — YouTube's NLP detects it."
        ),
        "structure": (
            "Line 1-2: Hook + primary keyword. "
            "Line 3-4: Brief content summary. "
            "Line 5+: Timestamps/chapters. "
            "Bottom: Social links, credits, related video links."
        ),
    },
    "hashtag_strategy": {
        "count": 3,
        "placement": "First 3 hashtags appear above the video title on mobile.",
        "examples": ["#DarkHistory", "#AncientMysteries", "#ForgottenEmpires"],
        "note": "Use exactly 3 hashtags. More than 3 looks spammy. "
                "Rotate based on topic era.",
    },
}


# ---------------------------------------------------------------------------
# 8. PUBLISHING STRATEGY
# ---------------------------------------------------------------------------

PUBLISHING_STRATEGY: dict = {
    "consistency": {
        "principle": "Consistency > frequency. 1 video/week on the same day is better "
                     "than 3 videos one week and none the next.",
        "minimum_cadence": "1 long-form video per week. 2-3 shorts per week.",
        "algorithm_trust": (
            "YouTube rewards channels that publish predictably. The algorithm "
            "allocates more impression budget to channels with consistent schedules."
        ),
    },
    "best_times": {
        "days": ["Saturday", "Sunday", "Thursday"],
        "time_utc": "14:00-17:00 UTC",
        "note": (
            "Educational/documentary content peaks on weekends when viewers have "
            "longer attention spans. Thursday is strong for 'weekend binge' discovery. "
            "Publish 2-3 hours before the peak viewing window in your target timezone."
        ),
        "shorts_timing": "Shorts perform best posted in the morning (8-10 AM local) "
                         "when people are scrolling during commutes/breaks.",
    },
    "seasonal_patterns": {
        "october": "Horror-adjacent history peaks (plagues, witch trials, cursed places). Plan 2-3 videos.",
        "december_january": "Year-end 'best of' compilations. 'The Darkest Year in History' style content.",
        "summer": "Slightly lower educational viewership. Lean into lighter, faster-paced content.",
        "movie_game_releases": (
            "Align content with major historical movie/game/TV releases. "
            "A Gladiator sequel = surge in Roman Empire searches. "
            "Monitor entertainment calendars quarterly."
        ),
        "anniversaries": (
            "Historical anniversaries drive search traffic. Track major ones: "
            "fall of Rome, signing of Magna Carta, key battles. "
            "Publish 1-2 days before the anniversary date."
        ),
    },
    "community_posts": {
        "frequency": "2-3 community posts per week between video uploads.",
        "types": [
            "Polls: 'Which empire should we cover next?' (drives engagement + topic research)",
            "Behind-the-scenes: Share a surprising fact found during research",
            "Teaser: Post a thumbnail draft or intriguing quote 24h before upload",
            "Discussion: 'What's the most underrated event in history?' (comment farming)",
        ],
        "note": "Community posts keep the channel active in subscribers' feeds between uploads.",
    },
}


# ---------------------------------------------------------------------------
# 9. CONFIDENCE BLENDING FUNCTION
# ---------------------------------------------------------------------------

def get_blended_value(
    metric_name: str,
    own_data_value: float,
    own_video_count: int,
    maturity_threshold: int = 15,
) -> float:
    """Blend base knowledge with the channel's own data based on confidence level.

    At 0 videos: 100% base knowledge (prior).
    At maturity_threshold videos: 100% own data (posterior).
    Linear interpolation between.

    Args:
        metric_name: Key into BASE_BENCHMARKS.
        own_data_value: The channel's measured value for this metric.
        own_video_count: How many videos the channel has published.
        maturity_threshold: Number of videos needed for full confidence in own data.

    Returns:
        Blended float value. Falls back to own_data_value if metric_name
        is not found in BASE_BENCHMARKS.
    """
    try:
        base_value = BASE_BENCHMARKS.get(metric_name)
        if base_value is None:
            return float(own_data_value)
        confidence = min(1.0, max(0.0, own_video_count / maturity_threshold))
        return base_value * (1.0 - confidence) + float(own_data_value) * confidence
    except Exception:
        return float(own_data_value) if own_data_value is not None else 0.0


def get_blended_benchmarks(own_metrics: dict, own_video_count: int, threshold: int = 15) -> dict:
    """Blend all available metrics at once.

    Args:
        own_metrics: Dict of {metric_name: measured_value}.
        own_video_count: Channel's total video count.
        threshold: Maturity threshold for full confidence.

    Returns:
        Dict of {metric_name: blended_value} for every key in own_metrics.
    """
    try:
        return {
            k: get_blended_value(k, v, own_video_count, threshold)
            for k, v in own_metrics.items()
        }
    except Exception:
        return own_metrics


def get_confidence_pct(own_video_count: int, maturity_threshold: int = 15) -> float:
    """Return the current confidence percentage in own data (0.0 to 1.0)."""
    try:
        return min(1.0, max(0.0, own_video_count / maturity_threshold))
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# 10. AGENT-SPECIFIC KNOWLEDGE PACKS
# ---------------------------------------------------------------------------

def _truncate(text: str, max_words: int = 500) -> str:
    """Truncate text to max_words, appending [...] if truncated."""
    words = str(text).split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [...]"


def get_base_topic_discovery_intel() -> str:
    """Pre-formatted intelligence for Agent 00 (Topic Discovery).

    Returns era trend data, topic selection heuristics, and seasonal
    guidance tuned for dark history content. Ready for prompt injection.
    """
    try:
        lines = [
            "=== BASE YOUTUBE KNOWLEDGE: TOPIC DISCOVERY ===",
            "(These are industry priors — will be overridden as channel data accumulates.)",
            "",
            "ERA POPULARITY TRENDS (general YouTube audience):",
            "  Ancient Rome: HIGH demand, HIGH competition. Focus on untold angles.",
            "  Ancient Egypt: HIGH demand, MEDIUM competition. Mysteries outperform factual recaps.",
            "  Medieval Europe: MEDIUM-HIGH demand. Brutality + daily life topics dominate.",
            "  Ancient Greece: MEDIUM demand. Philosophy + warfare are the top draws.",
            "  Colonial/Empire: MEDIUM demand. Controversial — handle with nuance.",
            "  Indian History: GROWING demand, LOW competition. Massive underserved audience.",
            "  Modern (WW1/WW2): VERY HIGH demand, VERY HIGH competition. Only cover with unique angles.",
            "",
            "TOPIC SELECTION HEURISTICS:",
            "- Prioritize 'hidden gem' topics: known eras, unknown specific events.",
            "- Emotional stakes > academic completeness. Pick topics with human drama.",
            "- 'Forbidden' or 'erased' framing massively boosts curiosity.",
            "- Check Google Trends for the topic — flat or rising = good, declining = avoid.",
            "- Cross-reference with other history channels: if nobody has covered it, that's gold.",
            "- If a major channel covered it recently, wait 6+ months or find a different angle.",
            "",
            "SEASONAL CONSIDERATIONS:",
            f"  October: {PUBLISHING_STRATEGY['seasonal_patterns']['october']}",
            f"  Dec-Jan: {PUBLISHING_STRATEGY['seasonal_patterns']['december_january']}",
            f"  Anniversaries: {PUBLISHING_STRATEGY['seasonal_patterns']['anniversaries']}",
            "",
            "SHORTS TOPIC STRATEGY:",
            "- Pick the single most shocking fact from a long-form topic.",
            "- 'Did you know' framing works for shorts but NOT long-form.",
            "- Each short should funnel to an existing or upcoming long-form video.",
            "=== END BASE KNOWLEDGE ===",
        ]
        return _truncate("\n".join(lines), max_words=450)
    except Exception:
        return ""


def get_base_narrative_intel() -> str:
    """Pre-formatted intelligence for Agent 03 (Narrative Architect).

    Returns structure, pacing, hook guidance, and retention psychology
    tuned for dark history documentary narration.
    """
    try:
        hook = RETENTION_PSYCHOLOGY["hook_structure"]
        pacing = RETENTION_PSYCHOLOGY["pacing_for_narrated_docs"]
        rehook = RETENTION_PSYCHOLOGY["rehook_intervals"]
        open_loop = RETENTION_PSYCHOLOGY["open_loop_technique"]
        end_card = RETENTION_PSYCHOLOGY["end_card_timing"]

        lines = [
            "=== BASE YOUTUBE KNOWLEDGE: NARRATIVE STRUCTURE ===",
            "(These are industry priors — will be overridden as channel data accumulates.)",
            "",
            "HOOK STRUCTURE:",
            f"  First 5 seconds: {hook['first_5_seconds']}",
            f"  First 30 seconds: {hook['first_30_seconds']}",
            f"  Cold open formula: {hook['cold_open_formula']}",
            "",
            "ACT STRUCTURE:",
            f"  {pacing['act_structure']}",
            "",
            f"PACING: {pacing['note']}",
            f"  Narration speed: {pacing['narration_speed_wpm'][0]}-{pacing['narration_speed_wpm'][1]} WPM",
            f"  Silence beats: {pacing['silence_beats']}",
            "",
            "RE-HOOK INTERVALS:",
            f"  Frequency: every {rehook['frequency_minutes']} minutes",
            f"  Technique: {rehook['technique']}",
            f"  Visual re-hook: {rehook['visual_rehook']}",
            "",
            "OPEN LOOPS:",
            f"  {open_loop['description']}",
            f"  Max concurrent: {open_loop['max_concurrent_loops']}",
            "  Examples:",
        ]
        for ex in open_loop["examples"]:
            lines.append(f"    - {ex}")
        lines += [
            "",
            "PATTERN INTERRUPTS:",
        ]
        for pi in RETENTION_PSYCHOLOGY["pattern_interrupts"]["types"]:
            lines.append(f"  - {pi}")
        lines += [
            f"  Frequency: {RETENTION_PSYCHOLOGY['pattern_interrupts']['frequency']}",
            "",
            "END CARD STRATEGY:",
            f"  Placement: {end_card['placement_seconds_before_end']}s before end",
            f"  Best practice: {end_card['best_practice']}",
            "",
            "RETENTION BENCHMARKS BY LENGTH:",
            f"  Under 8 min: {BASE_BENCHMARKS['retention_under_8min']}%",
            f"  8-12 min: {BASE_BENCHMARKS['retention_8_12min']}%",
            f"  12-16 min: {BASE_BENCHMARKS['retention_12_16min']}%",
            f"  16-20 min: {BASE_BENCHMARKS['retention_16_20min']}%",
            f"  Over 20 min: {BASE_BENCHMARKS['retention_over_20min']}%",
            "=== END BASE KNOWLEDGE ===",
        ]
        return _truncate("\n".join(lines), max_words=500)
    except Exception:
        return ""


def get_base_retention_intel() -> str:
    """Pre-formatted retention-specific intelligence for agents needing
    audience-retention guidance (hook strength, drop-off psychology,
    re-engagement, pacing).

    Draws from RETENTION_PSYCHOLOGY and BASE_BENCHMARKS.
    """
    try:
        hook = RETENTION_PSYCHOLOGY["hook_structure"]
        rehook = RETENTION_PSYCHOLOGY["rehook_intervals"]
        pacing = RETENTION_PSYCHOLOGY["pacing_for_narrated_docs"]
        pattern = RETENTION_PSYCHOLOGY["pattern_interrupts"]
        open_loop = RETENTION_PSYCHOLOGY["open_loop_technique"]
        end_card = RETENTION_PSYCHOLOGY["end_card_timing"]

        lines = [
            "=== BASE YOUTUBE KNOWLEDGE: RETENTION ===",
            "(Industry priors — will be overridden as channel data accumulates.)",
            "",
            "RETENTION BENCHMARKS (history/educational niche by video length):",
            f"  Under 8 min:  {BASE_BENCHMARKS['retention_under_8min']}% avg retention",
            f"  8-12 min:     {BASE_BENCHMARKS['retention_8_12min']}%",
            f"  12-16 min:    {BASE_BENCHMARKS['retention_12_16min']}%",
            f"  16-20 min:    {BASE_BENCHMARKS['retention_16_20min']}%",
            f"  Over 20 min:  {BASE_BENCHMARKS['retention_over_20min']}%",
            "",
            "HOOK RETENTION (first 30 seconds):",
            f"  First 5 seconds: {hook['first_5_seconds']}",
            f"  First 30 seconds: {hook['first_30_seconds']}",
            f"  Cold open formula: {hook['cold_open_formula']}",
            "",
            "DROP-OFF PSYCHOLOGY — WHY VIEWERS LEAVE:",
            "  - Weak hook: If the first 5 seconds don't spark emotion or curiosity, 30-40% leave immediately.",
            "  - No stakes established: Viewers need to know WHY this matters within 30 seconds.",
            "  - Predictability: Once the viewer can guess the outcome, they have no reason to stay.",
            "  - Pacing lulls: Stretches longer than 90 seconds without a new development trigger exits.",
            "  - Unresolved confusion: Too many names/dates without context overwhelms casual viewers.",
            "",
            "RE-ENGAGEMENT TECHNIQUES:",
            f"  Re-hook frequency: every {rehook['frequency_minutes']} minutes",
            f"  Technique: {rehook['technique']}",
            f"  Visual re-hook: {rehook['visual_rehook']}",
            "",
            "  Open loops: {desc}".format(desc=open_loop['description']),
            f"  Max concurrent loops: {open_loop['max_concurrent_loops']}",
            "",
            "  Pattern interrupts (every 60-90s subtle, every 3-4 min major):",
        ]
        for pi in pattern["types"]:
            lines.append(f"    - {pi}")
        lines += [
            "",
            "PACING ADVICE FOR RETENTION:",
            f"  Narration speed: {pacing['narration_speed_wpm'][0]}-{pacing['narration_speed_wpm'][1]} WPM",
            f"  {pacing['note']}",
            f"  Silence beats: {pacing['silence_beats']}",
            f"  Act structure: {pacing['act_structure']}",
            "",
            "END-OF-VIDEO RETENTION:",
            f"  End card placement: {end_card['placement_seconds_before_end']}s before end",
            f"  Best practice: {end_card['best_practice']}",
            "=== END BASE KNOWLEDGE ===",
        ]
        return _truncate("\n".join(lines), max_words=500)
    except Exception:
        return ""


def get_base_script_intel() -> str:
    """Pre-formatted intelligence for Agent 04 (Script Writer).

    Returns writing techniques, word choice guidance, emotional arc
    strategies, and dark-history-specific narration tips.
    """
    try:
        power = TITLE_PATTERNS["power_words"]
        lines = [
            "=== BASE YOUTUBE KNOWLEDGE: SCRIPT WRITING ===",
            "(These are industry priors — will be overridden as channel data accumulates.)",
            "",
            "OPENING LINE RULES:",
            "- First sentence must be visceral and immediate. Drop the viewer INTO the moment.",
            "- Never start with 'Today we're going to talk about...' or any meta-framing.",
            "- Use present tense for the hook: 'The walls are crumbling' not 'The walls crumbled.'",
            "- Sensory details in the first 2 sentences: sounds, sights, textures of the era.",
            "",
            "WORD CHOICE FOR DARK HISTORY:",
            f"  Mystery/Intrigue: {', '.join(power['mystery_intrigue'][:7])}",
            f"  Darkness/Severity: {', '.join(power['darkness_severity'][:7])}",
            f"  Scale/Impact: {', '.join(power['scale_impact'][:7])}",
            "",
            "EMOTIONAL ARC TEMPLATE:",
            "  1. INTRIGUE (0-15%): Mystery or shocking moment. Viewer asks 'What happened?'",
            "  2. CONTEXT (15-30%): Build the world. Who were these people? What was at stake?",
            "  3. ESCALATION (30-60%): Deepen the conflict. Introduce complications and betrayals.",
            "  4. CRISIS (60-80%): The darkest point. Maximum tension.",
            "  5. REVELATION (80-90%): The truth, twist, or ultimate consequence.",
            "  6. ECHO (90-100%): What this means. Why it still matters. Lingering question.",
            "",
            "NARRATION TECHNIQUES:",
            "- Use 'you' sparingly but effectively: 'Imagine you're standing on those walls...'",
            "- Contrast past and present: 'Today this is a quiet field. In 1066, it was an abattoir.'",
            "- Name individuals when possible. 'A soldier' is forgettable. 'Marcus, a 19-year-old legionnaire' is human.",
            "- Use short sentences for impact. Long sentences for atmosphere. Alternate.",
            "- Rhetorical questions every 2-3 minutes: 'So why did they stay?'",
            "",
            "THINGS TO AVOID:",
            "- Academic tone. This is storytelling, not a lecture.",
            "- Passive voice (except for deliberate dramatic effect).",
            "- Modern slang or anachronistic language.",
            "- Hedging language ('some historians think maybe...'). Be confident: 'Evidence suggests...'",
            "- Gratuitous violence without purpose. Dark does not mean exploitative.",
            "",
            "SCRIPT LENGTH TARGETS:",
            "  10-min video: ~1,500-1,700 words at 160 WPM",
            "  12-min video: ~1,800-2,000 words",
            "  15-min video: ~2,250-2,500 words",
            "  Short (40s): ~100-110 words",
            "=== END BASE KNOWLEDGE ===",
        ]
        return _truncate("\n".join(lines), max_words=500)
    except Exception:
        return ""


def get_base_seo_intel() -> str:
    """Pre-formatted intelligence for Agent 06 (SEO).

    Returns title, tag, description, and hashtag best practices
    specifically for dark history documentary content.
    """
    try:
        title_len = TITLE_PATTERNS["title_length"]
        framing = TITLE_PATTERNS["framing_effectiveness"]
        tags = SEO_KNOWLEDGE["tag_strategy"]
        desc = SEO_KNOWLEDGE["description_keywords"]
        hashtags = SEO_KNOWLEDGE["hashtag_strategy"]

        lines = [
            "=== BASE YOUTUBE KNOWLEDGE: SEO & METADATA ===",
            "(These are industry priors — will be overridden as channel data accumulates.)",
            "",
            "TITLE OPTIMIZATION:",
            f"  Sweet spot: {title_len['sweet_spot_chars'][0]}-{title_len['sweet_spot_chars'][1]} characters, "
            f"{title_len['sweet_spot_words'][0]}-{title_len['sweet_spot_words'][1]} words",
            "",
            "  High-CTR title structures:",
        ]
        for tp in TITLE_PATTERNS["high_ctr_structures"][:5]:
            lines.append(f"    Pattern: {tp['pattern']}")
            lines.append(f"    Example: \"{tp['example']}\"")
            lines.append(f"    Why: {tp['why']}")
            lines.append("")

        lines.append("  Framing effectiveness (CTR multiplier vs baseline):")
        for frame, data in framing.items():
            lines.append(f"    {frame.replace('_', ' ').title()}: {data['ctr_multiplier']}x — {data['note']}")

        lines += [
            "",
            "  Words to AVOID in titles:",
        ]
        for w in TITLE_PATTERNS["words_to_avoid"]:
            lines.append(f"    - {w}")

        lines += [
            "",
            "TAG STRATEGY:",
            f"  Total tags: {tags['total_tags'][0]}-{tags['total_tags'][1]}",
            f"  Broad examples: {', '.join(tags['mix']['broad'])}",
            f"  Medium examples: {', '.join(tags['mix']['medium'])}",
            f"  Specific examples: {', '.join(tags['mix']['specific'][:3])}",
            f"  Note: {tags['note']}",
            "",
            "DESCRIPTION:",
            f"  First 2 lines: {desc['first_2_lines']}",
            f"  Keyword density: {desc['keyword_density']}",
            f"  Structure: {desc['structure']}",
            "",
            "HASHTAGS:",
            f"  Count: {hashtags['count']} (exactly)",
            f"  Examples: {', '.join(hashtags['examples'])}",
            f"  Note: {hashtags['note']}",
            "",
            "SEARCH STRATEGY FOR SMALL CHANNELS:",
            f"  {SEO_KNOWLEDGE['long_tail_strategy']['principle']}",
            "",
            "  Example long-tail keywords:",
        ]
        for ex in SEO_KNOWLEDGE["long_tail_strategy"]["examples"][:4]:
            lines.append(f"    - {ex}")

        lines += [
            "",
            f"CTR BENCHMARKS: {BASE_BENCHMARKS['ctr_0_1k']}% (0-1K subs), "
            f"{BASE_BENCHMARKS['ctr_1k_10k']}% (1K-10K), "
            f"{BASE_BENCHMARKS['ctr_10k_100k']}% (10K-100K), "
            f"{BASE_BENCHMARKS['ctr_100k_plus']}% (100K+)",
            "=== END BASE KNOWLEDGE ===",
        ]
        return _truncate("\n".join(lines), max_words=550)
    except Exception:
        return ""


def get_base_thumbnail_intel() -> str:
    """Pre-formatted intelligence for thumbnail generation agents.

    Returns visual strategy, color psychology, composition rules, and
    A/B testing guidance for dark history documentary thumbnails.
    """
    try:
        color = THUMBNAIL_KNOWLEDGE["color_psychology"]
        comp = THUMBNAIL_KNOWLEDGE["composition"]
        text = THUMBNAIL_KNOWLEDGE["text_overlay"]
        face = THUMBNAIL_KNOWLEDGE["face_and_emotion"]
        ab = THUMBNAIL_KNOWLEDGE["ab_testing"]

        lines = [
            "=== BASE YOUTUBE KNOWLEDGE: THUMBNAIL STRATEGY ===",
            "(These are industry priors — will be overridden as channel data accumulates.)",
            "",
            "COLOR PALETTE:",
            f"  Primary colors: {', '.join(color['primary_palette'])}",
            f"  Mood: {color['mood']}",
            f"  Contrast: {color['contrast_rule']}",
            f"  Avoid: {color['avoid']}",
            "",
            "COMPOSITION:",
            f"  Rule of thirds: {comp['rule_of_thirds']}",
            f"  Focal point: {comp['focal_point']}",
            f"  Depth layering: {comp['depth_layering']}",
            f"  Negative space: {comp['negative_space']}",
            "",
            "TEXT OVERLAY:",
            f"  Max words: {text['max_words']}",
            f"  Font: {text['font_style']}",
            f"  Placement: {text['placement']}",
            f"  Color: {text['color']}",
            f"  When to use: {text['when_to_use']}",
            "",
            "FACES & EMOTION:",
            f"  {face['impact']}",
            f"  Eye direction: {face['eye_direction']}",
            f"  Stylization: {face['stylization']}",
            "",
            "A/B TESTING:",
            f"  Approach: {ab['approach']}",
            f"  Minimum impressions before swap: {ab['minimum_impressions']}",
            "  Test variables:",
        ]
        for test in ab["what_to_test"]:
            lines.append(f"    - {test}")

        lines += [
            "",
            "SHORTS THUMBNAIL (auto-generated frame):",
            "  The first frame IS the thumbnail for shorts. Make it count.",
            f"  {SHORTS_STRATEGY['hook_first_second']}",
            "=== END BASE KNOWLEDGE ===",
        ]
        return _truncate("\n".join(lines), max_words=450)
    except Exception:
        return ""


def get_base_shorts_intel() -> str:
    """Pre-formatted intelligence for shorts-related agents.

    Returns hook strategy, duration guidance, loop techniques, and
    funnel strategy for dark history YouTube Shorts.
    """
    try:
        dur = SHORTS_STRATEGY["optimal_duration"]
        loop = SHORTS_STRATEGY["loop_endings"]
        funnel = SHORTS_STRATEGY["shorts_to_longform_funnel"]
        vert = SHORTS_STRATEGY["vertical_composition"]

        lines = [
            "=== BASE YOUTUBE KNOWLEDGE: SHORTS STRATEGY ===",
            "(These are industry priors — will be overridden as channel data accumulates.)",
            "",
            "HOOK (FIRST 1 SECOND):",
            f"  {SHORTS_STRATEGY['hook_first_second']}",
            "",
            "DURATION:",
            f"  Sweet spot: {dur['sweet_spot_seconds'][0]}-{dur['sweet_spot_seconds'][1]} seconds",
            f"  Note: {dur['note']}",
            "",
            "LOOP ENDINGS:",
            f"  Technique: {loop['technique']}",
            "  Examples:",
        ]
        for ex in loop["examples"]:
            lines.append(f"    - {ex}")

        lines += [
            "",
            "SHORTS-TO-LONG-FORM FUNNEL:",
            f"  Strategy: {funnel['strategy']}",
            f"  Conversion: {funnel['conversion_expectation']}",
            "",
            "VERTICAL COMPOSITION:",
            f"  Framing: {vert['framing']}",
            f"  Motion: {vert['motion']}",
            f"  Text size: {vert['text_size']}",
            "",
            f"RETENTION BENCHMARK: {BASE_BENCHMARKS['shorts_avg_retention_pct']}% avg for history shorts",
            f"VIEW BENCHMARK: {BASE_BENCHMARKS['shorts_avg_views']:.0f} avg views per short (sub-10K channel)",
            "=== END BASE KNOWLEDGE ===",
        ]
        return _truncate("\n".join(lines), max_words=400)
    except Exception:
        return ""


def get_base_publishing_intel() -> str:
    """Pre-formatted publishing schedule intelligence.

    Returns timing, consistency, seasonal, and community post guidance.
    """
    try:
        cons = PUBLISHING_STRATEGY["consistency"]
        times = PUBLISHING_STRATEGY["best_times"]
        community = PUBLISHING_STRATEGY["community_posts"]

        lines = [
            "=== BASE YOUTUBE KNOWLEDGE: PUBLISHING STRATEGY ===",
            "(These are industry priors — will be overridden as channel data accumulates.)",
            "",
            "CONSISTENCY:",
            f"  {cons['principle']}",
            f"  Minimum cadence: {cons['minimum_cadence']}",
            f"  Algorithm trust: {cons['algorithm_trust']}",
            "",
            "BEST TIMES:",
            f"  Days: {', '.join(times['days'])}",
            f"  Time: {times['time_utc']}",
            f"  Note: {times['note']}",
            f"  Shorts: {times['shorts_timing']}",
            "",
            "SEASONAL PATTERNS:",
            f"  October: {PUBLISHING_STRATEGY['seasonal_patterns']['october']}",
            f"  Dec-Jan: {PUBLISHING_STRATEGY['seasonal_patterns']['december_january']}",
            f"  Summer: {PUBLISHING_STRATEGY['seasonal_patterns']['summer']}",
            f"  Tie-ins: {PUBLISHING_STRATEGY['seasonal_patterns']['movie_game_releases']}",
            "",
            "COMMUNITY POSTS:",
            f"  Frequency: {community['frequency']}",
            "  Types:",
        ]
        for t in community["types"]:
            lines.append(f"    - {t}")

        lines += [
            f"  Note: {community['note']}",
            "=== END BASE KNOWLEDGE ===",
        ]
        return _truncate("\n".join(lines), max_words=350)
    except Exception:
        return ""


def get_base_content_quality_intel() -> str:
    """Pre-formatted intelligence about content structure vs performance.

    Returns priors on which narrative structures, hook types, script qualities,
    and scene compositions drive retention in dark history documentaries.
    Used as fallback when the channel has no content quality correlation data yet.
    """
    try:
        lines = [
            "=== BASE YOUTUBE KNOWLEDGE: CONTENT QUALITY ===",
            "(These are industry priors — will be overridden as channel data accumulates.)",
            "",
            "NARRATIVE STRUCTURE VS RETENTION:",
            "  MYSTERY: Best for retention (~50%+) — viewers stay to solve it.",
            "  COUNTDOWN/TIMELINE: Strong retention — natural forward momentum.",
            "  CLASSIC (chronological): Solid baseline — works for most topics.",
            "  DUAL_TIMELINE: Higher engagement when executed well, riskier.",
            "  TRIAL/VERDICT: Great for controversial topics with clear stakes.",
            "",
            "HOOK TYPES (by retention at 30s):",
            "  mid_action: Best — drop viewer into the most dramatic moment.",
            "  provocative_question: Strong — creates immediate curiosity gap.",
            "  shocking_statement: Strong — pattern interrupt stops the scroll.",
            "  cold_open_narration: Moderate — depends on writing quality.",
            "  contextual_setup: Weakest — context-setting kills early retention.",
            "",
            "SCRIPT QUALITY SIGNALS:",
            "  Sentence length variance: HIGH variance = better retention.",
            "    (Mix 5-word punches with 25-word descriptions.)",
            "  Short sentence %: 30-40% short sentences (≤8 words) is optimal.",
            "  Question density: 3-5 questions per 1000 words drives engagement.",
            "  Emotional word density: 2-4% of words should be emotional.",
            "  Transition count: 8-12 transitions per script maintains flow.",
            "  Dialogue: 5-15% quoted speech adds variety to narration.",
            "",
            "SCENE COMPOSITION:",
            "  Scene count: 20-25 scenes for 10-15 min video is optimal.",
            "  Mood mix: 60% dark/tense + 30% dramatic + 10% reverent.",
            "  Reveal placement: Major reveal at 70-80% mark maximizes end retention.",
            "  Retention hooks: Place re-engagement moments every 3-4 minutes.",
            "  Dark/tense ratio above 0.5 correlates with higher retention in dark history.",
            "",
            "THUMBNAIL VS CTR:",
            "  Dark contrast with single bold element: highest CTR.",
            "  Faces with intense emotion: +15-25% CTR over faceless thumbnails.",
            "  2-3 word text overlay MAX — readable at mobile size (160x90px).",
            "  Warm/golden tones for ancient topics, cold/blue for medieval.",
            "=== END BASE KNOWLEDGE ===",
        ]
        return _truncate("\n".join(lines), max_words=400)
    except Exception:
        return ""


def get_full_knowledge_summary() -> str:
    """Return a compact summary of all base knowledge for debugging/overview."""
    try:
        return (
            f"YouTube Knowledge Base loaded: "
            f"{len(BASE_BENCHMARKS)} benchmark metrics, "
            f"{len(BENCHMARK_TIERS)} channel tiers, "
            f"{len(TITLE_PATTERNS['high_ctr_structures'])} title patterns, "
            f"{len(TITLE_PATTERNS['power_words'])} power word categories, "
            f"{len(ALGORITHM_KNOWLEDGE['traffic_sources'])} traffic source models, "
            f"{len(RETENTION_PSYCHOLOGY)} retention psychology sections, "
            f"{len(THUMBNAIL_KNOWLEDGE)} thumbnail knowledge areas, "
            f"{len(SEO_KNOWLEDGE)} SEO strategy sections, "
            f"{len(SHORTS_STRATEGY)} shorts strategy areas, "
            f"7 agent knowledge packs available."
        )
    except Exception:
        return "YouTube Knowledge Base loaded (summary unavailable)."
