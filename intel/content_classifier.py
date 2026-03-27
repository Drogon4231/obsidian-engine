"""
content_classifier.py — Content attribute classification for The Obsidian Archive.

Classifies hook types, pacing, thumbnail attributes, title patterns, and script
quality metrics. Produces a "content DNA" fingerprint per video that the analytics
agent correlates with performance metrics (views, retention, CTR).

All functions are pure/stateless. No AI calls — uses deterministic pattern matching
and numeric analysis. PIL is optional for thumbnail image analysis.

Used by: 12_analytics_agent.py, dashboard, future correlation engine.
"""

import re
import statistics
from typing import Optional

from intel.era_classifier import classify_era

# ── Constants ─────────────────────────────────────────────────────────────────

POWER_WORDS = {
    "dark", "secret", "forbidden", "lost", "hidden", "deadly", "brutal",
    "untold", "mysterious", "cursed", "terrifying", "savage", "shocking",
    "ancient", "forgotten", "blood", "death", "murder", "war", "massacre",
    "betrayal", "revenge", "doomed", "haunted", "sinister", "ruthless",
    "infamous", "legendary", "empire", "fallen", "destroyed", "unstoppable",
}

EMOTIONAL_WORDS = {
    "death", "blood", "terror", "glory", "love", "hate", "fear", "rage",
    "agony", "triumph", "horror", "despair", "betrayal", "sacrifice",
    "suffering", "joy", "grief", "vengeance", "fury", "ecstasy", "doom",
    "miracle", "tragedy", "slaughter", "mercy", "wrath", "pain", "hope",
    "courage", "shame", "pride", "sorrow", "anguish", "devastation",
}

TRANSITION_PHRASES = [
    "but", "however", "meanwhile", "what they didn't know",
    "what no one expected", "and yet", "suddenly", "then came",
    "everything changed", "but then", "little did they know",
    "on the other hand", "in reality", "the truth was",
    "things were about to change", "unbeknownst to",
]

ERA_AESTHETICS = {
    "ancient_rome":   "dark gold",
    "ancient_egypt":  "desert gold",
    "medieval":       "cold stone",
    "ancient_greece": "marble white",
    "colonial":       "sepia warm",
    "indian_history": "rich amber",
    "modern":         "steel grey",
    "other":          "dark neutral",
}

_PREFIX = "[ContentClassifier]"


# ── 1. Hook Type Classification ──────────────────────────────────────────────

