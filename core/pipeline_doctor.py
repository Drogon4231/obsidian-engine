"""
Pipeline Doctor — automatic failure diagnosis and retry.

Called by run_pipeline.py when any stage raises an exception.
Attempts to recover using categorized fix strategies before giving up.
Records every intervention in lessons_learned.json.
"""

import sys
import json
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.log import get_logger

logger = get_logger(__name__)

try:
    from core.pipeline_config import SCORING_THRESHOLDS, SCORING_CONFIG
except ImportError:
    SCORING_THRESHOLDS = {}
    SCORING_CONFIG = {}

BASE_DIR     = Path(__file__).resolve().parent.parent
LESSONS_FILE = BASE_DIR / "lessons_learned.json"

# ── Stages where a Claude-generated fallback is safe (pipeline can continue) ──
FALLBACK_SAFE_STAGES = {
    6,   # SEO — can use minimal title/tags
    9,   # Footage hunting — can return empty scene list
}

# ── Error category keywords ────────────────────────────────────────────────────
_CATEGORIES = {
    "rate_limit": ["rate_limit", "rate limit", "429", "too many requests",
                   "overloaded", "529"],
    "timeout":    ["timeout", "timed out", "read timeout", "connect timeout",
                   "readtimeout", "connectiontimeout"],
    "network":    ["connection", "network", "socket", "ssl", "certificate",
                   "connectionerror", "remotedisconnected"],
    "context":    ["context length", "too many tokens", "context_length_exceeded",
                   "max_tokens", "input is too long"],
    "quota":      ["quota", "quota_exceeded", "insufficient_quota",
                   "elevenlabs", "401 client error"],
    "json":       ["json", "jsondecodeerror", "parse error", "expecting value"],
    "not_found":  ["not found", "filenotfounderror", "no such file",
                   "no module named"],
}


def _check_scoring_config() -> list[str]:
    """Validate scoring thresholds for common misconfigurations."""
    issues = []
    if not SCORING_THRESHOLDS:
        return issues

    th = SCORING_THRESHOLDS

    # Quality multiplier range inverted
    q_min = th.get("quality_multiplier_min", 0.8)
    q_max = th.get("quality_multiplier_max", 1.2)
    if q_min >= q_max:
        issues.append(f"quality_multiplier_min ({q_min}) >= quality_multiplier_max ({q_max})")

    # Queue thresholds inverted
    q_low = th.get("queue_low_threshold", 5)
    q_high = th.get("queue_high_threshold", 15)
    if q_low >= q_high:
        issues.append(f"queue_low_threshold ({q_low}) >= queue_high_threshold ({q_high})")

    # Title word range inverted
    t_min = th.get("quality_min_title_words", 3)
    t_max = th.get("quality_max_title_words", 15)
    if t_min >= t_max:
        issues.append(f"quality_min_title_words ({t_min}) >= quality_max_title_words ({t_max})")

    # Traffic thresholds unreasonably high (would never trigger)
    for key in ("traffic_search_dominant_pct", "traffic_browse_dominant_pct", "traffic_suggested_dominant_pct"):
        val = th.get(key, 50)
        if val > 95:
            issues.append(f"{key} is {val}% — too high, signal will never fire")

    # Demographic threshold too high
    demo = th.get("demographic_min_audience_pct", 20)
    if demo > 50:
        issues.append(f"demographic_min_audience_pct is {demo}% — most countries won't reach this")

    # Conversion multiplier <= 1 (would always trigger "high")
    mult = th.get("sub_conversion_high_multiplier", 1.5)
    if mult <= 1.0:
        issues.append(f"sub_conversion_high_multiplier is {mult} — must be > 1.0 to be meaningful")

    # Queue minimum topics > max topics
    q_min_topics = th.get("queue_minimum_topics", 10)
    max_topics = SCORING_CONFIG.get("max_topics_per_discovery", 20)
    if q_min_topics > max_topics:
        issues.append(f"queue_minimum_topics ({q_min_topics}) > max_topics_per_discovery ({max_topics})")

    return issues


def _categorize(error: Exception) -> str:
    msg = (str(error) + " " + type(error).__name__).lower()
    for cat, keywords in _CATEGORIES.items():
        if any(kw in msg for kw in keywords):
            return cat
    return "unknown"


def _truncate_args(args: tuple):
    """Shorten long strings/lists inside args by ~30%. Returns None if nothing changed."""
    changed = False
    out = []
    for arg in args:
        if isinstance(arg, str) and len(arg) > 3000:
            out.append(arg[: int(len(arg) * 0.7)])
            changed = True
        elif isinstance(arg, dict):
            new_d = {}
            for k, v in arg.items():
                if isinstance(v, str) and len(v) > 3000:
                    new_d[k] = v[: int(len(v) * 0.7)]
                    changed = True
                elif isinstance(v, list) and len(v) > 20:
                    new_d[k] = v[:15]
                    changed = True
                else:
                    new_d[k] = v
            out.append(new_d)
        else:
            out.append(arg)
    return tuple(out) if changed else None


