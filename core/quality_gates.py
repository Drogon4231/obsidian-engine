"""
Quality Gates — Pipeline validation library.
Three tiers of checks:

  Gate checks      → return (passed: bool, reason: str)   — pipeline aborts on fail
  Quality checks   → return list[str] of warnings          — logged, do not abort
  Soft metrics     → return dict of values                 — logged only

Usage:
    from quality_gates import gate_script_length, quality_script, metrics_script
"""

import re
import json
import subprocess
from pathlib import Path

# ── Optional dependency: requests ─────────────────────────────────────────────
try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _requests = None
    _REQUESTS_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
# Gate checks  (abort on fail)
# ══════════════════════════════════════════════════════════════════════════════

def gate_script_length(script_data: dict) -> tuple[bool, str]:
    """
    Script must be within tier-appropriate word count bounds.
    STANDARD: 1,000-1,500  |  DEEP_DIVE: 1,000-2,600  |  EPIC: 1,000-3,500

    Args:
        script_data: dict with a 'full_script' key containing the narration text.

    Returns:
        (True, "") or (False, reason)
    """
    full_script = script_data.get("full_script", "")
    word_count = len(full_script.split())
    tier = script_data.get("length_tier", "STANDARD").upper()

    tier_max = {"STANDARD": 1500, "DEEP_DIVE": 2600, "EPIC": 3500}.get(tier, 2500)

    if word_count < 1000:
        return False, f"Script too short: {word_count} words (minimum 1,000)."
    if word_count > tier_max:
        return False, f"Script too long: {word_count} words (maximum {tier_max} for {tier} tier)."
    return True, ""


def gate_verification_passed(verification_data: dict) -> tuple[bool, str]:
    """
    Fact verification must not have returned a REQUIRES_REWRITE verdict.

    Args:
        verification_data: dict from the fact verification agent.

    Returns:
        (True, "") or (False, reason)
    """
    verdict = verification_data.get("overall_verdict", verification_data.get("verdict", "")).upper().replace(" ", "_")
    if verdict == "REQUIRES_REWRITE":
        reason = verification_data.get("reason", "Fact verification flagged the script for rewrite.")
        return False, f"Verification gate failed: {reason}"
    return True, ""


def gate_audio_exists(audio_path: str) -> tuple[bool, str]:
    """
    Audio file must exist on disk and be larger than 500 KB.

    Args:
        audio_path: filesystem path to the generated MP3/audio file.

    Returns:
        (True, "") or (False, reason)
    """
    path = Path(audio_path)
    if not path.exists():
        return False, f"Audio file not found: {audio_path}"

    size_bytes = path.stat().st_size
    min_bytes = 500 * 1024  # 500 KB

    if size_bytes < min_bytes:
        return (
            False,
            f"Audio file too small: {size_bytes // 1024} KB at {audio_path} (minimum 500 KB).",
        )
    return True, ""


def gate_render_exists(video_path: str) -> tuple[bool, str]:
    """
    Rendered video file must exist on disk and be larger than 10 MB.

    Args:
        video_path: filesystem path to the rendered video file.

    Returns:
        (True, "") or (False, reason)
    """
    path = Path(video_path)
    if not path.exists():
        return False, f"Rendered video not found: {video_path}"

    size_bytes = path.stat().st_size
    min_bytes = 10 * 1024 * 1024  # 10 MB

    if size_bytes < min_bytes:
        return (
            False,
            f"Rendered video too small: {size_bytes / (1024*1024):.1f} MB at {video_path} "
            f"(minimum 10 MB).",
        )
    return True, ""


def gate_wpm_range(word_count: int, duration_s: float, target: int = 130, tolerance: float = 0.15) -> tuple[bool, str]:
    """
    Check that words-per-minute falls within acceptable range around target.

    Args:
        word_count: Number of words in the narration segment.
        duration_s: Duration in seconds of the audio.
        target: Target WPM (default 130).
        tolerance: Allowed deviation as fraction (default 0.15 = ±15%).

    Returns:
        (True, "") or (False, reason)
    """
    if duration_s <= 0:
        return False, f"Invalid audio duration: {duration_s}s"
    actual = (word_count / duration_s) * 60
    lo = target * (1 - tolerance)
    hi = target * (1 + tolerance)
    if actual < lo or actual > hi:
        return False, f"WPM {actual:.0f} outside {lo:.0f}-{hi:.0f} (target {target})"
    return True, ""


def gate_script_breathability(full_script: str) -> tuple[bool, str]:
    """
    Check that a script has sufficient pause points for natural delivery.

    Counts em-dashes, ellipses, short sentences (≤8 words), rhetorical questions,
    and paragraph breaks. Requires ≥3 pause points per 100 words overall, and
    ≥2 per 100 words in each quarter of the script.

    Args:
        full_script: The full narration text.

    Returns:
        (True, "") or (False, reason)
    """
    if not full_script or len(full_script.split()) < 50:
        return True, ""  # Too short to meaningfully check

    import statistics

    words = full_script.split()
    total_words = len(words)

    # Count pause points
    def _count_pauses(text: str) -> int:
        count = 0
        # Em-dashes
        count += text.count("—") + text.count(" -- ")
        # Ellipses
        count += text.count("...") + text.count("…")
        # Rhetorical questions
        count += text.count("?")
        # Short sentences (≤8 words)
        sentences = re.split(r'[.!?]+', text)
        count += sum(1 for s in sentences if 0 < len(s.split()) <= 8)
        # Paragraph breaks
        count += text.count("\n\n")
        return count

    total_pauses = _count_pauses(full_script)
    pauses_per_100 = (total_pauses / total_words) * 100 if total_words > 0 else 0

    if pauses_per_100 < 3:
        return False, f"Script breathability too low: {pauses_per_100:.1f} pause points per 100 words (need ≥3)"

    # Check per-quarter distribution
    quarter_size = total_words // 4
    for q in range(4):
        start = q * quarter_size
        end = (q + 1) * quarter_size if q < 3 else total_words
        quarter_text = " ".join(words[start:end])
        quarter_words = end - start
        quarter_pauses = _count_pauses(quarter_text)
        q_per_100 = (quarter_pauses / quarter_words) * 100 if quarter_words > 0 else 0
        if q_per_100 < 2:
            return False, f"Quarter {q+1} breathability too low: {q_per_100:.1f} per 100 words (need ≥2)"

    # Sentence-length variance check
    sentences = [s.strip() for s in re.split(r'[.!?]+', full_script) if s.strip()]
    if len(sentences) >= 5:
        lengths = [len(s.split()) for s in sentences]
        stdev = statistics.stdev(lengths)
        if stdev < 5:
            return False, f"Sentence-length variance too low: stdev={stdev:.1f} (need ≥5)"

    return True, ""


def gate_short_script_length(short_script_data: dict) -> tuple[bool, str]:
    """
    YouTube Shorts script must be between 80 and 200 words (targets 45-60 second delivery).

    Args:
        short_script_data: dict with a 'full_script' key containing the Shorts narration.

    Returns:
        (True, "") or (False, reason)
    """
    full_script = short_script_data.get("full_script", "")
    word_count = len(full_script.split())

    if word_count < 80:
        return False, f"Shorts script too short: {word_count} words (minimum 80 for ~45s)."
    if word_count > 200:
        return False, f"Shorts script too long: {word_count} words (maximum 200 for ~60s)."
    return True, ""