def classify_hook(narration_text: str, first_scene: dict = None) -> dict:
    """Classify the opening hook type from the first ~50 words of narration.

    Uses keyword/pattern matching for speed and determinism.
    Returns: {"hook_type": str, "hook_words": str, "confidence": float}
    """
    if not narration_text or not isinstance(narration_text, str):
        print(f"{_PREFIX} No narration text provided for hook classification")
        return {"hook_type": "unknown", "hook_words": "", "confidence": 0.0}

    words = narration_text.split()
    opening = " ".join(words[:50])
    hook_words = " ".join(words[:10])
    opening_lower = opening.lower().strip()

    # Pattern matching in priority order
    # Question — opens with a question word or contains early "?"
    question_openers = ("what ", "why ", "how ", "did you know", "have you ever",
                        "who ", "where ", "when ", "could ", "would ", "can ")
    if any(opening_lower.startswith(q) for q in question_openers):
        return {"hook_type": "question", "hook_words": hook_words, "confidence": 0.9}
    if "?" in " ".join(words[:20]):
        return {"hook_type": "question", "hook_words": hook_words, "confidence": 0.7}

    # Direct address — addresses the viewer
    direct_openers = ("you ", "you've ", "you're ", "your ", "imagine ",
                      "picture this", "listen ", "look ")
    if any(opening_lower.startswith(d) for d in direct_openers):
        return {"hook_type": "direct_address", "hook_words": hook_words, "confidence": 0.85}

    # Statistic — opens with a number/percentage
    if re.match(r"^\d", opening_lower) or re.match(r"^(nearly|almost|over|about|roughly)\s+\d", opening_lower):
        return {"hook_type": "statistic", "hook_words": hook_words, "confidence": 0.85}
    if "%" in " ".join(words[:15]):
        return {"hook_type": "statistic", "hook_words": hook_words, "confidence": 0.7}

    # Contrast — juxtaposition patterns
    contrast_patterns = [
        r"he was .{5,30}\. he .{5,30}\.",
        r"she was .{5,30}\. she .{5,30}\.",
        r"they were .{5,30}\. they .{5,30}\.",
        r"loved .{3,20}\. .{3,20} (hated|feared|killed|murdered|destroyed)",
        r"but .{5,30} (secretly|actually|really|in truth)",
    ]
    for pattern in contrast_patterns:
        if re.search(pattern, opening_lower):
            return {"hook_type": "contrast", "hook_words": hook_words, "confidence": 0.75}
    # Simple sentence contrast: short first sentence followed by contradicting second
    sentences = re.split(r'[.!]', opening)
    if len(sentences) >= 2:
        s1 = sentences[0].strip().lower()
        s2 = sentences[1].strip().lower()
        if s1 and s2 and len(s1.split()) <= 10 and len(s2.split()) <= 10:
            if any(w in s2 for w in ["but", "yet", "however", "killed", "murdered",
                                      "destroyed", "hated", "feared"]):
                return {"hook_type": "contrast", "hook_words": hook_words, "confidence": 0.7}

    # Mystery — unsolved/unknown patterns
    mystery_keywords = ["no one knows", "nobody knows", "mystery", "vanished",
                        "disappeared", "unsolved", "enigma", "riddle",
                        "never been explained", "still unknown", "to this day"]
    if any(kw in opening_lower for kw in mystery_keywords):
        return {"hook_type": "mystery", "hook_words": hook_words, "confidence": 0.8}

    # Cold open — action/scene-setting verbs at start
    cold_open_patterns = [
        r"^the .{3,20} (raised|drew|pulled|swung|charged|entered|stood|fell|ran)",
        r"^(flames|fire|smoke|blood|screams|thunder|darkness|silence)",
        r"^(it was|the year was|the night of|on the morning of|at dawn|at midnight)",
        r"^(a (single|lone|young|old|tall|dark)|the (last|first|only|final))",
    ]
    for pattern in cold_open_patterns:
        if re.match(pattern, opening_lower):
            return {"hook_type": "cold_open", "hook_words": hook_words, "confidence": 0.7}

    # Bold claim — shocking statements with strong language
    bold_keywords = ["killed", "murdered", "destroyed", "wiped out", "single-handedly",
                     "changed the world", "most dangerous", "most powerful",
                     "greatest", "worst", "deadliest", "bloodiest", "largest",
                     "never before", "first time in history", "changed everything"]
    first_sentence = re.split(r'[.!?]', opening)[0].lower()
    if any(kw in first_sentence for kw in bold_keywords):
        return {"hook_type": "bold_claim", "hook_words": hook_words, "confidence": 0.7}

    # Default: classify as bold_claim with low confidence (most history content
    # opens with some kind of declarative statement)
    print(f"{_PREFIX} Hook type unclear, defaulting to bold_claim (low confidence)")
    return {"hook_type": "bold_claim", "hook_words": hook_words, "confidence": 0.3}


# ── 2. Narration Pacing Analysis ─────────────────────────────────────────────

