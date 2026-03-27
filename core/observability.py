"""
Native observability — replaces Sentry (error tracking) + Langfuse (agent tracing).
Uses JSONL files with rotation, same pattern as diagnostic_log.jsonl.
"""
import json
import hashlib
import threading
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone
from collections import deque

BASE_DIR = Path(__file__).resolve().parent.parent
ERROR_LOG = BASE_DIR / "outputs" / "error_log.jsonl"
TRACE_LOG = BASE_DIR / "outputs" / "agent_traces.jsonl"

_error_lock = threading.Lock()
_trace_lock = threading.Lock()
_dedup_cache: dict[str, dict] = {}  # dedup_key -> {count, first_seen, last_seen}
_MAX_DEDUP_ENTRIES = 500  # Prevent unbounded memory growth

def _rotate_if_needed(path: Path, max_bytes: int):
    """Rotate JSONL file if over max_bytes. Same pattern as agent_wrapper.py:101."""
    try:
        if path.exists() and path.stat().st_size > max_bytes:
            rotated = path.with_suffix(".jsonl.1")
            if rotated.exists():
                rotated.unlink()
            path.rename(rotated)
    except Exception:
        pass

# ── Error Tracker (replaces Sentry) ──────────────────────────────

def log_error(stage: str, agent: str, error: Exception,
              severity: str = "error", context: dict = None) -> None:
    """Log error with deduplication. Thread-safe."""
    tb = traceback.format_exc()
    first_tb_line = tb.strip().split('\n')[-1] if tb else ""
    dedup_key = hashlib.sha256(f"{agent}:{type(error).__name__}:{first_tb_line}".encode()).hexdigest()[:16]

    now = datetime.now(timezone.utc).isoformat()

    with _error_lock:
        if dedup_key in _dedup_cache:
            _dedup_cache[dedup_key]["count"] += 1
            _dedup_cache[dedup_key]["last_seen"] = now
            count = _dedup_cache[dedup_key]["count"]
        else:
            # Evict oldest entries if cache is full (prevent memory leak)
            if len(_dedup_cache) >= _MAX_DEDUP_ENTRIES:
                oldest = min(_dedup_cache, key=lambda k: _dedup_cache[k]["last_seen"])
                del _dedup_cache[oldest]
            _dedup_cache[dedup_key] = {"count": 1, "first_seen": now, "last_seen": now}
            count = 1

        entry = {
            "timestamp": now,
            "stage": stage,
            "agent": agent,
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
            "stack_trace": tb[:3000],
            "severity": severity,
            "dedup_key": dedup_key,
            "count": count,
            **(context or {}),
        }

        _rotate_if_needed(ERROR_LOG, 5 * 1024 * 1024)
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    # Telegram alert on critical or spike
    if severity == "critical" or count == 5:
        try:
            from server.notify import notify_error_spike
            notify_error_spike(agent, type(error).__name__, count, tb[:500])
        except Exception:
            pass

def get_error_summary(hours: int = 24) -> list[dict]:
    """Returns grouped errors from last N hours."""
    if not ERROR_LOG.exists():
        return []
    cutoff = time.time() - (hours * 3600)
    grouped: dict[str, dict] = {}
    try:
        with open(ERROR_LOG) as f:
            lines = deque(f, maxlen=1000)
        for line in lines:
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "")
                if isinstance(ts, str):
                    entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                else:
                    entry_time = float(ts)
                if entry_time < cutoff:
                    continue
                key = entry.get("dedup_key", "")
                if key in grouped:
                    grouped[key]["count"] = max(grouped[key]["count"], entry.get("count", 1))
                    grouped[key]["last_seen"] = entry.get("timestamp")
                else:
                    grouped[key] = entry
            except Exception:
                continue
    except Exception:
        pass
    return sorted(grouped.values(), key=lambda e: e.get("count", 0), reverse=True)

# ── Agent Trace Tracker (replaces Langfuse) ──────────────────────

def log_trace(agent: str, stage_num: int, model: str,
              elapsed_s: float, tokens: dict, sla_s: float,
              status: str, topic: str) -> None:
    """Append agent trace. Thread-safe."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "stage_num": stage_num,
        "model": model,
        "elapsed_s": round(elapsed_s, 2),
        "input_tokens": tokens.get("input", 0),
        "output_tokens": tokens.get("output", 0),
        "cache_read_tokens": tokens.get("cache_read", 0),
        "sla_s": sla_s,
        "sla_breach": elapsed_s > sla_s,
        "status": status,
        "topic": topic[:80],
    }
    with _trace_lock:
        _rotate_if_needed(TRACE_LOG, 10 * 1024 * 1024)
        TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACE_LOG, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

def get_agent_stats(days: int = 7) -> list[dict]:
    """Per-agent performance summary over N days."""
    if not TRACE_LOG.exists():
        return []
    cutoff = time.time() - (days * 86400)
    agents: dict[str, list] = {}
    try:
        with open(TRACE_LOG) as f:
            lines = deque(f, maxlen=5000)
        for line in lines:
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "")
                if isinstance(ts, str):
                    entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                else:
                    entry_time = float(ts)
                if entry_time < cutoff:
                    continue
                name = entry.get("agent", "unknown")
                agents.setdefault(name, []).append(entry)
            except Exception:
                continue
    except Exception:
        pass

    stats = []
    for name, entries in agents.items():
        latencies = [e["elapsed_s"] for e in entries if "elapsed_s" in e]
        successes = [e for e in entries if e.get("status") == "success"]
        breaches = [e for e in entries if e.get("sla_breach")]
        stats.append({
            "agent": name,
            "calls": len(entries),
            "avg_latency": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "p95_latency": round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 2),
            "success_rate": round(len(successes) / len(entries) * 100, 1) if entries else 0,
            "sla_breach_rate": round(len(breaches) / len(entries) * 100, 1) if entries else 0,
            "avg_input_tokens": round(sum(e.get("input_tokens", 0) for e in entries) / len(entries)) if entries else 0,
            "avg_output_tokens": round(sum(e.get("output_tokens", 0) for e in entries) / len(entries)) if entries else 0,
        })
    return sorted(stats, key=lambda s: s["calls"], reverse=True)
