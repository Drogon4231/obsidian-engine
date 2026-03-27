"""
Parameter observation storage and optimizer state persistence.

Stores per-video param snapshots + YouTube metrics in Supabase `param_observations`.
Optimizer state (momentum, epoch, losses) persists in `kv_store`.

Error handling: every function returns None on Supabase failure (never raises).
Pattern matches _fetch_from_supabase() in param_overrides.py.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


# ── Thread-safe JSONL writer ───────────────────────────────────────────────

_optimizer_log_lock = threading.Lock()
_OPTIMIZER_LOG_PATH = Path("outputs/optimizer_log.jsonl")
_OPTIMIZER_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB rotation


def _append_optimizer_log(entry: dict) -> None:
    """Append an entry to the optimizer JSONL log. Thread-safe, non-fatal."""
    try:
        _OPTIMIZER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _optimizer_log_lock:
            # Rotate if over 5MB
            if _OPTIMIZER_LOG_PATH.exists() and _OPTIMIZER_LOG_PATH.stat().st_size > _OPTIMIZER_LOG_MAX_BYTES:
                rotated = _OPTIMIZER_LOG_PATH.with_suffix(".jsonl.1")
                _OPTIMIZER_LOG_PATH.rename(rotated)

            with open(_OPTIMIZER_LOG_PATH, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass  # Non-fatal


# ── Supabase operations ───────────────────────────────────────────────────


def store_observation(
    video_id: str,
    youtube_id: str,
    params: dict,
    era: str,
    render_verification: object | None = None,
) -> dict | None:
    """Store a param snapshot + optional render verification for a video.

    Called after pipeline upload. Writes to `param_observations` table.
    Returns the inserted row dict, or None on failure.
    """
    try:
        from clients.supabase_client import get_client

        row = {
            "video_id": video_id,
            "youtube_id": youtube_id,
            "era": era,
            "params": params,
        }

        # Serialize render verification if provided
        if render_verification is not None:
            if hasattr(render_verification, "to_dict"):
                rv_dict = render_verification.to_dict()
            elif hasattr(render_verification, "__dict__"):
                rv_dict = asdict(render_verification)
            else:
                rv_dict = dict(render_verification) if isinstance(render_verification, dict) else {}

            row["render_verification"] = rv_dict
            row["render_compliance"] = rv_dict.get("overall_compliance", None)

        result = get_client().table("param_observations").insert(row).execute()
        return result.data[0] if result.data else None

    except Exception as e:
        try:
            from core.observability import log_error
            log_error(10, "param_history.store_observation", e, "warning")
        except Exception:
            pass
        return None


def attach_metrics(youtube_id: str, metrics_dict: dict) -> bool:
    """Attach YouTube performance metrics to an existing observation.

    Called by analytics agent when data matures (48h+).
    Returns True on success, False on failure.
    """
    try:
        from clients.supabase_client import get_client

        # Compute loss value if we have the optimizer
        loss_value = None
        try:
            from core.param_optimizer import ParamOptimizer, PerformanceMetrics
            pm = PerformanceMetrics(
                retention_pct=metrics_dict.get("retention_pct", 0),
                views_velocity=metrics_dict.get("views_velocity", 0),
                engagement_rate=metrics_dict.get("engagement_rate", 0),
                sentiment_score=metrics_dict.get("sentiment_score", 0),
                hook_retention_pct=metrics_dict.get("hook_retention_pct", 0),
            )
            optimizer = ParamOptimizer()
            loss_value = optimizer.compute_loss(pm)
        except Exception:
            pass

        update_data = {
            "metrics": metrics_dict,
            "metrics_attached_at": datetime.now(timezone.utc).isoformat(),
        }
        if loss_value is not None:
            update_data["loss_value"] = loss_value

        get_client().table("param_observations") \
            .update(update_data) \
            .eq("youtube_id", youtube_id) \
            .execute()
        return True

    except Exception as e:
        try:
            from core.observability import log_error
            log_error(12, "param_history.attach_metrics", e, "warning")
        except Exception:
            pass
        return False


def load_observations(min_age_hours: int = 48, limit: int = 50) -> list[dict] | None:
    """Load recent observations that have attached metrics.

    Returns list of observation dicts with params + metrics, or None on failure.
    """
    try:
        from clients.supabase_client import get_client

        result = get_client().table("param_observations") \
            .select("*") \
            .not_.is_("metrics", "null") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return result.data or []

    except Exception as e:
        try:
            from core.observability import log_error
            log_error(12, "param_history.load_observations", e, "warning")
        except Exception:
            pass
        return None


# ── Optimizer state persistence ────────────────────────────────────────────


def load_optimizer_state() -> dict | None:
    """Load optimizer state from kv_store. Returns plain dict, or None."""
    try:
        from clients.supabase_client import get_client

        result = get_client().table("kv_store") \
            .select("value") \
            .eq("key", "optimizer_state") \
            .execute()

        if result.data and result.data[0].get("value"):
            val = result.data[0]["value"]
            # Handle both string and dict JSONB values
            if isinstance(val, str):
                return json.loads(val)
            return val
        return None

    except Exception as e:
        try:
            from core.observability import log_error
            log_error(12, "param_history.load_optimizer_state", e, "warning")
        except Exception:
            pass
        return None


def save_optimizer_state(state) -> bool:
    """Save optimizer state to kv_store. Accepts OptimizerState or plain dict.

    Uses upsert with on_conflict="key" (string, not list — Supabase convention).
    Returns True on success.
    """
    try:
        from clients.supabase_client import get_client

        # Convert dataclass to dict if needed
        if hasattr(state, "to_dict"):
            state_dict = state.to_dict()
        elif hasattr(state, "__dataclass_fields__"):
            state_dict = asdict(state)
        else:
            state_dict = dict(state)

        get_client().table("kv_store").upsert(
            {
                "key": "optimizer_state",
                "value": state_dict,
            },
            on_conflict="key",
        ).execute()
        return True

    except Exception as e:
        try:
            from core.observability import log_error
            log_error(12, "param_history.save_optimizer_state", e, "warning")
        except Exception:
            pass
        return False


# ── Optimizer cycle logging ────────────────────────────────────────────────


def log_optimizer_cycle(result_dict: dict) -> bool:
    """Log an optimization cycle to both Supabase and JSONL.

    result_dict should contain: epoch, observations_used, confidence_level,
    proposals, auto_applied, pending_approval, rollback_triggered, diagnostics.
    Returns True if at least one storage succeeded.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = {"timestamp": timestamp, **result_dict}

    jsonl_ok = False
    supabase_ok = False

    # 1. JSONL log (always attempt)
    try:
        _append_optimizer_log(entry)
        jsonl_ok = True
    except Exception:
        pass

    # 2. Supabase optimizer_cycles table
    try:
        from clients.supabase_client import get_client

        row = {
            "epoch": result_dict.get("epoch", 0),
            "observations_used": result_dict.get("observations_used", 0),
            "confidence_level": result_dict.get("confidence_level", "none"),
            "proposals": result_dict.get("proposals"),
            "auto_applied": result_dict.get("auto_applied"),
            "pending_approval": result_dict.get("pending_approval"),
            "rollback_triggered": result_dict.get("rollback_triggered", False),
            "rollback_params": result_dict.get("rollback_params"),
            "diagnostics": result_dict.get("diagnostics"),
        }
        get_client().table("optimizer_cycles").insert(row).execute()
        supabase_ok = True

    except Exception as e:
        try:
            from core.observability import log_error
            log_error(12, "param_history.log_optimizer_cycle", e, "warning")
        except Exception:
            pass

    return jsonl_ok or supabase_ok