def analyze_pacing(word_timestamps: list, total_duration: float) -> dict:
    """Analyze narration pacing from word-level timestamps.

    Args:
        word_timestamps: List of {"word": str, "start": float, "end": float}.
        total_duration: Total video duration in seconds.

    Returns dict with wpm, per-quarter breakdown, silence metrics, and profile.
    """
    defaults = {
        "wpm": 0.0,
        "wpm_first_30s": 0.0,
        "wpm_by_quarter": [0.0, 0.0, 0.0, 0.0],
        "silence_pct": 0.0,
        "longest_pause_seconds": 0.0,
        "pacing_variance": 0.0,
        "pacing_profile": "unknown",
    }

    if not word_timestamps or total_duration <= 0:
        print(f"{_PREFIX} Insufficient data for pacing analysis")
        return defaults

    # Sanitize timestamps
    stamps = []
    for w in word_timestamps:
        if isinstance(w, dict) and "start" in w and "end" in w:
            stamps.append(w)
    if not stamps:
        return defaults

    total_words = len(stamps)

    # Overall WPM
    spoken_span = stamps[-1]["end"] - stamps[0]["start"]
    wpm = (total_words / max(spoken_span, 0.1)) * 60

    # WPM in first 30 seconds
    words_first_30 = [w for w in stamps if w["start"] < 30.0]
    if words_first_30:
        span_30 = min(30.0, words_first_30[-1]["end"] - words_first_30[0]["start"])
        wpm_first_30s = (len(words_first_30) / max(span_30, 0.1)) * 60
    else:
        wpm_first_30s = 0.0

    # WPM by quarter
    quarter_dur = total_duration / 4.0
    wpm_by_quarter = []
    for q in range(4):
        q_start = q * quarter_dur
        q_end = (q + 1) * quarter_dur
        q_words = [w for w in stamps if w["start"] >= q_start and w["start"] < q_end]
        if q_words:
            q_span = q_words[-1]["end"] - q_words[0]["start"]
            q_wpm = (len(q_words) / max(q_span, 0.1)) * 60
        else:
            q_wpm = 0.0
        wpm_by_quarter.append(round(q_wpm, 1))

    # Silence analysis — gaps > 0.5s between consecutive words
    total_silence = 0.0
    longest_pause = 0.0
    for i in range(1, len(stamps)):
        gap = stamps[i]["start"] - stamps[i - 1]["end"]
        if gap > 0.5:
            total_silence += gap
            longest_pause = max(longest_pause, gap)

    silence_pct = (total_silence / max(total_duration, 0.1)) * 100

    # Pacing variance — approximate per-sentence WPM
    # Split into chunks of ~15 words as sentence proxy
    chunk_size = 15
    chunk_wpms = []
    for i in range(0, total_words, chunk_size):
        chunk = stamps[i:i + chunk_size]
        if len(chunk) >= 3:
            c_span = chunk[-1]["end"] - chunk[0]["start"]
            if c_span > 0:
                chunk_wpms.append((len(chunk) / c_span) * 60)
    pacing_variance = statistics.stdev(chunk_wpms) if len(chunk_wpms) >= 2 else 0.0

    # Pacing profile
    pacing_profile = _classify_pacing_profile(wpm_by_quarter, pacing_variance)

    result = {
        "wpm": round(wpm, 1),
        "wpm_first_30s": round(wpm_first_30s, 1),
        "wpm_by_quarter": wpm_by_quarter,
        "silence_pct": round(silence_pct, 1),
        "longest_pause_seconds": round(longest_pause, 2),
        "pacing_variance": round(pacing_variance, 1),
        "pacing_profile": pacing_profile,
    }
    print(f"{_PREFIX} Pacing: {wpm:.0f} WPM overall, {wpm_first_30s:.0f} WPM first 30s, profile={pacing_profile}")
    return result


def _classify_pacing_profile(wpm_by_quarter: list, variance: float) -> str:
    """Determine pacing profile from quarter-by-quarter WPM."""
    if not wpm_by_quarter or all(q == 0 for q in wpm_by_quarter):
        return "unknown"

    nonzero = [q for q in wpm_by_quarter if q > 0]
    if not nonzero:
        return "unknown"

    avg = sum(nonzero) / len(nonzero)
    q1 = wpm_by_quarter[0]

    # Front loaded: Q1 significantly faster than average
    if q1 > 0 and q1 > avg * 1.15:
        return "front_loaded"

    # Slow burn: Q1 significantly slower, builds up
    if q1 > 0 and q1 < avg * 0.85:
        return "slow_burn"

    # Dynamic: high variance
    if variance > 25:
        return "dynamic"

    return "steady"


# ── 3. Thumbnail Attribute Classification ────────────────────────────────────

