"""
call_agent() — Unified execution wrapper for all pipeline agents.

Provides:
- Four-tier model routing with effort calibration
- Structured JSON output validation
- Chain-of-thought reasoning capture and logging
- Pipeline Doctor error recovery (with recursion guard)
- SLA timing and diagnostic logging
- Prompt versioning support
- Context assembly (DNA + channel insights)

Every Claude call in the pipeline should go through call_agent() instead
of calling call_claude() directly. This gives us one place to add
observability, recovery, cost controls, and quality gates.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clients.claude_client import call_claude, call_claude_with_search, OPUS, SONNET, HAIKU
from core.log import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
DIAGNOSTIC_LOG = OUTPUTS_DIR / "diagnostic_log.jsonl"
PROMPT_MANIFEST = OUTPUTS_DIR / "prompt_manifest.json"

# ── Model Tiers ──────────────────────────────────────────────────────────────
# Each agent has a default tier.  Effort offset shifts it up/down.
# Tier order: PREMIUM > FULL > LIGHT > NANO (NANO = skip / cached)

MODEL_TIERS = {
    "premium": OPUS,
    "full":    SONNET,
    "light":   HAIKU,
}

_TIER_ORDER = ["light", "full", "premium"]

# Default tier per agent name (matches the numbered filenames without extension)
AGENT_DEFAULTS = {
    # Premium (Opus) — creative judgment
    "04_script_writer":        {"tier": "premium", "sla_seconds": 120},
    "04b_script_doctor":       {"tier": "full",    "sla_seconds": 60},
    # Full (Sonnet) — complex reasoning
    "00_topic_discovery":      {"tier": "full",    "sla_seconds": 90},
    "01_research_agent":       {"tier": "full",    "sla_seconds": 90},
    "02_originality_agent":    {"tier": "full",    "sla_seconds": 60},
    "03_narrative_architect":  {"tier": "full",    "sla_seconds": 90},
    "05_fact_verification":    {"tier": "full",    "sla_seconds": 90},
    "07_scene_breakdown":      {"tier": "full",    "sla_seconds": 60},
    "07b_visual_continuity":   {"tier": "full",    "sla_seconds": 45},
    "12_analytics_agent":      {"tier": "full",    "sla_seconds": 120},
    "content_auditor_captions": {"tier": "light",  "sla_seconds": 30},
    "content_auditor_master":   {"tier": "full",   "sla_seconds": 60},
    "short_script_agent":      {"tier": "full",    "sla_seconds": 45},
    "short_storyboard_agent":  {"tier": "full",    "sla_seconds": 45},
    "thumbnail_agent":         {"tier": "full",    "sla_seconds": 45},
    # Light (Haiku) — mechanical / classification
    "06_seo_agent":            {"tier": "light",   "sla_seconds": 30},
    "tts_format_agent":        {"tier": "light",   "sla_seconds": 20},
    "comment_analyzer":        {"tier": "light",   "sla_seconds": 30},
    "compliance_checker":      {"tier": "light",   "sla_seconds": 30},
    "hook_scorer":             {"tier": "light",   "sla_seconds": 15},
    "localization_pipeline":   {"tier": "full",    "sla_seconds": 60},
}


def _resolve_model(agent_name: str, effort_offset: int = 0) -> str:
    """Resolve the model ID for an agent, applying effort offset.

    effort_offset:  +1 = bump up one tier,  -1 = bump down one tier
    Clamped to [light, premium].
    """
    defaults = AGENT_DEFAULTS.get(agent_name, {"tier": "full"})
    base_tier = defaults["tier"]
    base_idx = _TIER_ORDER.index(base_tier)
    target_idx = max(0, min(len(_TIER_ORDER) - 1, base_idx + effort_offset))
    return MODEL_TIERS[_TIER_ORDER[target_idx]]


def _get_sla(agent_name: str) -> float:
    """Return the SLA in seconds for the given agent."""
    return AGENT_DEFAULTS.get(agent_name, {}).get("sla_seconds", 60)


# ── Diagnostic Logging ───────────────────────────────────────────────────────

def _log_diagnostic(entry: dict):
    """Append a diagnostic entry to the JSONL log, rotating at 5MB."""
    try:
        DIAGNOSTIC_LOG.parent.mkdir(parents=True, exist_ok=True)
        # Rotate if over 5MB
        if DIAGNOSTIC_LOG.exists() and DIAGNOSTIC_LOG.stat().st_size > 5 * 1024 * 1024:
            rotated = DIAGNOSTIC_LOG.with_suffix(".jsonl.1")
            if rotated.exists():
                rotated.unlink()
            DIAGNOSTIC_LOG.rename(rotated)
        with open(DIAGNOSTIC_LOG, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass  # diagnostics must never crash the pipeline


# ── Prompt Versioning ────────────────────────────────────────────────────────

def _hash_prompt(text: str) -> str:
    """SHA-256 hash of a prompt (first 12 hex chars for brevity)."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def _check_prompt_drift(agent_name: str, system_prompt: str) -> str | None:
    """Compare system prompt hash against manifest. Returns diff note or None."""
    try:
        current_hash = _hash_prompt(system_prompt)
        manifest = {}
        if PROMPT_MANIFEST.exists():
            manifest = json.loads(PROMPT_MANIFEST.read_text())

        prev = manifest.get(agent_name, {})
        prev_hash = prev.get("hash", "")

        if prev_hash and prev_hash != current_hash:
            drift_note = (
                f"PROMPT DRIFT: {agent_name} system prompt changed "
                f"({prev_hash} → {current_hash})"
            )
            logger.info(f"  [prompt] {drift_note}")
            # Update manifest
            manifest[agent_name] = {
                "hash": current_hash,
                "updated": datetime.now(timezone.utc).isoformat(),
                "prev_hash": prev_hash,
                "char_count": len(system_prompt),
            }
            PROMPT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
            PROMPT_MANIFEST.write_text(json.dumps(manifest, indent=2))
            return drift_note
        elif not prev_hash:
            # First time seeing this agent — register
            manifest[agent_name] = {
                "hash": current_hash,
                "updated": datetime.now(timezone.utc).isoformat(),
                "prev_hash": "",
                "char_count": len(system_prompt),
            }
            PROMPT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
            PROMPT_MANIFEST.write_text(json.dumps(manifest, indent=2))
        return None
    except Exception:
        return None  # prompt versioning must never crash the pipeline