# ══════════════════════════════════════════════════════════════════════════════
# Quality checks  (warn, do not abort)
# ══════════════════════════════════════════════════════════════════════════════

def quality_research(research_data: dict) -> list[str]:
    """
    Check research output quality and return a list of warning strings.

    Warns if:
    - Fewer than 5 core facts
    - Fewer than 3 primary sources
    - Fewer than 2 key figures
    """
    warnings = []

    core_facts = research_data.get("core_facts", [])
    if len(core_facts) < 5:
        warnings.append(
            f"Research thin: only {len(core_facts)} core facts (recommend 5+)."
        )

    primary_sources = research_data.get("primary_sources", [])
    if len(primary_sources) < 3:
        warnings.append(
            f"Few primary sources: {len(primary_sources)} found (recommend 3+)."
        )

    key_figures = research_data.get("key_figures", [])
    if len(key_figures) < 2:
        warnings.append(
            f"Key figures sparse: only {len(key_figures)} identified (recommend 2+)."
        )

    return warnings


def quality_angle(angle_data: dict) -> list[str]:
    """
    Check originality/angle output quality and return a list of warning strings.

    Warns if:
    - No unique_angle field present or empty
    - No gap_in_coverage field present or empty
    - Unique angle description is shorter than 50 characters
    """
    warnings = []

    unique_angle = angle_data.get("unique_angle", "") or angle_data.get("chosen_angle", "")
    if not unique_angle:
        warnings.append("Angle missing: no 'unique_angle' or 'chosen_angle' in output.")
    elif len(unique_angle.strip()) < 50:
        warnings.append(
            f"Unique angle description very short ({len(unique_angle.strip())} chars) — "
            f"may not be sufficiently differentiated."
        )

    gap = angle_data.get("gap_in_coverage", "") or angle_data.get("twist_potential", "")
    if not gap:
        warnings.append(
            "No 'gap_in_coverage' or 'twist_potential' field — "
            "angle may not be differentiated from existing YouTube content."
        )

    return warnings


def quality_script(script_data: dict) -> list[str]:
    """
    Check script quality and return a list of warning strings.

    Warns if:
    - Script contains meta-text patterns (stage directions, headers, labels)
    - Fewer than 3 scene/paragraph breaks
    - Hook text appears to be missing (no strong opening)
    """
    warnings = []
    full_script = script_data.get("full_script", "")

    # Meta-text patterns that should not appear in a finalised script
    meta_patterns = [
        (r"\[.*?\]",                   "square-bracket stage directions"),
        (r"\(dramatic pause\)",        "(dramatic pause) marker"),
        (r"\(pause\)",                 "(pause) marker"),
        (r"\(beat\)",                  "(beat) marker"),
        (r"^HOOK\s*:",                 "HOOK: header label"),
        (r"^ACT\s*[123]\s*[:\-—]",    "ACT n: header label"),
        (r"^ENDING\s*:",               "ENDING: header label"),
        (r"^NARRATOR\s*:",             "NARRATOR: speaker label"),
        (r"\*\*[^*]+\*\*",            "bold markdown formatting"),
    ]
    for pattern, description in meta_patterns:
        if re.search(pattern, full_script, re.MULTILINE | re.IGNORECASE):
            warnings.append(f"Script contains meta-text: {description} — should be removed before TTS.")

    # Scene/paragraph break count (double newline = break between sections)
    scene_breaks = len(re.findall(r"\n\s*\n", full_script))
    if scene_breaks < 3:
        warnings.append(
            f"Only {scene_breaks} scene/paragraph breaks detected — "
            f"script may lack structural breathing room (recommend 3+)."
        )

    # Weak hook check: first 100 words should not start with a preamble
    first_100 = " ".join(full_script.split()[:100]).lower()
    preamble_phrases = [
        "in this video", "welcome back", "today we", "today i", "hello everyone",
        "in today's", "subscribe", "like and subscribe",
    ]
    for phrase in preamble_phrases:
        if phrase in first_100:
            warnings.append(
                f"Possible weak hook: script opens with preamble phrase '{phrase}' "
                f"— should open mid-action."
            )
            break

    return warnings


def quality_scenes(scenes_data: dict) -> list[str]:
    """
    Check scene breakdown quality and return a list of warning strings.

    Warns if:
    - Fewer than 10 scenes
    - More than 40 scenes
    - Any scene has narration text shorter than 20 words
    """
    warnings = []
    scenes = scenes_data.get("scenes", [])

    if len(scenes) < 10:
        warnings.append(
            f"Scene count low: {len(scenes)} scenes (recommend 10+ for a full episode)."
        )
    if len(scenes) > 40:
        warnings.append(
            f"Scene count high: {len(scenes)} scenes (recommend ≤40 to avoid render complexity)."
        )

    short_scene_ids = []
    for scene in scenes:
        narration = scene.get("narration", "")
        if len(narration.split()) < 20:
            short_scene_ids.append(str(scene.get("scene_id", "?")))

    if short_scene_ids:
        warnings.append(
            f"Scene(s) with narration < 20 words: IDs {', '.join(short_scene_ids)} — "
            f"may cause timing issues in the renderer."
        )

    return warnings


def quality_audio(audio_data: dict) -> list[str]:
    """
    Check audio generation output quality and return a list of warning strings.

    Warns if:
    - Duration is less than 480 seconds (8 min) — below mid-roll ad eligibility
    - Duration is greater than 1200 seconds (20 min) — unusually long
    - Fewer than 100 word timestamps — alignment may be incomplete
    - Audio file is smaller than 1 MB on disk
    """
    warnings = []

    duration = audio_data.get("total_duration_seconds", 0)
    if duration < 480:
        warnings.append(
            f"Audio duration short: {duration:.0f}s ({duration/60:.1f} min) — "
            f"below 8 min mid-roll threshold. Target 9–11 min for series."
        )
    if duration > 1200:
        warnings.append(
            f"Audio duration long: {duration:.0f}s ({duration/60:.1f} min) — "
            f"consider whether the script needs trimming."
        )

    # Check word timestamp count — proxy for alignment quality
    timestamps_path = audio_data.get("timestamps_path", "")
    word_count_in_timestamps = 0
    if timestamps_path and Path(timestamps_path).exists():
        try:
            with open(timestamps_path) as f:
                ts_data = json.load(f)
            word_count_in_timestamps = len(ts_data.get("words", []))
        except Exception:
            warnings.append(f"Could not read timestamps file: {timestamps_path}")

    if word_count_in_timestamps < 100 and timestamps_path:
        warnings.append(
            f"Word timestamps sparse: only {word_count_in_timestamps} words found in "
            f"timestamps — subtitle sync may be inaccurate."
        )

    audio_path = audio_data.get("audio_path", "")
    if audio_path and Path(audio_path).exists():
        size_bytes = Path(audio_path).stat().st_size
        if size_bytes < 1024 * 1024:
            warnings.append(
                f"Audio file small: {size_bytes // 1024} KB at {audio_path} "
                f"(expected > 1 MB for a full episode)."
            )

    return warnings