def classify_thumbnail(thumbnail_path: str = None, thumbnail_url: str = None,
                       title: str = "") -> dict:
    """Classify thumbnail attributes from metadata and optional image analysis.

    Falls back to heuristic inference when image analysis isn't available.
    If thumbnail_path is provided and PIL is installed, performs basic image analysis.
    """
    result = {
        "has_text_overlay": None,
        "estimated_brightness": "dark",
        "color_scheme": "dark neutral",
        "face_present": False,
        "era_aesthetic": "dark neutral",
    }

    # Infer era aesthetic from title
    if title:
        era = classify_era(title)
        result["era_aesthetic"] = ERA_AESTHETICS.get(era, "dark neutral")
        result["color_scheme"] = ERA_AESTHETICS.get(era, "dark neutral")

        # Face detection heuristic: proper nouns / person-related keywords
        title_lower = title.lower()
        face_indicators = [
            "king", "queen", "emperor", "pharaoh", "general", "pope",
            "president", "leader", "warrior", "knight", "assassin",
            "man who", "woman who", "boy who", "girl who", "person",
        ]
        if any(ind in title_lower for ind in face_indicators):
            result["face_present"] = True
        # Names often have multiple capitalized words
        caps = re.findall(r"\b[A-Z][a-z]{2,}", title)
        if len(caps) >= 2:
            result["face_present"] = True

    # Default brightness for the channel's dark aesthetic
    result["estimated_brightness"] = "dark"

    # Try PIL-based image analysis
    if thumbnail_path:
        image_attrs = _analyze_thumbnail_image(thumbnail_path)
        if image_attrs:
            result.update(image_attrs)

    print(f"{_PREFIX} Thumbnail: brightness={result['estimated_brightness']}, "
          f"scheme={result['color_scheme']}, face={result['face_present']}")
    return result


def _analyze_thumbnail_image(path: str) -> Optional[dict]:
    """Perform basic image analysis with PIL if available."""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        print(f"{_PREFIX} PIL not available, skipping image analysis")
        return None

    try:
        img = Image.open(path).convert("RGB")
        stat = ImageStat.Stat(img)

        # Average brightness (0-255)
        avg_r, avg_g, avg_b = stat.mean[:3]
        brightness = (avg_r * 0.299 + avg_g * 0.587 + avg_b * 0.114)

        if brightness < 85:
            brightness_label = "dark"
        elif brightness < 170:
            brightness_label = "medium"
        else:
            brightness_label = "light"

        # Dominant color — which channel is strongest
        channels = {"red": avg_r, "green": avg_g, "blue": avg_b}
        dominant = max(channels, key=channels.get)

        # Map to descriptive scheme
        color_map = {
            "red":   "blood red" if avg_r > 150 else "dark crimson",
            "green": "earthy green" if brightness > 100 else "dark forest",
            "blue":  "cold blue" if avg_b > 150 else "deep navy",
        }
        color_scheme = color_map.get(dominant, "dark neutral")

        # Contrast: ratio of max to min channel
        chan_min = min(avg_r, avg_g, avg_b)
        chan_max = max(avg_r, avg_g, avg_b)
        contrast_ratio = chan_max / max(chan_min, 1)

        return {
            "estimated_brightness": brightness_label,
            "avg_brightness": round(brightness, 1),
            "dominant_color": dominant,
            "color_scheme": color_scheme,
            "contrast_ratio": round(contrast_ratio, 2),
        }
    except Exception as e:
        print(f"{_PREFIX} Image analysis failed: {e}")
        return None


# ── 4. Title Attribute Analysis ──────────────────────────────────────────────

