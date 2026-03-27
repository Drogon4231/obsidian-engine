"""
diagnostics.py — Pipeline diagnostic intelligence from agent_wrapper logs.

Reads outputs/diagnostic_log.jsonl and computes:
- Per-agent success rate, avg latency, SLA breach rate
- Error hotspots (which agents fail most)
- Cost distribution by stage
- Pipeline health summary

Used by the dashboard and can be called from CLI.
"""

import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
DIAGNOSTIC_LOG = BASE_DIR / "outputs" / "diagnostic_log.jsonl"


def load_entries(hours: float = 168) -> list[dict]:
    """Load diagnostic log entries from the last N hours (default: 7 days)."""
    if not DIAGNOSTIC_LOG.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    entries = []

    try:
        with open(DIAGNOSTIC_LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", "")
                    if ts:
                        entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if entry_time < cutoff:
                            continue
                    entries.append(entry)
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception:
        return []

    return entries


def compute_agent_stats(entries: list[dict]) -> dict:
    """Compute per-agent performance stats."""
    agents = defaultdict(lambda: {
        "calls": 0, "successes": 0, "errors": 0, "recoveries": 0,
        "sla_breaches": 0, "total_latency": 0.0, "latencies": [],
        "error_types": defaultdict(int),
    })

    for e in entries:
        name = e.get("agent", "unknown")
        a = agents[name]
        a["calls"] += 1
        status = e.get("status", "")

        if status == "success":
            a["successes"] += 1
        elif status == "error":
            a["errors"] += 1
            err_type = e.get("error_type", "Unknown")
            a["error_types"][err_type] += 1
        elif status == "recovered":
            a["recoveries"] += 1

        if e.get("sla_breach"):
            a["sla_breaches"] += 1

        latency = e.get("elapsed_seconds", 0)
        if latency > 0:
            a["total_latency"] += latency
            a["latencies"].append(latency)

    # Compute summary stats
    result = {}
    for name, a in sorted(agents.items()):
        calls = a["calls"]
        latencies = sorted(a["latencies"])
        result[name] = {
            "calls": calls,
            "success_rate": round(a["successes"] / calls * 100, 1) if calls else 0,
            "error_rate": round(a["errors"] / calls * 100, 1) if calls else 0,
            "recovery_rate": round(a["recoveries"] / calls * 100, 1) if calls else 0,
            "sla_breach_rate": round(a["sla_breaches"] / calls * 100, 1) if calls else 0,
            "avg_latency_s": round(a["total_latency"] / len(latencies), 2) if latencies else 0,
            "p50_latency_s": latencies[len(latencies) // 2] if latencies else 0,
            "p95_latency_s": latencies[int(len(latencies) * 0.95)] if latencies else 0,
            "max_latency_s": max(latencies) if latencies else 0,
            "top_errors": dict(sorted(a["error_types"].items(), key=lambda x: -x[1])[:3]),
        }

    return result


def compute_pipeline_runs(entries: list[dict]) -> list[dict]:
    """Group entries into pipeline runs by topic + approximate time window."""
    runs = []
    current_run = None
    last_time = None

    for e in sorted(entries, key=lambda x: x.get("timestamp", "")):
        topic = e.get("topic", "")
        ts = e.get("timestamp", "")

        try:
            entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue

        # New run if topic changes or >30min gap
        if (current_run is None or
            topic != current_run["topic"] or
            (last_time and (entry_time - last_time).total_seconds() > 1800)):

            if current_run:
                current_run["duration_s"] = round(
                    (last_time - current_run["_start_time"]).total_seconds(), 1
                )
                del current_run["_start_time"]
                runs.append(current_run)

            current_run = {
                "topic": topic,
                "started": ts,
                "_start_time": entry_time,
                "stages": 0,
                "errors": 0,
                "sla_breaches": 0,
                "total_latency": 0.0,
            }

        current_run["stages"] += 1
        if e.get("status") == "error":
            current_run["errors"] += 1
        if e.get("sla_breach"):
            current_run["sla_breaches"] += 1
        current_run["total_latency"] += e.get("elapsed_seconds", 0)
        last_time = entry_time

    # Finalize last run
    if current_run and last_time:
        current_run["duration_s"] = round(
            (last_time - current_run["_start_time"]).total_seconds(), 1
        )
        del current_run["_start_time"]
        runs.append(current_run)

    return runs


def get_health_summary(hours: float = 168) -> dict:
    """Return a pipeline health summary for the dashboard."""
    entries = load_entries(hours)
    if not entries:
        return {"status": "no_data", "message": "No diagnostic entries found"}

    agent_stats = compute_agent_stats(entries)
    runs = compute_pipeline_runs(entries)

    total_calls = sum(a["calls"] for a in agent_stats.values())
    total_errors = sum(
        a["calls"] * a["error_rate"] / 100 for a in agent_stats.values()
    )
    total_sla_breaches = sum(
        a["calls"] * a["sla_breach_rate"] / 100 for a in agent_stats.values()
    )

    # Find worst-performing agents
    error_hotspots = sorted(
        [(name, stats) for name, stats in agent_stats.items() if stats["error_rate"] > 0],
        key=lambda x: -x[1]["error_rate"]
    )[:3]

    sla_hotspots = sorted(
        [(name, stats) for name, stats in agent_stats.items() if stats["sla_breach_rate"] > 0],
        key=lambda x: -x[1]["sla_breach_rate"]
    )[:3]

    # Determine overall health
    overall_error_rate = (total_errors / total_calls * 100) if total_calls else 0
    if overall_error_rate < 2:
        health = "healthy"
    elif overall_error_rate < 10:
        health = "degraded"
    else:
        health = "unhealthy"

    return {
        "status": health,
        "period_hours": hours,
        "total_calls": total_calls,
        "overall_error_rate": round(overall_error_rate, 1),
        "overall_sla_breach_rate": round(
            (total_sla_breaches / total_calls * 100) if total_calls else 0, 1
        ),
        "pipeline_runs": len(runs),
        "successful_runs": sum(1 for r in runs if r["errors"] == 0),
        "agent_stats": agent_stats,
        "error_hotspots": [
            {"agent": name, "error_rate": stats["error_rate"], "top_errors": stats["top_errors"]}
            for name, stats in error_hotspots
        ],
        "sla_hotspots": [
            {"agent": name, "breach_rate": stats["sla_breach_rate"],
             "avg_latency": stats["avg_latency_s"], "p95_latency": stats["p95_latency_s"]}
            for name, stats in sla_hotspots
        ],
        "recent_runs": runs[-5:] if runs else [],
    }


def print_report(hours: float = 168):
    """Print a human-readable diagnostic report."""
    summary = get_health_summary(hours)

    if summary["status"] == "no_data":
        print("No diagnostic data found.")
        return

    print(f"\n{'='*60}")
    print(f"  PIPELINE DIAGNOSTICS — last {hours:.0f}h")
    print(f"{'='*60}")
    print(f"  Status: {summary['status'].upper()}")
    print(f"  Total API calls: {summary['total_calls']}")
    print(f"  Error rate: {summary['overall_error_rate']}%")
    print(f"  SLA breach rate: {summary['overall_sla_breach_rate']}%")
    print(f"  Pipeline runs: {summary['pipeline_runs']} "
          f"({summary['successful_runs']} clean)")

    if summary["error_hotspots"]:
        print("\n  Error Hotspots:")
        for h in summary["error_hotspots"]:
            print(f"    {h['agent']}: {h['error_rate']}% error rate — {h['top_errors']}")

    if summary["sla_hotspots"]:
        print("\n  SLA Hotspots:")
        for h in summary["sla_hotspots"]:
            print(f"    {h['agent']}: {h['breach_rate']}% breaches "
                  f"(avg {h['avg_latency']}s, p95 {h['p95_latency']}s)")

    print("\n  Per-Agent Stats:")
    for name, stats in summary["agent_stats"].items():
        print(f"    {name}: {stats['calls']} calls, "
              f"{stats['success_rate']}% success, "
              f"avg {stats['avg_latency_s']}s")

    if summary["recent_runs"]:
        print("\n  Recent Runs:")
        for run in summary["recent_runs"]:
            status = "OK" if run["errors"] == 0 else f"{run['errors']} errors"
            print(f"    {run['topic'][:50]} — {run['stages']} stages, "
                  f"{run['duration_s']}s, {status}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    import sys
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 168
    print_report(hours)