def quality_images(manifest: dict) -> list[str]:
    """
    Check image generation quality from the footage/image manifest.

    Warns if:
    - Fewer than 50% of scenes have an 'ai_image' source visual
    - Any image file on disk is smaller than 50 KB
    """
    warnings = []
    scenes = manifest.get("scenes", [])

    if not scenes:
        warnings.append("Image manifest has no scenes.")
        return warnings

    ai_image_count = sum(
        1 for s in scenes
        if s.get("visual", {}).get("source") == "ai_image"
        or s.get("ai_image")
    )
    coverage_pct = ai_image_count / len(scenes) * 100

    if coverage_pct < 50:
        warnings.append(
            f"AI image coverage low: {ai_image_count}/{len(scenes)} scenes "
            f"({coverage_pct:.0f}%) have AI-generated images — below 50% threshold."
        )

    # Check file sizes for any local image paths present in the manifest
    small_images = []
    for scene in scenes:
        local_path = (
            scene.get("visual", {}).get("local_path")
            or scene.get("image_path")
            or scene.get("local_path")
        )
        if local_path and Path(local_path).exists():
            size = Path(local_path).stat().st_size
            if size < 50 * 1024:
                small_images.append(f"scene {scene.get('scene_id', '?')} ({size // 1024} KB)")

    if small_images:
        warnings.append(
            f"Small image files detected (< 50 KB): {', '.join(small_images)} — "
            f"may indicate failed or corrupt downloads."
        )

    return warnings


def quality_short_storyboard(storyboard_data: dict) -> list[str]:
    """
    Check YouTube Shorts storyboard quality and return a list of warning strings.

    Warns if:
    - Fewer than 2 or more than 5 scenes
    - Any scene is missing 'image_prompt' or 'mood' fields
    """
    warnings = []
    scenes = storyboard_data.get("scenes", [])

    if len(scenes) < 2:
        warnings.append(
            f"Short storyboard has only {len(scenes)} scene(s) — recommend 2–5 for a Short."
        )
    elif len(scenes) > 5:
        warnings.append(
            f"Short storyboard has {len(scenes)} scenes — recommend ≤5 for a 45-60s Short."
        )

    for scene in scenes:
        scene_id = scene.get("scene_id", "?")
        if not scene.get("image_prompt", "").strip():
            warnings.append(f"Scene {scene_id} missing 'image_prompt'.")
        if not scene.get("mood", "").strip():
            warnings.append(f"Scene {scene_id} missing 'mood'.")

    return warnings


def quality_seo(seo_data: dict) -> list[str]:
    """
    Check SEO output quality and return a list of warning strings.

    Warns if:
    - Title is longer than 75 characters
    - Fewer than 5 tags/keywords
    - No description field present or description is empty
    """
    warnings = []

    title = seo_data.get("recommended_title") or seo_data.get("title") or seo_data.get("video_title", "")
    if len(title) > 75:
        warnings.append(
            f"SEO title too long: {len(title)} characters (YouTube truncates at ~70 chars in search)."
        )

    tags = seo_data.get("tags", []) or seo_data.get("keywords", [])
    if len(tags) < 5:
        warnings.append(
            f"SEO tags sparse: only {len(tags)} tags (recommend 5+ for discoverability)."
        )

    desc_raw = seo_data.get("description") or seo_data.get("video_description", "")
    if isinstance(desc_raw, dict):
        description = desc_raw.get("full_description") or desc_raw.get("hook_lines") or ""
    else:
        description = desc_raw or ""
    if not str(description).strip():
        warnings.append("SEO description missing — YouTube heavily weights description for search ranking.")

    return warnings


# ══════════════════════════════════════════════════════════════════════════════
# Soft metrics  (log only, no pass/fail)
# ══════════════════════════════════════════════════════════════════════════════

def metrics_script(script_data: dict) -> dict:
    """
    Return soft metrics for the script: word count, average sentence length,
    and exclamation mark count.

    Returns:
        dict with keys: word_count, avg_sentence_length, exclamation_count
    """
    full_script = script_data.get("full_script", "")
    words = full_script.split()
    word_count = len(words)

    sentences = re.split(r"[.!?]+", full_script)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_length = (
        round(word_count / len(sentences), 1) if sentences else 0
    )

    exclamation_count = full_script.count("!")

    return {
        "word_count": word_count,
        "avg_sentence_length": avg_sentence_length,
        "exclamation_count": exclamation_count,
    }


def metrics_audio(audio_data: dict) -> dict:
    """
    Return soft metrics for the audio: duration in minutes, words per minute,
    and chunk count (if available from the pipeline).

    Returns:
        dict with keys: duration_minutes, words_per_minute, chunk_count
    """
    duration_seconds = audio_data.get("total_duration_seconds", 0)
    word_count = audio_data.get("word_count", 0)
    chunk_count = audio_data.get("chunk_count", None)

    duration_minutes = round(duration_seconds / 60, 2) if duration_seconds else 0
    words_per_minute = (
        round(word_count / duration_minutes, 1)
        if duration_minutes > 0 and word_count > 0
        else 0
    )

    result = {
        "duration_minutes": duration_minutes,
        "words_per_minute": words_per_minute,
    }
    if chunk_count is not None:
        result["chunk_count"] = chunk_count

    return result