def analyze_title(title: str) -> dict:
    """Classify title attributes for CTR correlation analysis.

    Analyzes word count, power words, sentiment, structure, etc.
    """
    if not title or not isinstance(title, str):
        print(f"{_PREFIX} No title provided for analysis")
        return {
            "word_count": 0, "char_count": 0, "has_number": False,
            "has_question": False, "has_colon": False, "power_words": [],
            "power_word_count": 0, "sentiment": "neutral",
            "structure": "declarative", "opening_word": "",
        }

    words = title.split()
    title_lower = title.lower()

    # Power words found
    found_power = [w for w in words if w.lower().strip(".,!?:;'\"") in POWER_WORDS]

    # Sentiment classification
    dark_indicators = sum(1 for w in words if w.lower().strip(".,!?:;'\"") in {
        "dark", "death", "murder", "blood", "brutal", "deadly", "cursed",
        "doomed", "haunted", "sinister", "massacre", "slaughter", "horror",
        "terrifying", "savage", "ruthless", "destroyed", "fallen",
    })
    sensational_indicators = sum(1 for w in words if w.lower().strip(".,!?:;'\"") in {
        "shocking", "unbelievable", "incredible", "insane", "mind-blowing",
        "you won't believe", "secret", "hidden", "forbidden", "untold",
    })
    if dark_indicators >= 2:
        sentiment = "dark"
    elif sensational_indicators >= 2:
        sentiment = "sensational"
    elif dark_indicators >= 1 or sensational_indicators >= 1:
        sentiment = "dark" if dark_indicators >= sensational_indicators else "sensational"
    else:
        sentiment = "neutral"

    # Structure classification
    structure = "declarative"
    if "?" in title:
        structure = "question"
    elif title_lower.startswith("how "):
        structure = "how_to"
    elif re.match(r"^\d+\s", title):
        structure = "list"
    elif ":" in title:
        # Could be mystery or revelation based on second half
        after_colon = title.split(":", 1)[1].strip().lower() if ":" in title else ""
        if any(w in after_colon for w in ["secret", "hidden", "untold", "mystery", "unknown"]):
            structure = "mystery"
        elif any(w in after_colon for w in ["truth", "revealed", "story", "real"]):
            structure = "revelation"
        else:
            structure = "declarative"
    elif any(kw in title_lower for kw in ["mystery", "who was", "what happened", "unknown"]):
        structure = "mystery"
    elif any(kw in title_lower for kw in ["truth about", "real story", "revealed"]):
        structure = "revelation"

    result = {
        "word_count": len(words),
        "char_count": len(title),
        "has_number": bool(re.search(r"\d", title)),
        "has_question": "?" in title,
        "has_colon": ":" in title,
        "power_words": found_power,
        "power_word_count": len(found_power),
        "sentiment": sentiment,
        "structure": structure,
        "opening_word": words[0] if words else "",
    }
    print(f"{_PREFIX} Title: {len(words)} words, {len(found_power)} power words, "
          f"sentiment={sentiment}, structure={structure}")
    return result


# ── 5. Script Quality Metrics ────────────────────────────────────────────────

def analyze_script_quality(script_text: str) -> dict:
    """Compute script quality metrics that correlate with audience retention.

    Analyzes sentence structure, question density, emotional language,
    dialogue proportion, and readability.
    """
    defaults = {
        "word_count": 0, "sentence_count": 0, "avg_sentence_length": 0.0,
        "sentence_length_variance": 0.0, "short_sentence_pct": 0.0,
        "question_count": 0, "questions_per_1000_words": 0.0,
        "transition_count": 0, "emotional_word_density": 0.0,
        "dialogue_pct": 0.0, "readability_grade": 0.0,
    }

    if not script_text or not isinstance(script_text, str):
        print(f"{_PREFIX} No script text provided for quality analysis")
        return defaults

    # Basic counts
    words = script_text.split()
    word_count = len(words)
    if word_count == 0:
        return defaults

    # Sentence splitting (handle abbreviations roughly)
    sentences = re.split(r'(?<=[.!?])\s+', script_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sentence_count = len(sentences) if sentences else 1

    # Sentence lengths
    sentence_lengths = [len(s.split()) for s in sentences]
    avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0

    # Variance
    if len(sentence_lengths) >= 2:
        sentence_length_variance = statistics.stdev(sentence_lengths)
    else:
        sentence_length_variance = 0.0

    # Short (punchy) sentences
    short_count = sum(1 for sl in sentence_lengths if sl <= 8)
    short_sentence_pct = (short_count / max(len(sentence_lengths), 1)) * 100

    # Questions
    question_count = script_text.count("?")
    questions_per_1000 = (question_count / max(word_count, 1)) * 1000

    # Transitions
    text_lower = script_text.lower()
    transition_count = 0
    for phrase in TRANSITION_PHRASES:
        transition_count += len(re.findall(r'\b' + re.escape(phrase) + r'\b', text_lower))

    # Emotional word density (per 100 words)
    emotional_count = sum(
        1 for w in words
        if w.lower().strip(".,!?:;'\"()-") in EMOTIONAL_WORDS
    )
    emotional_word_density = (emotional_count / max(word_count, 1)) * 100

    # Dialogue estimation — count quoted text proportion
    dialogue_matches = re.findall(r'["\u201c][^"\u201d]*["\u201d]', script_text)
    dialogue_words = sum(len(m.split()) for m in dialogue_matches)
    dialogue_pct = (dialogue_words / max(word_count, 1)) * 100

    # Readability — Flesch-Kincaid Grade Level approximation
    syllable_count = _estimate_syllables(script_text)
    if sentence_count > 0 and word_count > 0:
        fk_grade = (
            0.39 * (word_count / sentence_count)
            + 11.8 * (syllable_count / word_count)
            - 15.59
        )
    else:
        fk_grade = 0.0

    result = {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_sentence_length, 1),
        "sentence_length_variance": round(sentence_length_variance, 1),
        "short_sentence_pct": round(short_sentence_pct, 1),
        "question_count": question_count,
        "questions_per_1000_words": round(questions_per_1000, 1),
        "transition_count": transition_count,
        "emotional_word_density": round(emotional_word_density, 2),
        "dialogue_pct": round(dialogue_pct, 1),
        "readability_grade": round(max(fk_grade, 0), 1),
    }
    print(f"{_PREFIX} Script: {word_count} words, {sentence_count} sentences, "
          f"FK grade {fk_grade:.1f}, {question_count} questions")
    return result