def _diagnose(stage_num: int, stage_name: str, error: Exception,
              tb: str, recent_logs: list) -> dict:
    """Ask Claude Haiku to diagnose the error and recommend a fix strategy."""
    try:
        from clients.claude_client import call_claude, HAIKU
        log_snippet = "\n".join((recent_logs or [])[-20:])
        return call_claude(
            system_prompt=(
                "You are a pipeline debugger for an automated YouTube video production system. "
                "A pipeline stage has failed. Diagnose the root cause and recommend the best fix. "
                "Return ONLY JSON with these keys:\n"
                '  "diagnosis": "1-2 sentence plain-English explanation",\n'
                '  "root_cause": "technical root cause",\n'
                '  "fix_strategy": one of ["retry", "retry_modified_input", "use_fallback", "abort"],\n'
                '  "reasoning": "why this strategy"\n'
                "Rules:\n"
                "  retry               → transient API/network hiccup, clean retry likely helps\n"
                "  retry_modified_input → input too large, malformed, or needs simplification\n"
                "  use_fallback        → non-critical stage, pipeline can continue with minimal output\n"
                "  abort               → data corruption, bad config, or logic bug — do not retry"
            ),
            user_prompt=(
                f"STAGE: {stage_num} — {stage_name}\n"
                f"ERROR TYPE: {type(error).__name__}\n"
                f"ERROR: {str(error)[:600]}\n"
                f"TRACEBACK (tail):\n{tb[-1200:]}\n"
                f"RECENT LOG:\n{log_snippet}"
            ),
            model=HAIKU,
            max_tokens=350,
            expect_json=True,
        )
    except Exception as e:
        logger.warning(f"[Doctor] Claude diagnosis unavailable: {e}")
        return {}


def _generate_fallback(stage_num: int, stage_name: str, error: Exception) -> object:
    """Ask Claude Haiku to produce a minimal valid output for a safe-to-skip stage."""
    if stage_num not in FALLBACK_SAFE_STAGES:
        return None
    try:
        from clients.claude_client import call_claude, HAIKU
        hints = {
            6: ('SEO stage',
                '{"recommended_title":"Untitled","video_title":"Untitled",'
                '"description":"","tags":[],"keywords":[]}'),
            9: ('Footage hunting stage',
                '{"scenes":[],"credits":[]}'),
        }
        hint_name, hint_example = hints[stage_num]
        return call_claude(
            system_prompt=(
                f"You are generating a minimal fallback JSON result for a failed {hint_name} "
                "in a YouTube video pipeline. The output must be structurally valid so the "
                "pipeline can continue. Keep all fields minimal but present."
            ),
            user_prompt=(
                f"Stage failed: {error}\n"
                f"Produce a minimal fallback JSON. Example structure: {hint_example}"
            ),
            model=HAIKU,
            max_tokens=400,
            expect_json=True,
        )
    except Exception as e:
        logger.error(f"[Doctor] Fallback generation failed: {e}")
        return None


def _record(stage_num: int, stage_name: str, error: Exception,
            strategy: str, outcome: str, diagnosis: dict = None,
            config_issues: list = None):
    """Append an intervention record to lessons_learned.json."""
    entry = {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "stage_num":  stage_num,
        "stage_name": stage_name,
        "error":      f"{type(error).__name__}: {str(error)[:300]}",
        "category":   _categorize(error),
        "strategy":   strategy,
        "outcome":    outcome,
    }
    if diagnosis:
        entry["diagnosis"]  = diagnosis.get("diagnosis", "")
        entry["root_cause"] = diagnosis.get("root_cause", "")
    if config_issues:
        entry["config_issues"] = config_issues
    try:
        data = {}
        if LESSONS_FILE.exists():
            with open(LESSONS_FILE) as f:
                data = json.load(f)
        interventions = data.setdefault("doctor_interventions", [])
        interventions.append(entry)
        data["doctor_interventions"] = interventions[-500:]  # keep last 500 for pattern recognition
        with open(LESSONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"[Doctor] Could not save lesson: {e}")


# ── Public API ─────────────────────────────────────────────────────────────────