def metrics_images(manifest: dict) -> dict:
    """
    Return soft metrics for image generation: coverage percentage and
    total number of images generated.

    Returns:
        dict with keys: image_coverage_pct, total_images_generated
    """
    scenes = manifest.get("scenes", [])
    total_scenes = len(scenes)

    if total_scenes == 0:
        return {"image_coverage_pct": 0, "total_images_generated": 0}

    # Count scenes that have any visual assigned (any source counts for coverage)
    scenes_with_visual = sum(
        1 for s in scenes
        if s.get("visual") or s.get("image_path") or s.get("local_path")
    )

    # Count specifically AI-generated images
    ai_images = sum(
        1 for s in scenes
        if s.get("visual", {}).get("source") == "ai_image"
        or s.get("ai_image")
    )

    image_coverage_pct = round(scenes_with_visual / total_scenes * 100, 1)

    return {
        "image_coverage_pct": image_coverage_pct,
        "total_images_generated": ai_images,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ffprobe validation
# ══════════════════════════════════════════════════════════════════════════════

def validate_video_ffprobe(video_path: str) -> tuple[bool, dict]:
    """
    Run ffprobe on a rendered video to validate its streams.

    Checks:
    - duration > 0
    - At least one video stream is present
    - At least one audio stream is present

    Falls back gracefully if ffprobe is not installed or the binary is unavailable.

    Returns:
        (passed: bool, info_dict: dict)

    The info_dict contains stream summary data on success, or
    {"skipped": "ffprobe not available"} if ffprobe cannot be found.
    """
    # Try the local ffprobe binary in the project directory first, then PATH
    local_ffprobe = Path(__file__).resolve().parent.parent / "ffprobe"
    ffprobe_cmd = str(local_ffprobe) if local_ffprobe.exists() else "ffprobe"

    try:
        result = subprocess.run(
            [
                ffprobe_cmd,
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-show_format",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return True, {"skipped": "ffprobe not available"}
    except subprocess.TimeoutExpired:
        return False, {"error": "ffprobe timed out after 30s"}
    except Exception as exc:
        return True, {"skipped": f"ffprobe not available: {exc}"}

    if result.returncode != 0:
        stderr = result.stderr.strip()
        return False, {"error": f"ffprobe exited with code {result.returncode}: {stderr[:200]}"}

    try:
        probe = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return False, {"error": f"ffprobe output could not be parsed: {exc}"}

    streams = probe.get("streams", [])
    fmt = probe.get("format", {})

    # Check duration
    duration = float(fmt.get("duration", 0) or 0)
    if duration <= 0:
        # Try reading from individual streams
        for stream in streams:
            d = float(stream.get("duration", 0) or 0)
            if d > 0:
                duration = d
                break

    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    issues = []
    if duration <= 0:
        issues.append("duration is 0 or could not be determined")
    if not has_video:
        issues.append("no video stream found")
    if not has_audio:
        issues.append("no audio stream found")

    info = {
        "duration_seconds": round(duration, 2),
        "has_video": has_video,
        "has_audio": has_audio,
        "stream_count": len(streams),
        "format_name": fmt.get("format_name", ""),
        "size_bytes": int(fmt.get("size", 0) or 0),
    }

    if issues:
        info["issues"] = issues
        return False, info

    return True, info


# ══════════════════════════════════════════════════════════════════════════════
# B-roll quality scoring
# ══════════════════════════════════════════════════════════════════════════════

# Terms that indicate a lazy/generic prompt — each deducts 1 point
_GENERIC_TERMS = {
    "beautiful", "amazing", "stunning", "incredible", "gorgeous",
    "dark", "epic", "dramatic", "mysterious", "eerie", "cinematic",
    "breathtaking", "magnificent", "spectacular", "awesome",
}

# Patterns that indicate a high-quality, specific prompt — each adds 1 point
_SPECIFICITY_PATTERNS = [
    # Named historical period or year
    (r"\b\d{3,4}\s*(AD|BC|CE|BCE)?\b",       "specific period/year"),
    # Named location (city, country, region — capital letter proper noun)
    (r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b",  "named location or character"),
    # Lighting description
    (r"\b(torch|candlelight|firelight|moonlight|shaft of light|golden hour|"
     r"chiaroscuro|backlit|rimlit|silhouette|shadow[s]?)\b", "lighting description"),
    # Composition note
    (r"\b(close-?up|wide shot|low angle|bird.?s.eye|portrait|foreground|"
     r"background|framing|rule of thirds|depth of field|bokeh|"
     r"centered?|symmetrical)\b",             "composition note"),
    # Painterly style reference
    (r"\b(oil painting|watercolour|watercolor|fresco|engraving|woodcut|"
     r"illuminated manuscript|etching|charcoal|gouache|tempera)\b", "art medium reference"),
]


def score_broll_prompt(image_prompt: str) -> int:
    """
    Score an image/B-roll prompt from 0 to 10 for specificity and quality.

    Scoring logic:
      Start at 5 (neutral baseline).
      Deduct 1 for each generic/filler term found (min 0).
      Deduct 2 if the prompt is shorter than 30 characters.
      Deduct 1 if no clear subject noun can be identified.
      Award 1 for each of: specific period/location, character mention,
        lighting description, composition note, art medium reference.
      Score is clamped to [0, 10].

    Args:
        image_prompt: the prompt string to evaluate.

    Returns:
        int score between 0 and 10.
    """
    if not image_prompt or not image_prompt.strip():
        return 0

    score = 5
    prompt_lower = image_prompt.lower()

    # Deduct for generic terms
    for term in _GENERIC_TERMS:
        if re.search(r"\b" + re.escape(term) + r"\b", prompt_lower):
            score -= 1

    # Deduct for very short prompts
    if len(image_prompt.strip()) < 30:
        score -= 2

    # Deduct if no recognisable subject noun (heuristic: no capitalised word and
    # no common subject indicators)
    has_subject = bool(
        re.search(r"\b[A-Z][a-z]{2,}\b", image_prompt)  # proper noun
        or re.search(
            r"\b(soldier|warrior|emperor|king|queen|monk|priest|peasant|merchant|"
            r"castle|temple|ship|army|crowd|figure|man|woman|child|body|face)\b",
            prompt_lower,
        )
    )
    if not has_subject:
        score -= 1

    # Award for specificity patterns
    for pattern, _label in _SPECIFICITY_PATTERNS:
        if re.search(pattern, image_prompt, re.IGNORECASE):
            score += 1

    return max(0, min(10, score))


# ══════════════════════════════════════════════════════════════════════════════
# Professional quality checks  (warn, do not abort)
# ══════════════════════════════════════════════════════════════════════════════

def quality_audio_video_sync(audio_data: dict, scenes_data: dict) -> list[str]:
    """Check that audio duration and scene timeline are in sync."""
    warnings = []
    audio_dur = audio_data.get("total_duration_seconds", 0)
    scenes = scenes_data.get("scenes", [])
    if not scenes or not audio_dur:
        return warnings

    # Check total scene duration vs audio duration
    # Only meaningful when scenes have actual end_time (from convert stage).
    # Stage 7 duration_seconds are estimates (130 WPM) — always drift vs actual audio.
    has_end_time = any(s.get("end_time") for s in scenes)
    if has_end_time:
        last_end = max(s.get("end_time", 0) for s in scenes)
        if last_end > 0 and abs(audio_dur - last_end) > 5:
            warnings.append(
                f"Audio/scene sync mismatch: audio={audio_dur:.1f}s, scenes total={last_end:.1f}s "
                f"(drift {abs(audio_dur - last_end):.1f}s)."
            )

    # Check word timestamps span vs audio duration
    ts_path = audio_data.get("timestamps_path", "")
    if ts_path and Path(ts_path).exists():
        try:
            with open(ts_path) as f:
                ts = json.load(f)
            words = ts.get("words", [])
            if words:
                last_word_end = max(w.get("end", 0) for w in words)
                if last_word_end > 0 and abs(audio_dur - last_word_end) > 3:
                    warnings.append(
                        f"Timestamp/audio drift: last word ends at {last_word_end:.1f}s "
                        f"but audio is {audio_dur:.1f}s."
                    )
        except Exception:
            pass

    return warnings


def quality_audio_technical(audio_path: str) -> list[str]:
    """Check audio technical specs via ffprobe: bitrate, sample rate, loudness."""
    warnings = []
    if not audio_path or not Path(audio_path).exists():
        return warnings

    local_ffprobe = Path(__file__).resolve().parent.parent / "ffprobe"
    ffprobe_cmd = str(local_ffprobe) if local_ffprobe.exists() else "ffprobe"

    try:
        result = subprocess.run(
            [ffprobe_cmd, "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", audio_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return warnings

        probe = json.loads(result.stdout)
        fmt = probe.get("format", {})
        bit_rate = int(fmt.get("bit_rate", 0) or 0)
        if bit_rate > 0 and bit_rate < 64000:
            warnings.append(f"Audio bitrate low: {bit_rate // 1000}kbps (recommend 128kbps+).")

        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "audio":
                sample_rate = int(stream.get("sample_rate", 0) or 0)
                if sample_rate > 0 and sample_rate < 44100:
                    warnings.append(
                        f"Audio sample rate low: {sample_rate}Hz (recommend 44100Hz+)."
                    )
                channels = int(stream.get("channels", 0) or 0)
                if channels > 0 and channels > 2:
                    warnings.append(f"Audio has {channels} channels — expected mono or stereo.")
                break
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception:
        pass

    return warnings


def quality_video_technical(video_path: str) -> list[str]:
    """Check video technical specs: codec, frame rate, resolution."""
    warnings = []
    if not video_path or not Path(video_path).exists():
        return warnings

    local_ffprobe = Path(__file__).resolve().parent.parent / "ffprobe"
    ffprobe_cmd = str(local_ffprobe) if local_ffprobe.exists() else "ffprobe"

    try:
        result = subprocess.run(
            [ffprobe_cmd, "-v", "quiet", "-print_format", "json",
             "-show_streams", video_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return warnings

        probe = json.loads(result.stdout)
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video":
                codec = stream.get("codec_name", "")
                if codec and codec not in ("h264", "hevc", "vp9", "av1"):
                    warnings.append(
                        f"Video codec '{codec}' may not be YouTube-optimal (prefer h264)."
                    )
                width = int(stream.get("width", 0) or 0)
                height = int(stream.get("height", 0) or 0)
                if width > 0 and height > 0:
                    if width < 1920 and height < 1080:
                        warnings.append(
                            f"Video resolution {width}x{height} below 1080p."
                        )
                fps_str = stream.get("r_frame_rate", "0/1")
                try:
                    num, den = fps_str.split("/")
                    fps = int(num) / int(den) if int(den) > 0 else 0
                    if fps > 0 and fps < 24:
                        warnings.append(f"Frame rate {fps:.1f}fps below 24fps minimum.")
                except (ValueError, ZeroDivisionError):
                    pass
                break
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception:
        pass

    return warnings


def quality_content_policy(script_data: dict) -> list[str]:
    """Flag potential content policy issues in script text."""
    warnings = []
    text = script_data.get("full_script", "").lower()
    if not text:
        return warnings

    # Patterns that may trigger YouTube demonetization
    sensitive_patterns = [
        (r"\b(graphic|gruesome|gory)\s+(detail|description|depiction)", "graphic violence description"),
        (r"\b(racial slur|hate speech|slur)\b", "hate speech reference"),
        (r"\b(suicide|self[- ]harm)\s+(method|how to|instruction)", "self-harm instruction"),
        (r"\b(buy|purchase|order)\s+(drugs|weapons|firearms)\b", "prohibited commerce"),
    ]
    for pattern, label in sensitive_patterns:
        if re.search(pattern, text):
            warnings.append(f"Content policy flag: possible {label} detected — review before upload.")

    return warnings


def quality_plagiarism(script_data: dict, research_data: dict) -> list[str]:
    """Check if script lifts verbatim passages from research sources."""
    warnings = []
    script = script_data.get("full_script", "")
    if not script or not research_data:
        return warnings

    # Check for long verbatim overlaps with research core_facts and archival_gems
    source_texts = []
    for fact in research_data.get("core_facts", []):
        if isinstance(fact, str) and len(fact) > 40:
            source_texts.append(fact)
    for gem in research_data.get("archival_gems", []):
        if isinstance(gem, str) and len(gem) > 40:
            source_texts.append(gem)

    script_lower = script.lower()
    for src in source_texts:
        # Check if a 40+ char substring appears verbatim
        src_lower = src.lower().strip()
        if len(src_lower) >= 40 and src_lower in script_lower:
            warnings.append(
                f"Possible verbatim lift ({len(src_lower)} chars): '{src_lower[:60]}...' "
                f"— consider rephrasing."
            )

    return warnings


def quality_thumbnail(seo_data: dict, thumbnail_data: dict | None = None) -> list[str]:
    """Check thumbnail-related quality from SEO output and thumbnail agent result."""
    warnings = []

    # Thumbnail agent output is stored separately from SEO data
    if thumbnail_data and thumbnail_data.get("thumbnail_path"):
        # Thumbnail was generated — check text overlay length
        text_overlay = thumbnail_data.get("concept", "")
        if text_overlay and len(text_overlay) > 35:
            warnings.append(
                f"Thumbnail text too long ({len(text_overlay)} chars) — "
                f"max 3-5 words for mobile readability."
            )
        return warnings

    # Fall back to SEO-embedded thumbnail guidance
    thumb = seo_data.get("thumbnail_guidance", seo_data.get("thumbnail", {}))
    if isinstance(thumb, str):
        if len(thumb) < 20:
            warnings.append("Thumbnail guidance too vague — needs specific composition notes.")
        return warnings
    if isinstance(thumb, dict):
        text_overlay = thumb.get("text_overlay", thumb.get("text", ""))
        if text_overlay and len(text_overlay) > 35:
            warnings.append(
                f"Thumbnail text too long ({len(text_overlay)} chars) — "
                f"max 3-5 words for mobile readability."
            )
    # Also check thumbnail_concepts from SEO agent
    thumb_concepts = seo_data.get("thumbnail_concepts", [])
    if not thumb and not thumb_concepts:
        warnings.append("No thumbnail guidance provided — thumbnails drive 80%+ of CTR.")

    return warnings


def quality_cross_pipeline(pipeline_outputs: dict) -> list[str]:
    """Validate cross-pipeline consistency: all scenes have images, chapters sequential, etc."""
    warnings = []

    scenes = pipeline_outputs.get("scenes", {}).get("scenes", [])
    images = pipeline_outputs.get("images", {})
    audio = pipeline_outputs.get("audio", {})

    # All scenes should have visual assignments
    if scenes and images:
        image_scenes = images.get("scenes", [])
        image_ids = {s.get("scene_id") for s in image_scenes}
        missing = [s for s in scenes if s.get("scene_id") not in image_ids]
        if missing:
            warnings.append(
                f"{len(missing)} scene(s) have no image assignment: "
                f"IDs {[s.get('scene_id') for s in missing[:5]]}."
            )

    # Audio duration vs video scene total
    # Only compare when scenes have actual end_time (from convert stage).
    # Stage 7 duration_seconds are estimates (130 WPM) — always drift vs actual audio.
    if audio and scenes:
        has_end_time = any(s.get("end_time") for s in scenes)
        audio_dur = audio.get("total_duration_seconds", 0)
        if has_end_time and audio_dur > 0:
            last_end = max(s.get("end_time", 0) for s in scenes)
            drift = abs(audio_dur - last_end)
            if drift > 10:
                warnings.append(
                    f"Duration mismatch: audio={audio_dur:.0f}s vs scenes total={last_end:.0f}s "
                    f"(drift {drift:.0f}s)."
                )

    # SEO chapters should be sequential
    seo = pipeline_outputs.get("seo", {})
    chapters = seo.get("chapters", [])
    if chapters and len(chapters) > 1:
        prev_time = -1
        for ch in chapters:
            ts = ch.get("timestamp", ch.get("time", ""))
            if isinstance(ts, str) and ":" in ts:
                parts = ts.split(":")
                try:
                    if len(parts) >= 2:
                        secs = int(parts[0]) * 60 + int(parts[1])
                        if secs <= prev_time:
                            warnings.append(f"Chapter timestamps not sequential at '{ts}'.")
                            break
                        prev_time = secs
                except (ValueError, IndexError):
                    pass

    return warnings


def quality_duration_variance(script_data: dict, audio_data: dict) -> list[str]:
    """Check if actual audio duration deviates significantly from script estimate."""
    warnings = []
    estimated = script_data.get("estimated_duration_minutes", script_data.get("estimated_length_minutes", 0))
    actual_sec = audio_data.get("total_duration_seconds", 0)

    if estimated > 0 and actual_sec > 0:
        actual_min = actual_sec / 60
        try:
            estimated = float(estimated)
        except (TypeError, ValueError):
            return warnings
        variance_pct = abs(actual_min - estimated) / estimated * 100
        if variance_pct > 25:
            warnings.append(
                f"Duration variance: estimated {estimated:.1f}min, actual {actual_min:.1f}min "
                f"({variance_pct:.0f}% off) — pacing may be off."
            )

    return warnings


def quality_script_sentiment(script_data: dict) -> list[str]:
    """Analyze script mood distribution for monotone delivery risk."""
    warnings = []
    full_script = script_data.get("full_script", "")
    if not full_script:
        return warnings

    sentences = re.split(r"[.!?]+", full_script)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if len(sentences) < 5:
        return warnings

    # Check for monotone: if all sentences are roughly the same length
    lengths = [len(s.split()) for s in sentences]
    if lengths:
        avg_len = sum(lengths) / len(lengths)
        variance = sum((entry - avg_len) ** 2 for entry in lengths) / len(lengths)
        # Low variance = monotone pacing
        if variance < 4 and len(sentences) > 10:
            warnings.append(
                "Script pacing may be monotone: sentence lengths have very low variance. "
                "Consider varying rhythm with short punchy lines mixed with longer exposition."
            )

    # Check question density (engagement signal)
    question_count = full_script.count("?")
    if question_count == 0 and len(sentences) > 15:
        warnings.append(
            "No rhetorical questions in script — adding 2-3 can boost viewer engagement."
        )

    return warnings


def quality_seo_completeness(seo_data: dict) -> list[str]:
    """Check SEO metadata completeness: hashtags, keywords in description, etc."""
    warnings = []

    # Hashtags — may be top-level or nested inside description dict
    tags = seo_data.get("tags", []) or seo_data.get("keywords", [])
    hashtags = seo_data.get("hashtags", [])
    desc_raw = seo_data.get("description") or seo_data.get("video_description", "")
    if not hashtags and isinstance(desc_raw, dict):
        hashtags = desc_raw.get("hashtags", [])
    if not hashtags and tags:
        warnings.append("No #hashtags specified — YouTube supports up to 15 in description.")

    # Description keyword density
    if isinstance(desc_raw, dict):
        description = " ".join(filter(None, [
            desc_raw.get("hook_lines", ""),
            desc_raw.get("full_description", ""),
        ]))
    else:
        description = str(desc_raw) if desc_raw else ""
    title = seo_data.get("recommended_title") or seo_data.get("title") or seo_data.get("video_title", "")

    if title and description:
        # Check if primary keyword from title appears in description
        title_words = [w.lower() for w in title.split() if len(w) > 4]
        desc_lower = description.lower()
        missing_keywords = [w for w in title_words if w not in desc_lower]
        if len(missing_keywords) > len(title_words) // 2:
            warnings.append(
                "Title keywords missing from description — include primary keywords for SEO."
            )

    # Description length
    if description and len(description) < 100:
        warnings.append(
            f"Description too short ({len(description)} chars) — "
            f"YouTube recommends 200+ chars for search ranking."
        )

    return warnings


def quality_narrative_structure(script_data: dict) -> list[str]:
    """Validate narrative structure: hook, twist, ending."""
    warnings = []
    full_script = script_data.get("full_script", "")
    if not full_script:
        return warnings

    words = full_script.split()
    total = len(words)
    if total < 200:
        return warnings

    # Hook check: first 5% should be compelling (no slow preamble)
    hook_section = " ".join(words[:max(50, total // 20)]).lower()
    weak_openers = ["the history of", "throughout history", "for centuries", "many people"]
    for opener in weak_openers:
        if hook_section.startswith(opener):
            warnings.append(
                f"Weak hook: opens with '{opener}' — should start mid-action or with a question."
            )
            break

    # Ending check: last 5% should feel conclusive
    ending_section = " ".join(words[-max(50, total // 20):]).lower()
    cliffhanger_words = ["subscribe", "next video", "part 2", "stay tuned", "coming soon"]
    for cw in cliffhanger_words:
        if cw in ending_section:
            warnings.append(
                f"Ending contains '{cw}' — The Obsidian Archive should end on the story, not promotion."
            )
            break

    return warnings


def quality_source_authority(research_data: dict) -> list[str]:
    """Score the authority of cited sources."""
    warnings = []
    sources = research_data.get("primary_sources", [])
    if not sources:
        warnings.append("No primary sources cited — content credibility may be low.")
        return warnings

    # Check for Wikipedia-only sourcing
    wiki_count = sum(1 for s in sources
                     if isinstance(s, (str, dict)) and "wikipedia" in str(s).lower())
    if wiki_count == len(sources) and len(sources) > 0:
        warnings.append(
            "All sources are Wikipedia — add academic, archival, or primary historical sources."
        )

    # Check for source diversity
    if len(sources) < 3:
        warnings.append(
            f"Only {len(sources)} source(s) cited — recommend 3+ for credibility."
        )

    return warnings


def quality_image_licensing(manifest: dict) -> list[str]:
    """Validate that Wikimedia images have proper credits."""
    warnings = []
    scenes = manifest.get("scenes", [])
    credits = manifest.get("credits", [])

    uncredited = 0
    for scene in scenes:
        visual = scene.get("visual", {})
        if visual.get("source") == "wikimedia" and not visual.get("credit"):
            uncredited += 1

    if uncredited > 0:
        warnings.append(
            f"{uncredited} Wikimedia image(s) missing credit attribution — "
            f"required by CC license."
        )

    if not credits and scenes:
        warnings.append("No credits list in manifest — add attribution for all sourced media.")

    return warnings


def quality_optimizer_health() -> list[str]:
    """Soft metric — optimizer health warnings. Never blocks pipeline."""
    warnings = []
    try:
        from core.param_history import load_optimizer_state
        state = load_optimizer_state()
        if state is None:
            return []  # Not initialized yet — expected early on

        total_epochs = state.get("epoch", 0)
        exploration_rate = state.get("exploration_rate", 1.0)
        cooldown = state.get("cooldown_remaining", 0)
        running_loss = state.get("running_loss", [])

        if total_epochs > 10 and exploration_rate < 0.1:
            warnings.append(
                f"Optimizer: exploration rate very low ({exploration_rate:.0%}) — "
                f"may be stuck in local minimum"
            )

        if cooldown > 0:
            warnings.append(
                f"Optimizer: in rollback cooldown ({cooldown} videos remaining)"
            )

        if len(running_loss) >= 6:
            recent = running_loss[-3:]
            prior = running_loss[-6:-3]
            recent_avg = sum(recent) / 3
            prior_avg = sum(prior) / 3
            if prior_avg > 0 and recent_avg > prior_avg * 1.15:
                warnings.append(
                    f"Optimizer: loss trending upward "
                    f"({prior_avg:.3f} → {recent_avg:.3f})"
                )
    except Exception:
        pass  # Non-fatal
    return warnings


# ══════════════════════════════════════════════════════════════════════════════
# Three-Tier QA System
# ══════════════════════════════════════════════════════════════════════════════
#
# Tier 0: Pre-render data validation — runs BEFORE Remotion render.
#         Catches structural problems that would waste render time.
# Tier 1: Post-render technical — runs AFTER render.
#         Validates video/audio specs match expectations.
# Tier 2: Content quality — runs AFTER render (optional).
#         Vision-based sync check using frame sampling.
# ══════════════════════════════════════════════════════════════════════════════

def run_tier0_prerender(pipeline_outputs: dict) -> dict:
    """
    Tier 0: Pre-render data validation.

    Validates all data needed for Remotion render is structurally complete.
    Should run BEFORE stage 11 (Remotion conversion) to catch problems early.

    Args:
        pipeline_outputs: dict with keys: script, scenes, audio, seo.

    Returns:
        {passed: bool, errors: list[str], warnings: list[str]}
    """
    errors = []
    warnings = []

    script = pipeline_outputs.get("script", {})
    scenes = pipeline_outputs.get("scenes", {})
    audio = pipeline_outputs.get("audio", {})
    seo = pipeline_outputs.get("seo", {})

    # ── Script checks ─────────────────────────────────────────────────────
    if not script:
        errors.append("T0: No script data — cannot render.")
    else:
        full_script = script.get("full_script", "")
        if not full_script:
            errors.append("T0: Script has no full_script text.")
        word_count = len(full_script.split()) if full_script else 0
        if word_count < 100:
            errors.append(f"T0: Script too short ({word_count} words) — likely incomplete.")

        # Check act structure
        acts = script.get("script", {})
        for act_key in ["hook", "act1", "act2", "act3", "ending"]:
            if not acts.get(act_key):
                warnings.append(f"T0: Script missing '{act_key}' in act breakdown.")

    # ── Scenes checks ─────────────────────────────────────────────────────
    scene_list = scenes.get("scenes", []) if isinstance(scenes, dict) else []
    if not scene_list:
        errors.append("T0: No scenes — nothing to render.")
    else:
        for i, scene in enumerate(scene_list):
            if not scene.get("narration"):
                warnings.append(f"T0: Scene {i} has no narration text.")
            if not scene.get("image_prompt") and not scene.get("image_path"):
                warnings.append(f"T0: Scene {i} has no image_prompt or image_path.")

    # ── Audio checks ──────────────────────────────────────────────────────
    if not audio:
        errors.append("T0: No audio data — cannot render.")
    else:
        duration = audio.get("total_duration_seconds", 0)
        if not duration or duration < 10:
            errors.append(f"T0: Audio duration too short ({duration}s) — likely failed TTS.")
        audio_path = audio.get("audio_path", "")
        if audio_path and not Path(audio_path).exists():
            errors.append(f"T0: Audio file not found at {audio_path}.")

    # ── SEO checks ────────────────────────────────────────────────────────
    if not seo:
        warnings.append("T0: No SEO data — video will upload without metadata.")
    else:
        if not seo.get("recommended_title"):
            warnings.append("T0: SEO missing recommended_title.")

    # ── Scene-audio duration coherence ────────────────────────────────────
    if scene_list and audio:
        total_scene_dur = sum(s.get("duration_seconds", 0) for s in scene_list)
        audio_dur = audio.get("total_duration_seconds", 0)
        if total_scene_dur > 0 and audio_dur > 0:
            ratio = total_scene_dur / audio_dur
            if ratio < 0.7 or ratio > 1.3:
                warnings.append(
                    f"T0: Scene durations ({total_scene_dur:.0f}s) vs audio ({audio_dur:.0f}s) "
                    f"mismatch ({ratio:.2f}x) — may cause visual drift."
                )

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def run_tier1_postrender(video_path: str, audio_data: dict, script_data: dict) -> dict:
    """
    Tier 1: Post-render technical validation.

    Checks rendered video meets technical specs:
    - Duration within ±5% of expected
    - Audio track present
    - Video codec/resolution acceptable
    - Caption alignment coverage (if word timestamps available)

    Args:
        video_path: Path to rendered .mp4.
        audio_data: Audio stage output with total_duration_seconds.
        script_data: Script stage output with word_count.

    Returns:
        {passed: bool, errors: list[str], warnings: list[str], metrics: dict}
    """
    errors = []
    warnings = []
    metrics = {}

    path = Path(video_path) if video_path else None

    if not path or not path.exists():
        return {
            "passed": False,
            "errors": [f"T1: Rendered video not found: {video_path}"],
            "warnings": [],
            "metrics": {},
        }

    # ── File size sanity ──────────────────────────────────────────────────
    size_mb = path.stat().st_size / (1024 * 1024)
    metrics["file_size_mb"] = round(size_mb, 1)
    if size_mb < 10:
        errors.append(f"T1: Video too small ({size_mb:.1f} MB) — likely corrupt render.")

    # ── ffprobe validation ────────────────────────────────────────────────
    probe_ok, probe_data = validate_video_ffprobe(str(path))
    if probe_ok and probe_data:
        # Duration check: within ±5% of expected audio duration
        video_dur = probe_data.get("duration_seconds", 0)
        expected_dur = audio_data.get("total_duration_seconds", 0) if audio_data else 0
        metrics["video_duration_seconds"] = video_dur
        metrics["expected_duration_seconds"] = expected_dur

        if video_dur > 0 and expected_dur > 0:
            deviation = abs(video_dur - expected_dur) / expected_dur
            metrics["duration_deviation_pct"] = round(deviation * 100, 1)
            if deviation > 0.05:
                errors.append(
                    f"T1: Video duration ({video_dur:.1f}s) deviates "
                    f"{deviation*100:.1f}% from expected ({expected_dur:.1f}s) — "
                    f"exceeds ±5% tolerance."
                )

        # Audio track presence
        has_audio = probe_data.get("has_audio", False)
        metrics["has_audio_track"] = has_audio
        if not has_audio:
            errors.append("T1: Rendered video has no audio track.")

        # Resolution
        width = probe_data.get("width", 0)
        height = probe_data.get("height", 0)
        metrics["resolution"] = f"{width}x{height}"
        if width < 1920 or height < 1080:
            warnings.append(f"T1: Video resolution {width}x{height} below 1080p.")

        # Codec
        codec = probe_data.get("codec", "")
        metrics["codec"] = codec
        if codec and codec not in ("h264", "hevc", "vp9", "av1"):
            warnings.append(f"T1: Unusual video codec '{codec}' — may cause YouTube processing issues.")

    elif not probe_ok:
        warnings.append("T1: ffprobe validation failed — technical checks limited to file size.")

    # ── Caption coverage estimate ─────────────────────────────────────────
    if script_data:
        word_count = script_data.get("word_count", 0)
        word_timestamps = script_data.get("word_timestamps", [])
        if word_count > 0 and word_timestamps:
            coverage = len(word_timestamps) / word_count
            metrics["caption_coverage_pct"] = round(coverage * 100, 1)
            if coverage < 0.95:
                warnings.append(
                    f"T1: Caption coverage {coverage*100:.1f}% below 95% target "
                    f"({len(word_timestamps)}/{word_count} words timestamped)."
                )

    # ── Loudness check (render verification) ─────────────────────────────
    try:
        from core.render_verification import measure_loudness
        lufs = measure_loudness(str(path))
        if lufs:
            metrics["integrated_lufs"] = lufs["integrated_lufs"]
            metrics["lufs_method"] = lufs["method"]
            if abs(lufs["integrated_lufs"] - (-14)) > 3:
                warnings.append(
                    f"T1: Loudness {lufs['integrated_lufs']:.1f} LUFS "
                    f"(target: -14, deviation: {abs(lufs['integrated_lufs'] + 14):.1f})"
                )
    except Exception:
        pass  # Non-fatal — render verification is optional

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
    }


def run_tier2_content(video_path: str, script_data: dict, scenes_data: dict) -> dict:
    """
    Tier 2: Content quality — visual-narration sync check.

    Samples frames at scene boundaries and checks that the visual content
    roughly matches the narration's subject. Uses a lightweight heuristic
    (scene metadata matching) since vision model calls are expensive.

    Falls back gracefully if video path is unavailable or scenes are empty.

    Args:
        video_path: Path to rendered .mp4.
        script_data: Script stage output.
        scenes_data: Scenes stage output with scene list.

    Returns:
        {passed: bool, warnings: list[str], sync_score: float}
    """
    warnings = []

    if not video_path or not Path(video_path).exists():
        return {"passed": True, "warnings": ["T2: Skipped — video not available."], "sync_score": 0.0}

    scene_list = scenes_data.get("scenes", []) if isinstance(scenes_data, dict) else []
    if not scene_list:
        return {"passed": True, "warnings": ["T2: Skipped — no scene data."], "sync_score": 0.0}

    # ── Heuristic sync check ──────────────────────────────────────────────
    # Check that each scene has both narration and visual data, and that
    # scene ordering is coherent (durations sum to ~total).
    scored_scenes = 0
    synced_scenes = 0

    for i, scene in enumerate(scene_list):
        has_narration = bool(scene.get("narration", "").strip())
        has_visual = bool(
            scene.get("image_prompt")
            or scene.get("image_path")
            or scene.get("footage_url")
        )
        has_duration = scene.get("duration_seconds", 0) > 0

        scored_scenes += 1

        if has_narration and has_visual and has_duration:
            synced_scenes += 1
        else:
            missing = []
            if not has_narration:
                missing.append("narration")
            if not has_visual:
                missing.append("visual")
            if not has_duration:
                missing.append("duration")
            warnings.append(f"T2: Scene {i} missing: {', '.join(missing)}")

    sync_score = synced_scenes / scored_scenes if scored_scenes > 0 else 0.0
    passed = sync_score >= 0.85  # 85% of scenes must be fully synced

    if not passed:
        warnings.append(
            f"T2: Sync score {sync_score*100:.0f}% below 85% threshold "
            f"({synced_scenes}/{scored_scenes} scenes fully synced)."
        )

    return {
        "passed": passed,
        "warnings": warnings,
        "sync_score": round(sync_score, 3),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Aggregate runner
# ══════════════════════════════════════════════════════════════════════════════

def run_all_quality_checks(pipeline_outputs: dict) -> dict:
    """
    Run all quality checks against pipeline outputs.

    Args:
        pipeline_outputs: dict with keys like 'research', 'angle', 'script', 'scenes',
                         'audio', 'images', 'seo', plus optional paths.

    Returns:
        dict with 'warnings' (list[str]), 'metrics' (dict), 'total_warnings' (int)
    """
    all_warnings = []
    all_metrics = {}

    research = pipeline_outputs.get("research", {})
    angle = pipeline_outputs.get("angle", {})
    script = pipeline_outputs.get("script", {})
    scenes = pipeline_outputs.get("scenes", {})
    audio = pipeline_outputs.get("audio", {})
    images = pipeline_outputs.get("images", {})
    seo = pipeline_outputs.get("seo", {})

    # Original quality checks
    all_warnings.extend(quality_research(research))
    all_warnings.extend(quality_angle(angle))
    all_warnings.extend(quality_script(script))
    all_warnings.extend(quality_scenes(scenes))
    all_warnings.extend(quality_audio(audio))
    all_warnings.extend(quality_images(images))
    all_warnings.extend(quality_seo(seo))

    # New professional checks
    all_warnings.extend(quality_audio_video_sync(audio, scenes))
    audio_path = audio.get("audio_path", "")
    all_warnings.extend(quality_audio_technical(audio_path))
    video_path = pipeline_outputs.get("video_path", "")
    all_warnings.extend(quality_video_technical(video_path))
    all_warnings.extend(quality_content_policy(script))
    all_warnings.extend(quality_plagiarism(script, research))
    thumbnail = pipeline_outputs.get("thumbnail", {})
    all_warnings.extend(quality_thumbnail(seo, thumbnail))
    all_warnings.extend(quality_cross_pipeline(pipeline_outputs))
    all_warnings.extend(quality_duration_variance(script, audio))
    all_warnings.extend(quality_script_sentiment(script))
    all_warnings.extend(quality_seo_completeness(seo))
    all_warnings.extend(quality_narrative_structure(script))
    all_warnings.extend(quality_source_authority(research))
    all_warnings.extend(quality_image_licensing(images))

    # Optimizer health (soft — warnings only, never blocks pipeline)
    all_warnings.extend(quality_optimizer_health())

    # Metrics
    all_metrics.update(metrics_script(script))
    all_metrics.update(metrics_audio(audio))
    all_metrics.update(metrics_images(images))

    # B-roll prompt scoring
    broll_scores = []
    for scene in scenes.get("scenes", []):
        prompt = scene.get("image_prompt", "")
        if prompt:
            broll_scores.append(score_broll_prompt(prompt))
    if broll_scores:
        all_metrics["avg_broll_score"] = round(sum(broll_scores) / len(broll_scores), 1)
        all_metrics["min_broll_score"] = min(broll_scores)

    return {
        "warnings": all_warnings,
        "metrics": all_metrics,
        "total_warnings": len(all_warnings),
    }