def _estimate_syllables(text: str) -> int:
    """Rough syllable count using vowel-group heuristic."""
    words = re.findall(r"[a-zA-Z]+", text)
    total = 0
    for word in words:
        word = word.lower()
        count = len(re.findall(r'[aeiouy]+', word))
        # Silent e
        if word.endswith('e') and count > 1:
            count -= 1
        count = max(count, 1)
        total += count
    return total


# ── 6. Content DNA Fingerprint ───────────────────────────────────────────────

def compute_content_dna(hook_type: str, pacing: dict, title_attrs: dict,
                        script_quality: dict, era: str) -> dict:
    """Combine all classifications into a normalized numeric fingerprint.

    Each feature is normalized to 0-1 range for correlation analysis.
    Returns a flat dict of ~15-20 features stored per-video.
    """
    dna = {}

    # Hook type — one-hot encoding
    hook_types = ["question", "bold_claim", "mystery", "cold_open",
                  "statistic", "contrast", "direct_address"]
    for ht in hook_types:
        dna[f"hook_{ht}"] = 1.0 if hook_type == ht else 0.0

    # Pacing features (normalized)
    wpm = pacing.get("wpm", 0)
    dna["wpm_normalized"] = _normalize(wpm, 100, 220)  # typical narration range
    dna["wpm_first_30s_normalized"] = _normalize(pacing.get("wpm_first_30s", 0), 100, 250)
    dna["silence_pct"] = _normalize(pacing.get("silence_pct", 0), 0, 20)
    dna["pacing_variance_normalized"] = _normalize(pacing.get("pacing_variance", 0), 0, 50)

    pacing_profiles = {"steady": 0.25, "dynamic": 0.75, "front_loaded": 1.0, "slow_burn": 0.0}
    dna["pacing_profile_score"] = pacing_profiles.get(pacing.get("pacing_profile", ""), 0.5)

    # Title features
    dna["title_word_count_normalized"] = _normalize(title_attrs.get("word_count", 0), 3, 15)
    dna["title_has_number"] = 1.0 if title_attrs.get("has_number") else 0.0
    dna["title_has_question"] = 1.0 if title_attrs.get("has_question") else 0.0
    dna["title_has_colon"] = 1.0 if title_attrs.get("has_colon") else 0.0
    dna["title_power_word_density"] = _normalize(
        title_attrs.get("power_word_count", 0), 0, 4
    )

    sentiment_scores = {"dark": 1.0, "sensational": 0.7, "neutral": 0.3}
    dna["title_sentiment_score"] = sentiment_scores.get(title_attrs.get("sentiment", ""), 0.3)

    # Script quality features
    dna["script_avg_sentence_length"] = _normalize(
        script_quality.get("avg_sentence_length", 0), 5, 25
    )
    dna["script_short_sentence_pct"] = _normalize(
        script_quality.get("short_sentence_pct", 0), 0, 60
    )
    dna["script_question_density"] = _normalize(
        script_quality.get("questions_per_1000_words", 0), 0, 10
    )
    dna["script_emotional_density"] = _normalize(
        script_quality.get("emotional_word_density", 0), 0, 5
    )
    dna["script_dialogue_pct"] = _normalize(
        script_quality.get("dialogue_pct", 0), 0, 30
    )
    dna["script_readability_grade"] = _normalize(
        script_quality.get("readability_grade", 0), 4, 14
    )

    # Era — encoded as numeric
    era_scores = {
        "ancient_rome": 0.9, "ancient_egypt": 0.85, "medieval": 0.8,
        "ancient_greece": 0.75, "colonial": 0.5, "indian_history": 0.6,
        "modern": 0.4, "other": 0.3,
    }
    dna["era_score"] = era_scores.get(era, 0.3)

    print(f"{_PREFIX} Content DNA: {len(dna)} features computed")
    return dna