def intervene(stage_num: int, stage_name: str, fn, args: tuple,
              error: Exception, recent_logs: list = None):
    """
    Try to recover from a stage failure. Returns the stage result if successful.
    Re-raises the original (or latest) exception if all recovery attempts fail.
    """
    tb       = traceback.format_exc()
    category = _categorize(error)

    logger.error(f"\n[Doctor] 🩺  Stage {stage_num} ({stage_name}) — {category} error detected")
    logger.error(f"[Doctor]     {type(error).__name__}: {str(error)[:200]}")

    # For topic discovery failures, also check scoring config
    config_issues = None
    if stage_num == 0:
        config_issues = _check_scoring_config() or None
        if config_issues:
            logger.warning("[Doctor] Scoring config issues detected:")
            for issue in config_issues:
                logger.warning(f"[Doctor]   • {issue}")

    # ── Rate limit: exponential back-off ──────────────────────────────────────
    if category == "rate_limit":
        for attempt in range(1, 3):
            wait = 60 * attempt
            logger.warning(f"[Doctor] Rate limit — sleeping {wait}s (attempt {attempt}/2)...")
            time.sleep(wait)
            try:
                result = fn(*args)
                logger.info("[Doctor] ✓ Recovered from rate limit")
                _record(stage_num, stage_name, error, "rate_limit_retry", "success", config_issues=config_issues)
                return result
            except Exception as e2:
                error = e2
                category = _categorize(e2)
        _record(stage_num, stage_name, error, "rate_limit_retry", "failed", config_issues=config_issues)
        raise error

    # ── Timeout / network: single retry after brief pause ─────────────────────
    if category in ("timeout", "network"):
        logger.warning(f"[Doctor] {category} error — sleeping 30s then retrying...")
        time.sleep(30)
        try:
            result = fn(*args)
            logger.info(f"[Doctor] ✓ Recovered from {category} error")
            _record(stage_num, stage_name, error, "network_retry", "success", config_issues=config_issues)
            return result
        except Exception as e2:
            _record(stage_num, stage_name, error, "network_retry", "failed", config_issues=config_issues)
            raise e2

    # ── Context length: truncate inputs and retry ─────────────────────────────
    if category == "context":
        modified = _truncate_args(args)
        if modified:
            logger.info("[Doctor] Context length — retrying with truncated inputs...")
            try:
                result = fn(*modified)
                logger.info("[Doctor] ✓ Recovered by truncating inputs")
                _record(stage_num, stage_name, error, "truncate_retry", "success", config_issues=config_issues)
                return result
            except Exception as e2:
                _record(stage_num, stage_name, error, "truncate_retry", "failed", config_issues=config_issues)
                raise e2

    # ── Ask Claude for diagnosis on anything else ─────────────────────────────
    diagnosis = _diagnose(stage_num, stage_name, error, tb, recent_logs)
    fix = diagnosis.get("fix_strategy", "abort") if diagnosis else "abort"

    if diagnosis:
        logger.info(f"[Doctor] Diagnosis: {diagnosis.get('diagnosis', 'no diagnosis')}")
        logger.info(f"[Doctor] Strategy:  {fix} — {diagnosis.get('reasoning', '')}")

    if fix == "retry":
        time.sleep(15)
        try:
            result = fn(*args)
            logger.info("[Doctor] ✓ Clean retry succeeded")
            _record(stage_num, stage_name, error, "retry", "success", diagnosis, config_issues=config_issues)
            return result
        except Exception as e2:
            _record(stage_num, stage_name, error, "retry", "failed", diagnosis, config_issues=config_issues)
            raise e2

    elif fix == "retry_modified_input":
        modified = _truncate_args(args)
        if modified:
            try:
                result = fn(*modified)
                logger.info("[Doctor] ✓ Modified-input retry succeeded")
                _record(stage_num, stage_name, error, "retry_modified_input", "success", diagnosis, config_issues=config_issues)
                return result
            except Exception as e2:
                error = e2  # propagate latest failure, not the original
        _record(stage_num, stage_name, error, "retry_modified_input", "failed", diagnosis, config_issues=config_issues)

    elif fix == "use_fallback":
        logger.info(f"[Doctor] Attempting fallback generation for Stage {stage_num}...")
        fallback = _generate_fallback(stage_num, stage_name, error)
        if fallback is not None:
            logger.info("[Doctor] ✓ Using Claude-generated fallback — pipeline continues")
            _record(stage_num, stage_name, error, "use_fallback", "success_fallback", diagnosis, config_issues=config_issues)
            return fallback
        logger.error(f"[Doctor] No fallback available for Stage {stage_num} — aborting")
        _record(stage_num, stage_name, error, "use_fallback", "no_fallback", diagnosis, config_issues=config_issues)

    else:  # abort
        logger.error("[Doctor] Strategy is 'abort' — passing error through")
        _record(stage_num, stage_name, error, "abort", "aborted", diagnosis, config_issues=config_issues)

    raise error