# ── Reasoning Capture ────────────────────────────────────────────────────────

_REASONING_DIR = OUTPUTS_DIR / "reasoning"


def _save_reasoning(agent_name: str, topic: str, reasoning: str):
    """Save chain-of-thought reasoning to a file for debugging."""
    if not reasoning:
        return
    try:
        _REASONING_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c if c.isalnum() or c in "-_ " else "" for c in (topic or "unknown"))[:40].strip()
        path = _REASONING_DIR / f"{ts}_{agent_name}_{safe_topic}.txt"
        path.write_text(reasoning)
    except Exception:
        pass


# ── Doctor Integration ───────────────────────────────────────────────────────

# Thread-local recursion guard to prevent Doctor → call_agent → Doctor loops
_recovery_state = threading.local()
_MAX_RECOVERY_DEPTH = 1


def _attempt_recovery(agent_name: str, stage_num: int | None,
                      fn, args: tuple, kwargs: dict,
                      error: Exception) -> Any:
    """Try Pipeline Doctor recovery. Returns result or re-raises."""
    depth = getattr(_recovery_state, "depth", 0)

    if depth >= _MAX_RECOVERY_DEPTH:
        raise error

    _recovery_state.depth = depth + 1
    try:
        from core import pipeline_doctor
        # Doctor's intervene() expects (stage_num, stage_name, fn, args, error)
        # For non-numbered agents, use -1 as stage_num
        result = pipeline_doctor.intervene(
            stage_num or -1,
            agent_name,
            lambda: fn(*args, **kwargs),
            (),
            error,
            recent_logs=[],
        )
        return result
    except ImportError:
        raise error
    except Exception:
        raise error
    finally:
        _recovery_state.depth = depth


# ── Public API ───────────────────────────────────────────────────────────────