def _normalize(value: float, low: float, high: float) -> float:
    """Normalize value to 0-1 range given expected low/high bounds."""
    if high <= low:
        return 0.5
    normalized = (value - low) / (high - low)
    return round(max(0.0, min(1.0, normalized)), 3)


# ── 7. Batch Classification ─────────────────────────────────────────────────

def classify_video_content(manifest: dict, word_timestamps: list = None,
                           total_duration: float = 0) -> dict:
    """Run all classifiers on a video's manifest data and return complete classification.

    Args:
        manifest: Video manifest dict (expects keys: title, narration, script,
                  thumbnail_path, topic, etc.)
        word_timestamps: Optional word-level timestamps from audio.
        total_duration: Total video duration in seconds.

    Returns dict with hook, pacing, thumbnail, title, script_quality, content_dna.
    """
    if not manifest or not isinstance(manifest, dict):
        print(f"{_PREFIX} Invalid manifest, returning empty classification")
        return {
            "hook": {}, "pacing": {}, "thumbnail": {},
            "title": {}, "script_quality": {}, "content_dna": {},
        }

    title = manifest.get("title", "") or ""
    narration = manifest.get("narration", "") or manifest.get("script", "") or ""
    script = manifest.get("script", "") or narration
    thumbnail_path = manifest.get("thumbnail_path", None)
    thumbnail_url = manifest.get("thumbnail_url", None)
    topic = manifest.get("topic", "") or title

    print(f"{_PREFIX} Classifying content for: {title[:60]}...")

    # Run classifiers
    hook = classify_hook(narration)
    pacing = analyze_pacing(word_timestamps, total_duration) if word_timestamps else {
        "wpm": 0.0, "wpm_first_30s": 0.0, "wpm_by_quarter": [0.0, 0.0, 0.0, 0.0],
        "silence_pct": 0.0, "longest_pause_seconds": 0.0,
        "pacing_variance": 0.0, "pacing_profile": "unknown",
    }
    thumbnail = classify_thumbnail(
        thumbnail_path=thumbnail_path,
        thumbnail_url=thumbnail_url,
        title=title,
    )
    title_attrs = analyze_title(title)
    script_quality = analyze_script_quality(script)

    # Compute DNA fingerprint
    era = classify_era(topic)
    content_dna = compute_content_dna(
        hook_type=hook.get("hook_type", "unknown"),
        pacing=pacing,
        title_attrs=title_attrs,
        script_quality=script_quality,
        era=era,
    )

    result = {
        "hook": hook,
        "pacing": pacing,
        "thumbnail": thumbnail,
        "title": title_attrs,
        "script_quality": script_quality,
        "content_dna": content_dna,
    }
    print(f"{_PREFIX} Classification complete — hook={hook.get('hook_type')}, "
          f"era={era}, dna_features={len(content_dna)}")
    return result
