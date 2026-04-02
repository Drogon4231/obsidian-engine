"""Stage output validators and quality checks — extracted from run_pipeline.py."""
import re
from pathlib import Path

from core.log import get_logger

logger = get_logger(__name__)


def validate_stage_output(stage_num, data):
    """Validate that a resumed stage's output has the minimum required keys."""
    if data is None:
        return False
    REQUIRED_KEYS = {
        1: ["core_facts", "key_figures"],
        2: ["chosen_angle"],
        3: ["hook", "act1", "act2", "act3"],
        4: ["full_script"],
        5: ["overall_verdict"],
        6: ["recommended_title"],
        7: ["scenes"],
        8: ["audio_path", "total_duration_seconds"],
        9: ["scenes"],       # footage manifest
        10: ["scenes"],      # image manifest
    }
    # Stages 11 (convert) and 12 (render) return strings (paths), not dicts
    if stage_num in (11, 12) and isinstance(data, str) and data:
        return True
    # Stage 11 can also return a dict with scenes + total_duration_seconds
    if stage_num == 11 and isinstance(data, dict):
        return bool(data.get("scenes") and data.get("total_duration_seconds"))
    # Stage 13 (upload) returns dict with video_id
    if stage_num == 13 and isinstance(data, dict) and data.get("video_id"):
        return True
    required = REQUIRED_KEYS.get(stage_num, [])
    if not required:
        return True
    if not isinstance(data, dict):
        return False
    missing = [k for k in required if not data.get(k)]
    if missing:
        logger.warning(f"[State] Stage {stage_num} output missing keys: {missing} — will re-run")
        return False
    return True


# ── Quality checks ───────────────────────────────────────────────────────────
def check_research(r):
    issues = []
    if len(r.get("core_facts", [])) < 5:
        issues.append("Fewer than 5 core facts")
    if len(r.get("key_figures", [])) < 2:
        issues.append("Fewer than 2 key figures")
    if not r.get("primary_sources"):
        issues.append("No primary sources found")
    return issues

def check_angle(a):
    issues = []
    if not a.get("chosen_angle"):
        issues.append("No chosen angle identified")
    if not a.get("angle_justification"):
        issues.append("No angle justification found")
    return issues

def check_blueprint(b):
    issues = []
    # 03_narrative_architect returns act1/act2/act3/hook/ending — not an "acts" array
    missing_acts = [k for k in ("act1", "act2", "act3") if not b.get(k)]
    if missing_acts:
        issues.append(f"Missing blueprint sections: {missing_acts}")
    if not b.get("hook"):
        issues.append("No hook section in blueprint")
    if not b.get("ending"):
        issues.append("No ending section in blueprint")
    return issues

def check_script(s):
    issues = []
    text = s.get("full_script", "")
    words = len(text.split())
    tier = s.get("length_tier", "STANDARD").upper()
    tier_max = {"STANDARD": 1500, "DEEP_DIVE": 2600, "EPIC": 3500}.get(tier, 2500)
    if words < 1000:
        issues.append(f"Script too short: {words} words (min 1000)")
    if words > tier_max:
        issues.append(f"Script too long: {words} words (max {tier_max} for {tier})")
    meta_patterns = r'(?i)(verification|approved|corrections|fact.check|agent\s+\d|pipeline)'
    if re.search(meta_patterns, text):
        issues.append("Meta/pipeline text found in script — will be stripped")
    return issues

def check_pacing(s):
    """Analyze script pacing — flag if too monotonous or too rushed."""
    issues = []
    text = s.get("full_script", "")
    sentences = [sent.strip() for sent in re.split(r'[.!?]+', text) if sent.strip()]
    if not sentences:
        return issues
    lengths = [len(sent.split()) for sent in sentences]
    avg_len = sum(lengths) / len(lengths)
    # Check for monotonous pacing (low variance in sentence length)
    if len(lengths) > 10:
        variance = sum((length - avg_len) ** 2 for length in lengths) / len(lengths)
        std_dev = variance ** 0.5
        if std_dev < 3:
            issues.append(f"Monotonous pacing: sentence length std_dev={std_dev:.1f} (target >5)")
    # Check for too many long sentences in a row
    long_streak = 0
    max_streak = 0
    for length in lengths:
        if length > 20:
            long_streak += 1
            max_streak = max(max_streak, long_streak)
        else:
            long_streak = 0
    if max_streak >= 5:
        issues.append(f"Pacing drag: {max_streak} consecutive long sentences (>20 words)")
    # Check short punchy sentences exist (documentary style)
    short_count = sum(1 for length in lengths if length <= 5)
    if short_count < len(sentences) * 0.1:
        issues.append(f"Low punch: only {short_count}/{len(sentences)} short sentences (<= 5 words)")
    return issues

def check_verification(v):
    issues = []
    verdict = v.get("overall_verdict", "")
    if "REJECTED" in verdict.upper():
        issues.append(f"Verification rejected: {verdict}")
    return issues

def check_seo(s):
    issues = []
    if not s.get("recommended_title"):
        issues.append("No title generated")
    if len(s.get("tags", [])) < 5:
        issues.append("Fewer than 5 tags")
    return issues

def check_scenes(s):
    issues = []
    if len(s.get("scenes", [])) < 5:
        issues.append("Fewer than 5 scenes")
    return issues

def check_audio(a):
    issues = []
    audio_path_str = a.get("audio_path") or ""
    if not audio_path_str:
        issues.append("Audio file path missing")
    else:
        audio_path = Path(audio_path_str)
        if not audio_path.exists():
            issues.append("Audio file not found")
        elif audio_path.stat().st_size < 1_000_000:
            issues.append("Audio file suspiciously small (<1MB)")
    duration = a.get("total_duration_seconds") or 0
    if duration < 300:
        issues.append(f"Audio too short: {duration:.0f}s (min 300s)")
    if duration > 1200:
        issues.append(f"Audio too long: {duration:.0f}s (max 1200s)")
    return issues

def check_render(output_path):
    issues = []
    p = Path(output_path)
    if not p.exists():
        issues.append("Rendered video not found")
    elif p.stat().st_size < 50_000_000:
        issues.append(f"Video suspiciously small: {p.stat().st_size//1024//1024}MB")
    return issues