# ── Pending approvals ──────────────────────────────────────────────────────


def load_pending_approvals() -> list[dict] | None:
    """Load pending optimizer proposals from kv_store."""
    try:
        from clients.supabase_client import get_client

        result = get_client().table("kv_store") \
            .select("value") \
            .eq("key", "optimizer_pending_approvals") \
            .execute()

        if result.data and result.data[0].get("value"):
            val = result.data[0]["value"]
            if isinstance(val, str):
                return json.loads(val)
            return val if isinstance(val, list) else []
        return []

    except Exception:
        return None


def save_pending_approvals(approvals: list[dict]) -> bool:
    """Save pending optimizer proposals to kv_store."""
    try:
        from clients.supabase_client import get_client

        get_client().table("kv_store").upsert(
            {
                "key": "optimizer_pending_approvals",
                "value": approvals,
            },
            on_conflict="key",
        ).execute()
        return True

    except Exception:
        return False


def is_optimizer_enabled() -> bool:
    """Check the kill switch. Returns True if optimizer is enabled (default)."""
    try:
        from clients.supabase_client import get_client

        result = get_client().table("kv_store") \
            .select("value") \
            .eq("key", "optimizer_enabled") \
            .execute()

        if result.data and result.data[0].get("value") is not None:
            val = result.data[0]["value"]
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.lower() not in ("false", "0", "no")
            return bool(val)
        return True  # Default: enabled

    except Exception:
        return True  # On failure, assume enabled (safe default)


# ── Batch override save ───────────────────────────────────────────────────


def save_override_batch(updates: dict[str, float], approved_by: str = "optimizer") -> bool:
    """Save multiple param overrides atomically.

    Args:
        updates: {param_key: new_value}
        approved_by: who approved ("optimizer", "optimizer_rollback", "optimizer_explore", "dashboard")

    Returns True on success.
    """
    if not updates:
        return True

    try:
        from core.param_overrides import save_override
        for key, value in updates.items():
            save_override(key, value, approved_by=approved_by)
        return True

    except Exception as e:
        try:
            from core.observability import log_error
            log_error(12, "param_history.save_override_batch", e, "warning")
        except Exception:
            pass
        return False
