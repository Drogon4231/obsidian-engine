"""
cost_tracker.py — API cost tracking and ROI analysis.

Tracks per-run costs across all services in the pipeline (Claude, ElevenLabs,
fal.ai, etc.) and produces ROI reports by correlating costs with video performance.

Usage:
    from cost_tracker import start_run, log_cost, get_cost_estimate, end_run
    run_id = "run_20260316_mkultra"
    start_run("MKUltra", run_id)
    log_cost(run_id, "research", "claude_opus", 50000, "tokens")
    estimate = get_cost_estimate(run_id)
    end_run(run_id, video_id="abc123")
"""

import os
import sys
import json
import threading
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
COST_LOG_FILE = OUTPUTS_DIR / "cost_log.json"
INSIGHTS_FILE = BASE_DIR / "channel_insights.json"

PREFIX = "[CostTracker]"

# ── Thread-safe in-memory store ──────────────────────────────────────────────
_lock = threading.Lock()
_file_lock = threading.Lock()  # Protects cost_log.json read-modify-write
_runs: dict[str, dict] = {}


# ── Rate card (USD) — prices imported from claude_client as single source of truth
try:
    from clients.claude_client import _PRICES as _CLAUDE_PRICES
    _opus_p   = _CLAUDE_PRICES.get("claude-opus-4-6",           {"input": 15.00, "output": 75.00})
    _sonnet_p = _CLAUDE_PRICES.get("claude-sonnet-4-6",         {"input":  3.00, "output": 15.00})
    _haiku_p  = _CLAUDE_PRICES.get("claude-haiku-4-5-20251001", {"input":  0.80, "output":  4.00})
except ImportError:
    _opus_p   = {"input": 15.00, "output": 75.00}
    _sonnet_p = {"input":  3.00, "output": 15.00}
    _haiku_p  = {"input":  0.80, "output":  4.00}