def call_agent(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    *,
    expect_json: bool = True,
    max_tokens: int = 4000,
    effort_offset: int = 0,
    stage_num: int | None = None,
    topic: str = "",
    enable_recovery: bool = True,
    use_search: bool = False,
    _is_recovery_call: bool = False,
    output_schema: dict | None = None,
) -> Any:
    """
    Unified entry point for all Claude calls in the pipeline.

    Args:
        agent_name:      Identifier for the calling agent (e.g. "01_research_agent")
        system_prompt:   The system prompt for Claude
        user_prompt:     The user prompt for Claude
        expect_json:     If True, parse response as JSON
        max_tokens:      Max output tokens
        effort_offset:   Shift model tier up (+1) or down (-1)
        stage_num:       Pipeline stage number (for Doctor integration)
        topic:           Current topic (for logging)
        enable_recovery: Whether to attempt Pipeline Doctor recovery on failure
        use_search:      If True, use call_claude_with_search instead
        _is_recovery_call: Internal flag to prevent recursion

    Returns:
        Parsed JSON dict/list, or raw text string if expect_json=False
    """
    model = _resolve_model(agent_name, effort_offset)
    sla = _get_sla(agent_name)

    # Prompt drift detection (non-blocking)
    drift_note = _check_prompt_drift(agent_name, system_prompt)

    t0 = time.time()
    diag = {
        "agent": agent_name,
        "model": model,
        "stage_num": stage_num,
        "topic": topic[:80] if topic else "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sla_seconds": sla,
        "prompt_hash": _hash_prompt(system_prompt),
    }
    if drift_note:
        diag["prompt_drift"] = drift_note

    # Auto-lookup schema from registry if not explicitly passed
    if output_schema is None and expect_json:
        try:
            from core.structured_schemas import SCHEMA_REGISTRY
            output_schema = SCHEMA_REGISTRY.get(agent_name)
        except ImportError:
            pass

    try:
        if use_search:
            result = call_claude_with_search(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                max_tokens=max_tokens,
                output_schema=output_schema,
            )
        else:
            result = call_claude(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                max_tokens=max_tokens,
                expect_json=expect_json,
                output_schema=output_schema,
            )

        elapsed = round(time.time() - t0, 2)
        diag["elapsed_seconds"] = elapsed
        diag["status"] = "success"
        diag["sla_breach"] = elapsed > sla

        if diag["sla_breach"]:
            logger.warning(f"  [SLA] {agent_name} took {elapsed}s (SLA: {sla}s)")

        _log_diagnostic(diag)
        try:
            from core.observability import log_trace
            log_trace(agent_name, stage_num or -1, model, elapsed, {}, sla, "success", topic)
        except Exception:
            pass
        return result

    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        diag["elapsed_seconds"] = elapsed
        diag["status"] = "error"
        diag["error_type"] = type(e).__name__
        diag["error_message"] = str(e)[:300]
        _log_diagnostic(diag)
        try:
            from core.observability import log_error, log_trace
            log_error(str(stage_num or ""), agent_name, e, context={"model": model, "topic": topic})
            log_trace(agent_name, stage_num or -1, model, elapsed, {}, sla, "error", topic)
        except Exception:
            pass

        # Attempt recovery if enabled and not already in a recovery call
        if enable_recovery and not _is_recovery_call:
            logger.error(f"  [{agent_name}] Error: {type(e).__name__} — attempting recovery...")
            try:
                recovered = _attempt_recovery(
                    agent_name, stage_num,
                    _call_raw, (system_prompt, user_prompt, model, max_tokens, expect_json, use_search, output_schema),
                    {},
                    e,
                )
                diag_recovery = {
                    **diag,
                    "status": "recovered",
                    "elapsed_seconds": round(time.time() - t0, 2),
                }
                _log_diagnostic(diag_recovery)
                return recovered
            except Exception:
                pass  # recovery failed, raise original

        raise


def _call_raw(system_prompt, user_prompt, model, max_tokens, expect_json, use_search, output_schema=None):
    """Raw Claude call used as the retry function for Doctor."""
    if use_search:
        return call_claude_with_search(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            max_tokens=max_tokens,
            output_schema=output_schema,
        )
    return call_claude(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
        expect_json=expect_json,
        output_schema=output_schema,
    )