RATE_CARD = {
    "claude_opus": {
        "tokens": {"input": _opus_p["input"] / 1_000_000, "output": _opus_p["output"] / 1_000_000},
        "default_split": 0.6,
    },
    "claude_sonnet": {
        "tokens": {"input": _sonnet_p["input"] / 1_000_000, "output": _sonnet_p["output"] / 1_000_000},
        "default_split": 0.6,
    },
    "claude_haiku": {
        "tokens": {"input": _haiku_p["input"] / 1_000_000, "output": _haiku_p["output"] / 1_000_000},
        "default_split": 0.6,
    },
    "elevenlabs": {
        "characters": 0.30 / 1000,  # ~$0.30 per 1000 chars
    },
    "fal_ai": {
        "images": 0.05,  # ~$0.05 per image
    },
    "youtube_api": {
        "api_calls": 0.0,  # free (quota-based)
    },
    "google_scholar": {
        "api_calls": 0.0,  # free
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Run lifecycle
# ══════════════════════════════════════════════════════════════════════════════

_active_run_id: str | None = None


def get_active_run_id() -> str | None:
    """Return the currently active run ID, or None if no run is active."""
    return _active_run_id


def start_run(topic: str, run_id: str) -> None:
    """
    Initialize a cost tracking session.

    Args:
        topic: The video topic being produced.
        run_id: Unique identifier for this pipeline run.
    """
    global _active_run_id
    _active_run_id = run_id
    with _lock:
        _runs[run_id] = {
            "run_id": run_id,
            "topic": topic,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "video_id": None,
            "entries": [],
            "finalized": False,
        }
    print(f"{PREFIX} Started tracking run '{run_id}' for topic: {topic}")


def log_usd_cost(run_id: str, stage: str, service: str, usd: float) -> None:
    """Log a pre-computed USD cost (bypasses RATE_CARD estimation)."""
    with _lock:
        if run_id not in _runs:
            return
        _runs[run_id]["entries"].append({
            "stage": stage,
            "service": service,
            "units": 0,
            "unit_type": "usd_direct",
            "usd_direct": round(usd, 6),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


def log_cost(run_id: str, stage: str, service: str, units: float, unit_type: str) -> None:
    """
    Log a cost entry for a pipeline stage.

    Args:
        run_id: The run to log against.
        stage: Pipeline stage (e.g., 'research', 'script', 'audio', 'images').
        service: Service name (e.g., 'claude_opus', 'elevenlabs', 'fal_ai').
        units: Number of units consumed.
        unit_type: Type of units ('tokens', 'characters', 'images', 'api_calls').
    """
    with _lock:
        if run_id not in _runs:
            print(f"{PREFIX} Warning: run '{run_id}' not found — creating it.")
            _runs[run_id] = {
                "run_id": run_id,
                "topic": "unknown",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "ended_at": None,
                "video_id": None,
                "entries": [],
                "finalized": False,
            }

        _runs[run_id]["entries"].append({
            "stage": stage,
            "service": service,
            "units": units,
            "unit_type": unit_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


def get_cost_estimate(run_id: str) -> dict:
    """
    Calculate estimated USD cost for a run using the rate card.

    Args:
        run_id: The run to estimate costs for.

    Returns:
        {total_cost, per_stage: {stage: cost}, per_service: {service: cost}, entries: int}
    """
    with _lock:
        run_data = _runs.get(run_id)
        if not run_data:
            print(f"{PREFIX} Run '{run_id}' not found.")
            return {"total_cost": 0.0, "per_stage": {}, "per_service": {}, "entries": 0}

        entries = run_data["entries"]

    total = 0.0
    per_stage: dict[str, float] = {}
    per_service: dict[str, float] = {}

    for entry in entries:
        cost = _calculate_entry_cost(entry)
        total += cost

        stage = entry["stage"]
        service = entry["service"]
        per_stage[stage] = per_stage.get(stage, 0.0) + cost
        per_service[service] = per_service.get(service, 0.0) + cost

    # Round everything for readability
    result = {
        "total_cost": round(total, 4),
        "per_stage": {k: round(v, 4) for k, v in per_stage.items()},
        "per_service": {k: round(v, 4) for k, v in per_service.items()},
        "entries": len(entries),
    }

    return result


def _calculate_entry_cost(entry: dict) -> float:
    """Calculate USD cost for a single log entry."""
    unit_type = entry.get("unit_type", "")

    # Pre-computed USD from claude_client (cache-aware, most accurate)
    if unit_type == "usd_direct":
        return entry.get("usd_direct", 0.0)

    service = entry.get("service", "")
    units = entry.get("units", 0)

    rate_info = RATE_CARD.get(service)
    if not rate_info:
        return 0.0

    # Token-based services (Claude models)
    if unit_type == "tokens" and "tokens" in rate_info:
        # Assume default input/output split when not specified
        split = rate_info.get("default_split", 0.6)
        input_tokens = units * split
        output_tokens = units * (1 - split)
        return (input_tokens * rate_info["tokens"]["input"]
                + output_tokens * rate_info["tokens"]["output"])

    # Character-based (ElevenLabs)
    if unit_type == "characters" and "characters" in rate_info:
        return units * rate_info["characters"]

    # Image-based (fal.ai)
    if unit_type == "images" and "images" in rate_info:
        return units * rate_info["images"]

    # API call-based (free services)
    if unit_type == "api_calls" and "api_calls" in rate_info:
        return units * rate_info["api_calls"]

    return 0.0


def end_run(run_id: str, video_id: str = None) -> dict:
    """
    Finalize a run and append to cost_log.json.

    Args:
        run_id: The run to finalize.
        video_id: Optional YouTube video ID (if uploaded).

    Returns:
        The finalized run record.
    """
    global _active_run_id
    _active_run_id = None
    estimate = get_cost_estimate(run_id)

    with _lock:
        run_data = _runs.get(run_id)
        if not run_data:
            print(f"{PREFIX} Run '{run_id}' not found — nothing to finalize.")
            return {}

        run_data["ended_at"] = datetime.now(timezone.utc).isoformat()
        run_data["video_id"] = video_id
        run_data["finalized"] = True
        run_data["cost_estimate"] = estimate

        record = dict(run_data)

    # Append to cost_log.json
    _append_to_cost_log(record)

    print(f"{PREFIX} Run '{run_id}' finalized — total cost: ${estimate['total_cost']:.4f}")
    return record


def _append_to_cost_log(record: dict) -> None:
    """Append a run record to the persistent cost log. Thread-safe."""
    OUTPUTS_DIR.mkdir(exist_ok=True)

    with _file_lock:
        existing = []
        if COST_LOG_FILE.exists():
            try:
                existing = json.loads(COST_LOG_FILE.read_text())
                if not isinstance(existing, list):
                    existing = [existing]
            except Exception:
                existing = []

        existing.append(record)

        try:
            COST_LOG_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
            print(f"{PREFIX} Appended run to {COST_LOG_FILE}")
        except Exception as e:
            print(f"{PREFIX} Warning: could not write cost log: {e}")

    # Persist to Supabase outside the file lock (network I/O can be slow)
    try:
        from core.utils import persist_json_to_supabase
        persist_json_to_supabase(COST_LOG_FILE, existing)
    except Exception as e:
        print(f"{PREFIX} Warning: could not persist cost log to Supabase: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Budget enforcement
# ══════════════════════════════════════════════════════════════════════════════

class BudgetExceededError(Exception):
    """Raised when a pipeline run exceeds its cost budget."""
    def __init__(self, spent: float, budget: float, stage: str = ""):
        self.spent = spent
        self.budget = budget
        self.stage = stage
        msg = f"Budget exceeded: ${spent:.4f} spent (limit: ${budget:.2f})"
        if stage:
            msg += f" — detected after stage '{stage}'"
        super().__init__(msg)


def check_budget(budget_usd: float, stage_name: str = "") -> bool:
    """
    Check if current session spend exceeds the budget.

    Uses claude_client.get_session_costs() for real-time Claude API spend,
    which is the dominant cost in the pipeline.

    Args:
        budget_usd: Maximum allowed USD spend. If 0 or negative, check is skipped.
        stage_name: Current stage name (for error context).

    Returns:
        True if within budget, raises BudgetExceededError if over.
    """
    if budget_usd <= 0:
        return True  # Budget enforcement disabled

    try:
        from clients.claude_client import get_session_costs
        costs = get_session_costs()
        spent = costs.get("usd_total", 0.0)
    except Exception:
        return True  # Can't check — don't block pipeline

    if spent > budget_usd:
        raise BudgetExceededError(spent, budget_usd, stage_name)

    return True


def get_remaining_budget(budget_usd: float) -> float:
    """
    Return remaining budget in USD. Returns float('inf') if budget is disabled.

    Args:
        budget_usd: Maximum allowed USD spend. If 0 or negative, returns inf.
    """
    if budget_usd <= 0:
        return float("inf")

    try:
        from clients.claude_client import get_session_costs
        costs = get_session_costs()
        spent = costs.get("usd_total", 0.0)
    except Exception:
        return float("inf")

    return max(0.0, budget_usd - spent)


# ══════════════════════════════════════════════════════════════════════════════
# ROI reporting
# ══════════════════════════════════════════════════════════════════════════════

def _load_cost_log() -> list[dict]:
    """Load the persistent cost log."""
    if not COST_LOG_FILE.exists():
        return []
    try:
        data = json.loads(COST_LOG_FILE.read_text())
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


def _load_insights() -> dict:
    """Load channel_insights.json for performance data."""
    if not INSIGHTS_FILE.exists():
        return {}
    try:
        return json.loads(INSIGHTS_FILE.read_text())
    except Exception:
        return {}


def get_roi_report() -> str:
    """
    Cross-reference cost_log.json with channel_insights.json to calculate
    cost-per-view and cost-per-subscriber for produced videos.

    Returns:
        Formatted ROI report string.
    """
    runs = _load_cost_log()
    insights = _load_insights()

    if not runs:
        return f"{PREFIX} No cost data available. Run the pipeline first."

    # Extract per-video performance from insights
    video_performance = {}
    for video in insights.get("video_performance", []):
        vid = video.get("video_id")
        if vid:
            video_performance[vid] = {
                "views": video.get("views", 0),
                "subscribers_gained": video.get("subscribers_gained", 0),
                "title": video.get("title", "Unknown"),
            }

    lines = [
        "=" * 60,
        "  THE OBSIDIAN ARCHIVE — ROI REPORT",
        "=" * 60,
        "",
    ]

    total_cost = 0.0
    total_views = 0
    total_subs = 0
    matched = 0

    for run in runs:
        cost = run.get("cost_estimate", {}).get("total_cost", 0.0)
        total_cost += cost
        vid = run.get("video_id")
        topic = run.get("topic", "Unknown")

        if vid and vid in video_performance:
            perf = video_performance[vid]
            views = perf["views"]
            subs = perf["subscribers_gained"]
            total_views += views
            total_subs += subs
            matched += 1

            cpv = f"${cost / views:.4f}" if views > 0 else "N/A"
            cps = f"${cost / subs:.2f}" if subs > 0 else "N/A"

            lines.append(f"  {topic}")
            lines.append(f"    Cost: ${cost:.4f}  |  Views: {views:,}  |  Subs: +{subs}")
            lines.append(f"    Cost/View: {cpv}  |  Cost/Sub: {cps}")
            lines.append("")
        else:
            lines.append(f"  {topic}")
            lines.append(f"    Cost: ${cost:.4f}  |  Performance data: not available")
            lines.append("")

    lines.append("-" * 60)
    lines.append(f"  Total runs: {len(runs)}")
    lines.append(f"  Total cost: ${total_cost:.4f}")

    if matched > 0 and total_views > 0:
        lines.append(f"  Avg cost/view: ${total_cost / total_views:.4f}")
    if matched > 0 and total_subs > 0:
        lines.append(f"  Avg cost/subscriber: ${total_cost / total_subs:.2f}")

    lines.append(f"  Videos with performance data: {matched}/{len(runs)}")
    lines.append("=" * 60)

    return "\n".join(lines)


def get_monthly_summary() -> dict:
    """
    Aggregate costs by month.

    Returns:
        {month, total_cost, videos_produced, avg_cost_per_video, estimated_revenue}
    """
    runs = _load_cost_log()
    if not runs:
        return {}

    months: dict[str, dict] = {}

    for run in runs:
        started = run.get("started_at", "")
        if not started:
            continue

        try:
            dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            month_key = dt.strftime("%Y-%m")
        except Exception:
            continue

        cost = run.get("cost_estimate", {}).get("total_cost", 0.0)

        if month_key not in months:
            months[month_key] = {
                "month": month_key,
                "total_cost": 0.0,
                "videos_produced": 0,
                "runs": [],
            }

        months[month_key]["total_cost"] += cost
        months[month_key]["videos_produced"] += 1
        months[month_key]["runs"].append(run.get("topic", "unknown"))

    # Calculate averages and estimates
    insights = _load_insights()
    insights.get("channel_stats", {})
    # Rough revenue estimate: $2-5 CPM for documentary content

    result = {}
    for key, data in sorted(months.items()):
        avg_cost = data["total_cost"] / data["videos_produced"] if data["videos_produced"] > 0 else 0.0
        result[key] = {
            "month": key,
            "total_cost": round(data["total_cost"], 4),
            "videos_produced": data["videos_produced"],
            "avg_cost_per_video": round(avg_cost, 4),
            "estimated_revenue": None,  # requires view data per month
            "topics": data["runs"],
        }

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(get_roi_report())
    print()
    monthly = get_monthly_summary()
    if monthly:
        print("Monthly Summary:")
        print(json.dumps(monthly, indent=2))
    else:
        print("No monthly data available.")
