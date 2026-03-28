#!/usr/bin/env python3
"""
The Obsidian Archive — Webhook Server + Dashboard
Serves monitoring dashboard at GET / and exposes pipeline control API.
Start via scheduler.py (daemon thread) or standalone: python3 webhook_server.py
"""

import os
import sys
import json
import re
import hmac
import time as _time
import threading
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps
from collections import defaultdict

from collections import deque

from flask import Flask, request, jsonify, session, redirect, send_from_directory

sys.path.append(str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from core.pipeline_config import (  # noqa: E402  — must follow load_dotenv()
    WEBHOOK_MAX_TRIGGERS_PER_HOUR,
    WEBHOOK_MAX_CALLS_PER_MINUTE,
    DASHBOARD_PASSWORD,
)

try:
    from core.pipeline_config import (
        SCORING_CONFIG, SCORING_THRESHOLDS,
        SCORING_ADJUSTMENTS_EARLY,
        SCORING_ADJUSTMENTS_GROWING,
        SCORING_ADJUSTMENTS_MATURE,
    )
except ImportError:
    SCORING_CONFIG = {}
    SCORING_THRESHOLDS = {}
    SCORING_ADJUSTMENTS_EARLY = {}
    SCORING_ADJUSTMENTS_GROWING = {}
    SCORING_ADJUSTMENTS_MATURE = {}

BASE_DIR      = Path(__file__).resolve().parent.parent
LESSONS_FILE  = BASE_DIR / "lessons_learned.json"
INSIGHTS_FILE = BASE_DIR / "channel_insights.json"
PORT         = int(os.getenv("PORT", 8080))
TRIGGER_KEY  = os.getenv("TRIGGER_KEY", "")

app   = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(32).hex()
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max request size
_lock = threading.Lock()


# ── Audit logging ────────────────────────────────────────────────────────────

_AUDIT_LOG_DIR = BASE_DIR / "outputs" / "logs"
_AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

_audit_logger = logging.getLogger("obsidian.audit")
_audit_logger.setLevel(logging.INFO)
_audit_logger.propagate = False
_audit_handler = logging.FileHandler(str(_AUDIT_LOG_DIR / "audit.log"))
_audit_handler.setFormatter(logging.Formatter("%(message)s"))
_audit_logger.addHandler(_audit_handler)


def _audit(ip: str, action: str, details: str):
    """Write a structured line to the audit log."""
    ts = datetime.now(timezone.utc).isoformat()
    _audit_logger.info(f"{ts} | {ip} | {action} | {details}")


# ── Rate limiting (in-memory) ────────────────────────────────────────────────

_rate_trigger_log = defaultdict(list)   # ip -> [timestamps]
_rate_api_log = defaultdict(list)       # ip -> [timestamps]
_rate_lock = threading.Lock()


def _cleanup_timestamps(timestamps, window_seconds):
    """Remove timestamps older than the window."""
    cutoff = _time.time() - window_seconds
    return [t for t in timestamps if t > cutoff]


def rate_limit(f):
    """Rate limit decorator for /trigger and /run-analytics endpoints.
    - Max WEBHOOK_MAX_TRIGGERS_PER_HOUR pipeline triggers per hour per IP
    - Max WEBHOOK_MAX_CALLS_PER_MINUTE API calls per minute per IP
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        now = _time.time()

        with _rate_lock:
            # Per-minute API call limit
            _rate_api_log[ip] = _cleanup_timestamps(_rate_api_log[ip], 60)
            if not _rate_api_log[ip]:
                del _rate_api_log[ip]
            elif len(_rate_api_log[ip]) >= WEBHOOK_MAX_CALLS_PER_MINUTE:
                _audit(
                    ip, "RATE_LIMITED",
                    f"exceeded {WEBHOOK_MAX_CALLS_PER_MINUTE} calls/min",
                )
                return jsonify({"error": "Rate limit exceeded"}), 429
            _rate_api_log[ip].append(now)

            # Per-hour trigger limit (only for trigger-like endpoints)
            _rate_trigger_log[ip] = _cleanup_timestamps(_rate_trigger_log[ip], 3600)
            if not _rate_trigger_log[ip]:
                del _rate_trigger_log[ip]
            elif len(_rate_trigger_log[ip]) >= WEBHOOK_MAX_TRIGGERS_PER_HOUR:
                _audit(
                    ip, "RATE_LIMITED",
                    f"exceeded {WEBHOOK_MAX_TRIGGERS_PER_HOUR} triggers/hr",
                )
                return jsonify({"error": "Rate limit exceeded"}), 429
            _rate_trigger_log[ip].append(now)

        return f(*args, **kwargs)
    return wrapped


# ── Input validation ─────────────────────────────────────────────────────────

_INJECTION_PATTERNS = re.compile(
    r"(<\s*script|<\s*/\s*script|javascript\s*:|on\w+\s*=|"
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|UNION|EXEC)\b\s+"
    r"\b(FROM|INTO|TABLE|SET|ALL|WHERE|DATABASE)\b))",
    re.IGNORECASE,
)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_HTML_TAGS = re.compile(r"<[^>]+>")


def _validate_topic(topic: str):
    """Validate and sanitise a topic string. Returns (clean_topic, error_message)."""
    if not topic:
        return topic, None  # empty topic handled downstream

    # Strip HTML tags and control characters
    topic = _HTML_TAGS.sub("", topic)
    topic = _CONTROL_CHARS.sub("", topic).strip()

    if len(topic) < 5:
        return None, "Topic too short (minimum 5 characters)"
    if len(topic) > 200:
        return None, "Topic too long (maximum 200 characters)"
    if _INJECTION_PATTERNS.search(topic):
        return None, "Topic contains disallowed content"

    return topic, None

_state = {
    "running":            False,
    "analytics_running":  False,
    "active_jobs":        {},          # {job_name: started_at_iso}
    "topic":              "",
    "stage":              "",
    "stage_num":          0,
    "short_stage":        "",
    "short_stage_num":    0,
    "last_status":        "idle",
    "log":                [],
    "started_at":         None,
    "finished_at":        None,
    "tuning_version":     0,
}
_proc = None
_last_analytics_trigger = 0


def mark_job_running(name: str):
    """Mark a background job as running (visible in dashboard)."""
    from datetime import datetime, timezone
    with _lock:
        _state["active_jobs"][name] = datetime.now(timezone.utc).isoformat()
        if name == "analytics":
            _state["analytics_running"] = True


def mark_job_done(name: str):
    """Mark a background job as finished."""
    with _lock:
        _state["active_jobs"].pop(name, None)
        if name == "analytics":
            _state["analytics_running"] = False


# ── Auth ──────────────────────────────────────────────────────────────────────

def _check_key():
    k = (request.headers.get("X-Trigger-Key")
         or request.args.get("key"))
    return (not TRIGGER_KEY) or k == TRIGGER_KEY

def require_key(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not _check_key():
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapped


# ── Log helper ────────────────────────────────────────────────────────────────

_LOG_DIR = BASE_DIR / "outputs" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

def _log(line: str):
    # Suppress repeated render progress lines — keep only latest
    is_render = 'Rendered ' in line and '/' in line
    with _lock:
        if is_render and _state["log"] and 'Rendered ' in _state["log"][-1]:
            _state["log"][-1] = line  # replace last render line in-place
        else:
            _state["log"].append(line)
        if len(_state["log"]) > 500:
            _state["log"] = _state["log"][-500:]
    # Persist to log file for historical debugging
    try:
        topic_slug = re.sub(
            r'[^a-z0-9]+', '_',
            _state.get("topic", "unknown").lower(),
        )[:30]
        log_file = _LOG_DIR / f"{topic_slug}.log"
        with open(log_file, "a") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {line}\n")
    except Exception as e:
        _log(f"[Server] Warning: failed to write pipeline log: {e}")


# ── Pipeline runner ───────────────────────────────────────────────────────────

def _run_thread(topic: str, resume_from: int, topic_id: str = None):
    global _proc
    cmd = [sys.executable, str(BASE_DIR / "run_pipeline.py"), topic]
    if resume_from > 1:
        cmd += ["--from-stage", str(resume_from)]

    with _lock:
        _state.update({
            "running":         True,
            "pipeline_done":   False,
            "topic":           topic,
            "stage":           "Initialising...",
            "stage_num":       0,
            "short_stage":     "",
            "short_stage_num": 0,
            "last_status":     "running",
            "log":             [],
            "started_at":      datetime.now(timezone.utc).isoformat(),
            "finished_at":     None,
        })

    try:
        _proc = subprocess.Popen(
            cmd, cwd=str(BASE_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        SHORT_STAGE_MAP = {
            "SHORT SCRIPT": 1, "SHORT STORYBOARD": 2, "SHORT AUDIO": 3,
            "SHORT IMAGES": 4, "SHORT CONVERT": 5, "SHORT RENDER": 6, "SHORT UPLOAD": 7,
        }
        for line in _proc.stdout:
            line = line.rstrip()
            _log(line)
            # Long pipeline stage
            m = re.search(r'STAGE\s+0*(\d+)\s+[—\-]+\s+(.+)', line)
            if m:
                with _lock:
                    _state["stage_num"] = int(m.group(1))
                    _state["stage"]     = m.group(2).strip()
            # Short pipeline stage
            ms = re.search(r'SHORT STAGE\s+[—\-]+\s+(.+)', line)
            if ms:
                stage_name = re.split(r'[:\—\-]', ms.group(1))[0].strip()
                num = SHORT_STAGE_MAP.get(stage_name.upper(), 0)
                if num == 0:
                    continue  # Don't overwrite progress with failed lookup
                with _lock:
                    _state["short_stage_num"] = num
                    _state["short_stage"]     = stage_name

        _proc.wait()
        ok = _proc.returncode == 0
        with _lock:
            # Don't overwrite "killed" status if user killed the pipeline
            if _state.get("_killed"):
                _state.pop("_killed", None)
            else:
                _state["running"]     = False
                _state["last_status"] = "done" if ok else "failed"
                _state["finished_at"] = datetime.now(timezone.utc).isoformat()
                _state["pipeline_done"] = ok
                if ok:
                    _state["stage_num"] = 13
                    _state["stage"]     = "Complete"
        # Save run to history
        try:
            history_file = BASE_DIR / "outputs" / "run_history.json"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history = []
            if history_file.exists():
                try:
                    history = json.loads(history_file.read_text())
                except Exception:
                    history = []
            # Load costs from latest state file
            run_cost = None
            try:
                state_files = sorted(
                    (BASE_DIR / "outputs").glob("*_state.json"),
                    key=lambda p: p.stat().st_mtime,
                )
                if state_files:
                    latest_state = json.loads(
                        state_files[-1].read_text()
                    )
                    run_cost = latest_state.get(
                        "costs", {}
                    ).get("usd_total")
            except Exception as e:
                _log(f"[Server] Warning: failed to load run cost from state file: {e}")
            with _lock:
                _started = _state.get("started_at", "")
                _finished = _state.get("finished_at", "")
                _stages = _state.get("stage_num", 0)
            history.append({
                "topic": topic,
                "status": "done" if ok else "failed",
                "started_at": _started,
                "finished_at": _finished,
                "elapsed_seconds": round(
                    (_time.time() - datetime.fromisoformat(
                        _started
                    ).timestamp()) if _started else 0
                ),
                "cost_usd": run_cost,
                "stages_completed": _stages,
            })
            # Keep last 50 runs
            history = history[-50:]
            history_file.write_text(json.dumps(history, indent=2))
        except Exception as e:
            _log(f"[Server] Failed to save run history: {e}")
        # Mark topic status in Supabase so it doesn't stay in_progress forever
        if topic_id:
            try:
                from clients.supabase_client import mark_topic_status
                mark_topic_status(topic_id, "done" if ok else "failed")
            except Exception as e:
                _log(f"[Server] Warning: failed to mark topic status in Supabase: {e}")
    except Exception as e:
        _log(f"[Server] Thread error: {e}")
        with _lock:
            _state["running"]     = False
            _state["last_status"] = "error"
            _state["finished_at"] = datetime.now(timezone.utc).isoformat()
        # Save failed run to history
        try:
            history_file = BASE_DIR / "outputs" / "run_history.json"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history = []
            if history_file.exists():
                try:
                    history = json.loads(history_file.read_text())
                except Exception:
                    history = []
            with _lock:
                _started = _state.get("started_at", "")
                _finished = _state.get("finished_at", "")
                _stages = _state.get("stage_num", 0)
            history.append({
                "topic": topic,
                "status": "failed",
                "started_at": _started,
                "finished_at": _finished,
                "elapsed_seconds": round(
                    (_time.time() - datetime.fromisoformat(
                        _started
                    ).timestamp()) if _started else 0
                ),
                "cost_usd": None,
                "stages_completed": _stages,
            })
            history = history[-50:]
            history_file.write_text(json.dumps(history, indent=2))
        except Exception as he:
            _log(f"[Server] Failed to save run history: {he}")
        if topic_id:
            try:
                from clients.supabase_client import mark_topic_status
                mark_topic_status(topic_id, "failed")
            except Exception as se:
                _log(f"[Server] Warning: failed to mark topic status as failed in Supabase: {se}")
    finally:
        _proc = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return "OK", 200


@app.route("/status")
@require_key
def status():
    with _lock:
        snap = dict(_state)
    return jsonify(snap)


MAX_SSE_LIFETIME = 3600  # 1 hour — force client reconnect to prevent zombie threads


@app.route("/stream")
@require_key
def stream():
    """Server-Sent Events stream for real-time dashboard updates."""
    def generate():
        last_log_len = 0
        last_stage = 0
        tick_count = 0
        prev_analytics_running = None
        sent_stage_keys = set()
        start_time = _time.time()
        prev_snap_json = ""
        try:
            while True:
                # Self-terminate after MAX_SSE_LIFETIME
                if _time.time() - start_time > MAX_SSE_LIFETIME:
                    msg = json.dumps(
                        {'reason': 'lifetime_exceeded'}
                    )
                    yield f"event: reconnect\ndata: {msg}\n\n"
                    return

                with _lock:
                    snap = dict(_state)
                log = snap.pop("log", [])

                # Only send state when it has changed
                snap_json = json.dumps(snap, sort_keys=True)
                if snap_json != prev_snap_json:
                    prev_snap_json = snap_json
                    yield f"event: state\ndata: {snap_json}\n\n"

                # Send new log lines only
                if len(log) > last_log_len:
                    new_lines = log[last_log_len:]
                    last_log_len = len(log)
                    yield f"event: log\ndata: {json.dumps(new_lines)}\n\n"

                # Send stage change event
                if snap.get("stage_num", 0) != last_stage:
                    last_stage = snap.get("stage_num", 0)
                    stage_msg = json.dumps({
                        'stage_num': last_stage,
                        'stage': snap.get('stage', ''),
                    })
                    yield f"event: stage\ndata: {stage_msg}\n\n"

                # Send cost event every 10s during RUNNING
                if snap.get("running") and tick_count % 10 == 0:
                    try:
                        state_files = sorted(
                            (BASE_DIR / "outputs").glob("*_state.json"),
                            key=lambda p: p.stat().st_mtime
                        )
                        if state_files:
                            state_data = json.loads(state_files[-1].read_text())
                            # Stale-run guard: verify topic matches
                            if state_data.get("topic") == snap.get("topic"):
                                costs = state_data.get("costs", {})
                                cost_msg = json.dumps({
                                    'usd_total': costs.get('usd_total', 0),
                                    'tokens': costs.get('tokens', {}),
                                })
                                yield f"event: cost\ndata: {cost_msg}\n\n"
                    except Exception:
                        pass

                # Send stage_summary updates (cumulative)
                try:
                    summary_path = BASE_DIR / "outputs" / "stage_summary.json"
                    if summary_path.exists():
                        summary_data = json.loads(summary_path.read_text())
                        new_keys = set(summary_data.keys()) - sent_stage_keys
                        if new_keys:
                            sent_stage_keys.update(new_keys)
                            summ_msg = json.dumps(summary_data)
                            yield f"event: stage_summary\ndata: {summ_msg}\n\n"
                except Exception:
                    pass

                # Detect analytics_running True→False edge → send intel_updated
                curr_analytics = snap.get("analytics_running", False)
                if prev_analytics_running is True and curr_analytics is False:
                    intel_msg = json.dumps({'updated': True})
                    yield f"event: intel_updated\ndata: {intel_msg}\n\n"
                prev_analytics_running = curr_analytics

                # Detect tuning override changes → send tuning_updated
                curr_tuning_v = snap.get("tuning_version", 0)
                if not hasattr(generate, '_prev_tuning_v'):
                    generate._prev_tuning_v = curr_tuning_v
                if curr_tuning_v != generate._prev_tuning_v:
                    generate._prev_tuning_v = curr_tuning_v
                    tune_msg = json.dumps(
                        {'version': curr_tuning_v}
                    )
                    yield f"event: tuning_updated\ndata: {tune_msg}\n\n"

                tick_count += 1
                _time.sleep(1)
        except GeneratorExit:
            return

    from flask import Response
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache, no-store',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    })


@app.route("/trigger", methods=["POST"])
@require_key
@rate_limit
def trigger():
    ip = request.remote_addr or "unknown"

    with _lock:
        if _state["running"]:
            _audit(
                ip, "TRIGGER_REJECTED",
                f"pipeline already running for '{_state['topic']}'",
            )
            return jsonify({
                "error": "Pipeline already running",
                "topic": _state["topic"],
            }), 409
        # Claim the running slot immediately to prevent race conditions
        _state["running"] = True

    body        = request.get_json(silent=True) or {}
    topic       = (body.get("topic") or "").strip()
    try:
        resume_from = int(body.get("resume_from") or 1)
    except (ValueError, TypeError):
        resume_from = 1

    # Input validation for user-supplied topic
    if topic:
        topic, err = _validate_topic(topic)
        if err:
            with _lock:
                _state["running"] = False
            _audit(ip, "TRIGGER_INVALID", f"validation failed: {err}")
            return jsonify({"error": err}), 400

    topic_id = None
    if not topic:
        try:
            from clients.supabase_client import get_next_topic
            row   = get_next_topic()
            topic = row["topic"] if row else ""
            if row:
                topic_id = row["id"]
                # get_next_topic() already claimed the topic
                # atomically via claim_topic()
        except Exception as e:
            with _lock:
                _state["running"] = False
            _audit(ip, "TRIGGER_ERROR", f"queue fetch failed: {e}")
            return jsonify({"error": f"Queue fetch failed: {e}"}), 500
        if not topic:
            with _lock:
                _state["running"] = False
            _audit(ip, "TRIGGER_EMPTY", "queue is empty")
            return jsonify({"error": "Queue is empty — add topics first"}), 422

    _audit(
        ip, "TRIGGER_OK",
        f"topic='{topic}' resume_from={resume_from}"
        f" auth={'key' if _check_key() else 'none'}",
    )
    threading.Thread(
        target=_run_thread,
        args=(topic, resume_from, topic_id),
        daemon=True,
    ).start()
    return jsonify({
        "ok": True, "topic": topic,
        "resume_from": resume_from,
    })


@app.route("/trigger-analytics", methods=["POST"])
@require_key
def trigger_analytics():
    global _last_analytics_trigger
    ip = request.remote_addr or "unknown"
    now = _time.time()
    with _lock:
        if now - _last_analytics_trigger < 300:  # 5 minute cooldown
            _audit(
                ip, "ANALYTICS_COOLDOWN",
                "attempted during 5-min cooldown",
            )
            return jsonify({
                "ok": False,
                "message": "Analytics cooldown — try again in 5 minutes",
            }), 429
        _last_analytics_trigger = now

    def _run_analytics():
        mark_job_running("analytics")
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "analytics", BASE_DIR / "agents" / "12_analytics_agent.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.run()
            _log("[Server] Analytics run complete")
            _audit(ip, "ANALYTICS_DONE", "completed successfully")
        except Exception as e:
            _log(f"[Server] Analytics run error: {e}")
            _audit(ip, "ANALYTICS_ERROR", str(e))
        finally:
            mark_job_done("analytics")

    _audit(
        ip, "ANALYTICS_TRIGGERED",
        f"source={'api' if _check_key() else 'unknown'}",
    )
    threading.Thread(target=_run_analytics, daemon=True).start()
    return jsonify({"ok": True, "message": "Analytics agent started"})


@app.route("/kill", methods=["POST"])
@require_key
def kill():
    global _proc
    with _lock:
        proc = _proc
        is_running = _state.get("running", False)
    if proc and is_running:
        proc.terminate()
        try:
            proc.wait(timeout=10)  # Reap zombie process
        except Exception:
            proc.kill()  # Force kill if terminate didn't work
        with _lock:
            _state["running"]     = False
            _state["last_status"] = "killed"
            _state["finished_at"] = datetime.now(timezone.utc).isoformat()
            _state["_killed"]     = True  # Signal to _run_thread
        _log("[Server] Pipeline killed by user")
        return jsonify({"ok": True, "message": "Pipeline terminated"})
    return jsonify({"error": "No pipeline running"}), 400


@app.route("/queue")
@require_key
def queue_list():
    try:
        from clients.supabase_client import get_client
        r = (get_client().table("topics")
             .select("*").order("score", desc=True)
             .execute())
        return jsonify(r.data or [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/queue/add", methods=["POST"])
@require_key
def queue_add():
    body  = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "topic required"}), 400
    topic, err = _validate_topic(topic)
    if err:
        return jsonify({"error": err}), 400
    try:
        from clients.supabase_client import get_client
        r = get_client().table("topics").insert({
            "topic": topic, "status": "queued", "score": 0.5, "source": "manual"
        }).execute()
        return jsonify(r.data[0] if r.data else {"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/queue/delete", methods=["POST"])
@require_key
def queue_delete():
    body = request.get_json(silent=True) or {}
    tid  = body.get("id")
    if not tid:
        return jsonify({"error": "id required"}), 400
    try:
        from clients.supabase_client import get_client
        get_client().table("topics").delete().eq("id", tid).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/videos")
@require_key
def videos():
    try:
        from clients.supabase_client import get_client
        client = get_client()
        vids = (client.table("videos")
                .select("*")
                .order("created_at", desc=True)
                .execute())
        rows   = vids.data or []
        for row in rows:
            try:
                anl = client.table("analytics").select("*") \
                    .eq("video_id", row["id"]) \
                    .order("recorded_at", desc=True).limit(1).execute()
                row["analytics"] = anl.data[0] if anl.data else {}
            except Exception:
                row["analytics"] = {}
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analytics")
@require_key
def analytics():
    if not LESSONS_FILE.exists():
        return jsonify({})
    try:
        with open(LESSONS_FILE) as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/insights")
@require_key
def insights():
    if not INSIGHTS_FILE.exists():
        return jsonify({})
    try:
        with open(INSIGHTS_FILE) as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/config")
@require_key
def scoring_config():
    return jsonify({
        "scoring_config": SCORING_CONFIG,
        "scoring_thresholds": SCORING_THRESHOLDS,
        "scoring_adjustments": {
            "early": SCORING_ADJUSTMENTS_EARLY,
            "growing": SCORING_ADJUSTMENTS_GROWING,
            "mature": SCORING_ADJUSTMENTS_MATURE,
        },
    })


@app.route("/schedule")
@require_key
def get_schedule():
    """Return current schedule configuration from scheduler globals."""
    try:
        import scheduler as sched_mod
        publish_days = getattr(sched_mod, "PUBLISH_DAYS", ["tuesday"])
        publish_time = getattr(sched_mod, "PUBLISH_TIME", "09:00")
        discover_time = getattr(sched_mod, "DISCOVER_TIME", "08:00")
    except Exception:
        publish_days = ["tuesday"]
        publish_time = "09:00"
        discover_time = "08:00"

    entries = [
        {"day": "MON",   "time_utc": discover_time, "job": "TOPIC DISCOVERY"},
        {"day": "DAILY", "time_utc": "06:00",        "job": "ANALYTICS LOOP"},
        {"day": "DAILY", "time_utc": "07:00",        "job": "A/B TITLE CHECK"},
        {"day": "DAILY", "time_utc": "07:30",        "job": "ELEVENLABS CREDITS"},
        {"day": "DAILY", "time_utc": "07:30",        "job": "HEALTH CHECK"},
        {"day": "DAILY", "time_utc": "05:00",        "job": "COMPETITIVE INTEL"},
        {"day": "DAILY", "time_utc": "14:00",        "job": "TAG OPTIMIZATION"},
        {"day": "MON",   "time_utc": "10:00",        "job": "WEEKLY REPORT"},
        {"day": "MON",   "time_utc": "11:00",        "job": "RE-ENGAGEMENT"},
        {"day": "WED",   "time_utc": "10:00",        "job": "COMMUNITY POLL"},
        {"day": "FRI",   "time_utc": "12:00",        "job": "SHORTS FUNNEL"},
        {"day": "3H",    "time_utc": "",             "job": "TREND DETECTION"},
    ]
    for d in publish_days:
        entries.append({
            "day": d[:3].upper(),
            "time_utc": publish_time,
            "job": "FULL PIPELINE",
        })

    return jsonify({
        "schedule": entries,
        "publish_days": publish_days,
        "publish_time_utc": publish_time,
    })


@app.route("/costs")
@require_key
def get_costs():
    """Return cost data from latest pipeline run."""
    try:
        state_files = sorted(
            Path(BASE_DIR / "outputs").glob("*_state.json"),
            key=lambda p: p.stat().st_mtime,
        )
        if not state_files:
            return jsonify({"costs": None, "message": "No pipeline runs found"})
        latest = json.loads(state_files[-1].read_text())
        return jsonify({
            "costs": latest.get("costs", {}),
            "topic": latest.get("topic", ""),
            "status": latest.get("pipeline_status", "unknown"),
            "elapsed_seconds": latest.get("elapsed_seconds", 0),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/history")
@require_key
def run_history():
    history_file = BASE_DIR / "outputs" / "run_history.json"
    if not history_file.exists():
        return jsonify([])
    try:
        return jsonify(json.loads(history_file.read_text()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/music")
@require_key
def music_status():
    """Return music library status: tracks per mood, usage stats."""
    try:
        music_dir = BASE_DIR / "remotion" / "public" / "music"
        usage_file = BASE_DIR / "outputs" / "music_usage.json"
        tracks = {}
        moods = [
            "dark", "tense", "dramatic", "cold",
            "reverent", "wonder", "warmth", "absurdity",
        ]
        if music_dir.exists():
            for f in music_dir.iterdir():
                if f.suffix in (".mp3", ".wav", ".ogg"):
                    name = f.stem.lower()
                    # Detect mood from filename
                    # (handles epidemic_dark_*, dark_01_*, etc.)
                    mood = "unknown"
                    for m in moods:
                        if m in name:
                            mood = m
                            break
                    if mood not in tracks:
                        tracks[mood] = []
                    tracks[mood].append(f.name)
        usage = {}
        if usage_file.exists():
            try:
                usage = json.loads(usage_file.read_text())
            except Exception:
                pass
        return jsonify({
            "tracks_by_mood": tracks,
            "total_tracks": sum(len(v) for v in tracks.values()),
            "moods": list(tracks.keys()),
            "usage": usage,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/trends")
@require_key
def trends_status():
    """Return latest trend detection results if available."""
    try:
        trend_file = BASE_DIR / "outputs" / "trend_results.json"
        if trend_file.exists():
            data = json.loads(trend_file.read_text())
            return jsonify(data)
        return jsonify({"trends": [], "message": "No trend data yet"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/audit")
@require_key
def audit_status():
    """Return image audit log for compliance tracking."""
    try:
        audit_file = BASE_DIR / "outputs" / "image_audit_log.json"
        if audit_file.exists():
            data = json.loads(audit_file.read_text())
            # Return last 50 entries
            if isinstance(data, list):
                return jsonify({"entries": data[-50:], "total": len(data)})
            return jsonify(data)
        return jsonify({"entries": [], "total": 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/diagnostics")
@require_key
def diagnostics_endpoint():
    """Return pipeline diagnostics from agent_wrapper logs."""
    try:
        from scripts.diagnostics import get_health_summary
        hours = float(request.args.get("hours", 168))
        return jsonify(get_health_summary(hours))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Pulse cache infrastructure ───────────────────────────────────────────────

_pulse_lock = threading.Lock()
_pulse_cache = {}


def _cached(key, ttl_seconds, compute_fn, default=None):
    """Thread-safe TTL cache. Returns stale value on error, or default."""
    now = _time.time()
    with _pulse_lock:
        entry = _pulse_cache.get(key)
        if entry and entry["expires"] > now:
            return entry["value"]
    try:
        val = compute_fn()
    except Exception:
        return entry["value"] if entry else default
    with _pulse_lock:
        _pulse_cache[key] = {"value": val, "expires": now + ttl_seconds}
    return val


def _load_run_history(limit=50):
    """Load run history from JSON file. Returns [] on error."""
    path = Path(BASE_DIR / "outputs" / "run_history.json")
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())[-limit:]
    except (json.JSONDecodeError, OSError):
        return []


def _count_errors_24h():
    """Count errors in diagnostic_log.jsonl from last 24 hours."""
    log_path = BASE_DIR / "outputs" / "diagnostic_log.jsonl"
    if not log_path.exists():
        return 0
    try:
        cutoff = _time.time() - 86400
        count = 0
        with open(log_path) as f:
            lines = deque(f, maxlen=500)
        for line in lines:
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", 0)
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                if ts > cutoff and entry.get("status") in ("error", "recovered"):
                    count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0


def _compute_health():
    """Build health status from diagnostic log + scoring config."""
    errors = _count_errors_24h()
    config_issues = []
    try:
        from core.pipeline_doctor import _check_scoring_config
        config_issues = _check_scoring_config()
    except Exception as e:
        _log(f"[Server] Warning: health check config validation failed: {e}")

    if errors > 10 or len(config_issues) > 3:
        return "unhealthy"
    elif errors > 3 or len(config_issues) > 0:
        return "degraded"
    return "healthy"


def _get_queue_depth():
    """Get queue depth from Supabase."""
    try:
        from clients.supabase_client import get_client
        r = (get_client().table("topics")
             .select("id", count="exact")
             .eq("status", "queued").execute())
        return r.count if r.count is not None else len(r.data or [])
    except Exception:
        return 0


def _build_summary(insights, history):
    """Build 5 pre-computed summary signals with fallbacks."""
    signals = []

    # 1. Last run
    if history:
        last = history[-1]
        signals.append({
            "label": "Last Run",
            "value": (
                f"{last.get('topic', 'Unknown')}"
                f" — {last.get('status', 'unknown')}"
            ),
            "type": "info",
        })
    else:
        signals.append({"label": "Last Run", "value": "No runs yet", "type": "neutral"})

    # 2. Best era
    era_perf = insights.get("era_performance", {})
    if era_perf:
        best_era = max(
            era_perf.items(),
            key=lambda x: x[1].get("avg_views", 0),
            default=(None, None),
        )
        if best_era[0]:
            signals.append({
                "label": "Best Era",
                "value": best_era[0],
                "type": "success",
            })
        else:
            signals.append({
            "label": "Best Era",
            "value": "Awaiting era data",
            "type": "neutral",
        })
    else:
        signals.append({
            "label": "Best Era",
            "value": "Awaiting era data",
            "type": "neutral",
        })

    # 3. Retention trend
    retention = insights.get("retention_analysis", {})
    if retention and len(insights.get("per_video_stats", [])) >= 3:
        avg_ret = retention.get("average_retention_pct", 0)
        signals.append({
            "label": "Retention",
            "value": f"{avg_ret:.0f}% avg",
            "type": "info",
        })
    else:
        signals.append({
            "label": "Retention",
            "value": "Need 3+ videos for trends",
            "type": "neutral",
        })

    # 4. Top audience request
    requests = insights.get("audience_requests", [])
    if requests:
        signals.append({
            "label": "Top Request",
            "value": str(requests[0])[:80],
            "type": "info",
        })
    else:
        signals.append({
            "label": "Top Request",
            "value": "No comment data yet",
            "type": "neutral",
        })

    # 5. System health
    health = _cached("health", 30, _compute_health, default="healthy")
    if health == "healthy":
        signals.append({
            "label": "System",
            "value": "All systems nominal",
            "type": "success",
        })
    elif health == "degraded":
        signals.append({
            "label": "System",
            "value": "Degraded — check health view",
            "type": "warning",
        })
    else:
        signals.append({
            "label": "System",
            "value": "Unhealthy — check health view",
            "type": "error",
        })

    return {"signals": signals[:5]}


@app.route("/api/pulse")
@require_key
def api_pulse():
    """Lightweight status endpoint for dashboard polling (~10ms)."""
    # Read _state snapshot under _lock (selective fields only — NOT full dict)
    with _lock:
        snap = {k: _state.get(k) for k in (
            "running", "analytics_running", "topic", "stage", "stage_num",
            "last_status", "started_at", "finished_at", "active_jobs",
        )}

    # Cached expensive queries
    queue_depth = _cached("queue_depth", 30, _get_queue_depth, default=0)
    errors_24h = _cached("errors_24h", 30, _count_errors_24h, default=0)
    health = _cached("health", 30, _compute_health, default="healthy")

    last_cost = None
    history = _cached("run_history", 60, _load_run_history, default=[])
    if history:
        last_cost = history[-1].get("cost_usd")

    return jsonify({
        "status": snap["last_status"],
        "running": snap["running"],
        "stage": snap["stage"],
        "stage_num": snap["stage_num"],
        "topic": snap["topic"],
        "started_at": snap["started_at"],
        "finished_at": snap["finished_at"],
        "analytics_running": snap["analytics_running"],
        "active_jobs": snap.get("active_jobs", {}),
        "queue_depth": queue_depth,
        "errors_24h": errors_24h,
        "health": health,
        "last_cost_usd": last_cost,
    })


@app.route("/api/last-error")
@require_key
def api_last_error():
    """Return most recent Pipeline Doctor diagnosis."""
    path = BASE_DIR / "outputs" / "lessons_learned.json"
    if not path.exists():
        return jsonify({"error": "No error data"}), 404
    try:
        data = json.loads(path.read_text())
    except Exception:
        return jsonify({"error": "Could not read error data"}), 500
    interventions = data.get("doctor_interventions", [])
    if not interventions:
        return jsonify({"error": "No interventions"}), 404
    last = interventions[-1]
    return jsonify({
        "stage_name": last.get("stage_name", "Unknown"),
        "stage_num": last.get("stage_num", 0),
        "diagnosis": last.get("diagnosis", ""),
        "root_cause": last.get("root_cause", ""),
        "strategy": last.get("strategy", ""),
        "error": last.get("error", ""),
        "timestamp": last.get("timestamp", ""),
    })


@app.route("/api/run-detail")
@require_key
def api_run_detail():
    """Return full telemetry for the most recent (or specified) run."""
    state_files = sorted(
        (BASE_DIR / "outputs").glob("*_state.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not state_files:
        return jsonify({"error": "No runs found"}), 404
    try:
        data = json.loads(state_files[-1].read_text())
    except Exception:
        return jsonify({"error": "Could not read state file"}), 500

    # Extract stage timings
    stage_timings = data.get("stage_timings", {})
    costs = data.get("costs", {})
    quality = {}
    for key in (
        "hook_scores", "script_doctor_scores",
        "compliance", "qa_tier1", "qa_tier2",
        "predictive_score",
    ):
        val = data.get(key)
        if val is not None:
            quality[key] = val
    seo = data.get("stage_6", {})
    if seo.get("seo_score"):
        quality["seo_score"] = seo["seo_score"]
    fact = data.get("stage_5", {})
    if fact.get("overall_verdict"):
        quality["fact_verification"] = fact["overall_verdict"]

    # Agent performance from diagnostic log
    agents = []
    diag_path = BASE_DIR / "outputs" / "diagnostic_log.jsonl"
    if diag_path.exists():
        try:
            topic_slug = data.get("topic", "")[:40]
            for line in diag_path.read_text().strip().split("\n")[-50:]:
                entry = json.loads(line)
                if topic_slug and topic_slug in entry.get("topic", ""):
                    agents.append({
                        "agent": entry.get("agent", ""),
                        "elapsed_s": entry.get("elapsed_seconds", 0),
                        "sla_s": entry.get("sla_seconds", 0),
                        "model": entry.get("model", ""),
                        "status": entry.get("status", ""),
                    })
        except Exception:
            pass

    # Doctor interventions
    interventions = []
    lessons_path = BASE_DIR / "outputs" / "lessons_learned.json"
    if lessons_path.exists():
        try:
            lessons = json.loads(lessons_path.read_text())
            interventions = lessons.get("doctor_interventions", [])[-5:]
        except Exception:
            pass

    stage_13 = data.get("stage_13", {})
    return jsonify({
        "topic": data.get("topic", ""),
        "status": data.get("pipeline_status", data.get("last_status", data.get("status", ""))),
        "stage_timings": stage_timings,
        "costs": {
            "usd_total": costs.get("usd_total", 0),
            "per_stage": costs.get("per_stage", {}),
            "per_service": costs.get("per_service", {}),
        },
        "tokens": {
            "input": costs.get("tokens", {}).get("input", 0),
            "output": costs.get("tokens", {}).get("output", 0),
            "per_model": costs.get("per_model", {}),
        },
        "quality": quality,
        "output": {
            "youtube_url": stage_13.get("youtube_url"),
            "youtube_id": stage_13.get("video_id"),
            "duration_s": data.get("stage_8", {}).get("total_duration_seconds"),
            "word_count": data.get("stage_4", {}).get("word_count"),
            "scene_count": data.get("stage_7", {}).get("scene_count"),
            "file_size_mb": data.get("stage_12", {}).get("file_size_mb"),
        },
        "agent_performance": agents,
        "doctor_interventions": interventions,
    })


@app.route("/api/dashboard")
@require_key
def api_dashboard():
    """Assembled dashboard payload with selectable sections."""
    sections_param = request.args.get("sections", "summary")
    sections = [s.strip() for s in sections_param.split(",") if s.strip()]
    if not sections:
        sections = ["summary"]

    result = {}

    try:
        from intel.channel_insights import load_insights, get_dna_confidence_block
        insights = load_insights()
    except Exception:
        insights = {}
        def get_dna_confidence_block():
            return ""

    for section in sections:
        if section == "performance":
            result["performance"] = {
                "era_performance": insights.get("era_performance", {}),
                "retention_analysis": insights.get("retention_analysis", {}),
                "per_video_stats": insights.get("per_video_stats", []),
            }
        elif section == "content":
            result["content"] = {
                "content_quality_correlation": insights.get(
                    "content_quality_correlation", {},
                ),
                "tag_performance": insights.get("tag_performance", {}),
                "top_performing_videos": insights.get("top_performing_videos", []),
            }
        elif section == "audience":
            result["audience"] = {
                "demographics": insights.get("demographics", {}),
                "audience_requests": insights.get("audience_requests", []),
                "subscriber_conversion": insights.get("subscriber_conversion", {}),
            }
        elif section == "config":
            try:
                from core.pipeline_config import (
                    SCORING_ADJUSTMENTS_EARLY, SCORING_ADJUSTMENTS_GROWING,
                    SCORING_ADJUSTMENTS_MATURE, SCORING_THRESHOLDS,
                )
                result["config"] = {
                    "scoring_adjustments": {
                        "early": dict(SCORING_ADJUSTMENTS_EARLY),
                        "growing": dict(SCORING_ADJUSTMENTS_GROWING),
                        "mature": dict(SCORING_ADJUSTMENTS_MATURE),
                    },
                    "quality_thresholds": dict(SCORING_THRESHOLDS),
                    "dna_confidence": get_dna_confidence_block(),
                }
            except Exception as e:
                result["config"] = {"config_error": str(e)}
        elif section == "analytics":
            result["analytics"] = {
                "per_video_stats": insights.get("per_video_stats", []),
                "channel_health": insights.get("channel_health", {}),
            }
        elif section == "summary":
            history = _load_run_history()
            result["summary"] = _build_summary(insights, history)
        # Unknown sections silently ignored (return empty dict, not 400)

    return jsonify(result)


# ── Cache-Control ────────────────────────────────────────────────────────────

@app.after_request
def _set_cache_headers(response):
    """Set Cache-Control headers for API responses."""
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-cache, no-store'
        response.headers['Pragma'] = 'no-cache'
    return response


# ── Static file serving for new dashboard ─────────────────────────────────────

_DASHBOARD_DIST_DIR = BASE_DIR / "dashboard" / "dist"
_NEW_DASHBOARD_HTML = None


def _load_new_dashboard():
    """Load new dashboard index.html with TRIGGER_KEY injection."""
    index_path = _DASHBOARD_DIST_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return None


_NEW_DASHBOARD_HTML = _load_new_dashboard()


# ── Tuning API endpoints ─────────────────────────────────────────────────────

def _fetch_override_history():
    """Fetch override history from Supabase (all rows, including reverted)."""
    try:
        from clients.supabase_client import get_client
        resp = get_client().table("tuning_overrides") \
            .select(
                "param_key, value, previous_value,"
                " approved_at, reverted_at, approved_by"
            ) \
            .order("approved_at", desc=True) \
            .limit(50) \
            .execute()
        return [
            {
                "key": r["param_key"],
                "action": "revert" if r.get("reverted_at") else "approve",
                "value": r["value"],
                "previous_value": r.get("previous_value"),
                "timestamp": r.get("reverted_at") or r["approved_at"],
                "approved_by": r.get("approved_by", "dashboard"),
            }
            for r in (resp.data or [])
        ]
    except Exception:
        return []


@app.route("/api/overrides")
@require_key
def get_overrides():
    """Return active overrides + param bounds + defaults + history."""
    from core.param_overrides import (
        load_overrides, PARAM_BOUNDS, PARAM_DEFAULTS, PARAM_MIN_STEP,
    )
    overrides_dict = load_overrides()
    # Convert {key: value} dict to [{key, value}] array for frontend
    overrides = [{"key": k, "value": v} for k, v in overrides_dict.items()]
    history = _fetch_override_history()
    return jsonify({
        "overrides": overrides,
        "bounds": {k: {"min": lo, "max": hi} for k, (lo, hi) in PARAM_BOUNDS.items()},
        "defaults": PARAM_DEFAULTS,
        "min_steps": PARAM_MIN_STEP,
        "history": history,
    })


@app.route("/api/overrides/approve", methods=["POST"])
@require_key
def approve_override():
    """Save a parameter override."""
    from core.param_overrides import save_override
    body = request.get_json(silent=True) or {}
    key = (body.get("key") or "").strip()
    value = body.get("value")
    if not key or value is None:
        return jsonify({"error": "key and value required"}), 400
    try:
        value = float(value)
    except (ValueError, TypeError):
        return jsonify({"error": "value must be a number"}), 400
    try:
        save_override(key, value)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Save failed: {e}"}), 500
    # Notify SSE clients
    with _lock:
        _state["tuning_version"] = _state.get("tuning_version", 0) + 1
    return jsonify({"ok": True, "key": key, "value": value})


@app.route("/api/overrides/revert", methods=["POST"])
@require_key
def revert_override():
    """Revert a parameter to default (soft-delete via reverted_at)."""
    from core.param_overrides import revert_override as do_revert
    body = request.get_json(silent=True) or {}
    key = (body.get("key") or "").strip()
    if not key:
        return jsonify({"error": "key required"}), 400
    try:
        do_revert(key)
    except Exception as e:
        return jsonify({"error": f"Revert failed: {e}"}), 500
    # Notify SSE clients
    with _lock:
        _state["tuning_version"] = _state.get("tuning_version", 0) + 1
    return jsonify({"ok": True, "key": key})


@app.route("/api/correlation")
@require_key
def get_correlation():
    """Return correlation engine results."""
    recs_file = BASE_DIR / "outputs" / "correlation_results.json"
    if recs_file.exists():
        try:
            return jsonify(json.loads(recs_file.read_text()))
        except Exception:
            pass
    # Fallback: check channel_insights.json for summary
    if INSIGHTS_FILE.exists():
        try:
            insights = json.loads(INSIGHTS_FILE.read_text())
            summary = insights.get("correlation_engine")
            if summary:
                return jsonify(summary)
        except Exception:
            pass
    return jsonify({"layers": {}, "recommendations": [], "maturity": "early"})


@app.route("/api/errors")
@require_key
def api_errors():
    try:
        hours = int(request.args.get("hours", 24))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid 'hours' parameter"}), 400
    from core.observability import get_error_summary
    return jsonify(get_error_summary(hours))


@app.route("/api/traces")
@require_key
def api_traces():
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid 'limit' parameter"}), 400
    agent_filter = request.args.get("agent", "")
    trace_path = BASE_DIR / "outputs" / "agent_traces.jsonl"
    if not trace_path.exists():
        return jsonify([])
    from collections import deque
    with open(trace_path) as f:
        lines = deque(f, maxlen=limit * 2)
    entries = []
    for line in reversed(list(lines)):
        try:
            entry = json.loads(line)
            if agent_filter and entry.get("agent") != agent_filter:
                continue
            entries.append(entry)
            if len(entries) >= limit:
                break
        except Exception:
            continue
    return jsonify(entries)


@app.route("/api/agent-stats")
@require_key
def api_agent_stats():
    try:
        days = int(request.args.get("days", 7))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid 'days' parameter"}), 400
    from core.observability import get_agent_stats
    return jsonify(get_agent_stats(days))


# ── Optimizer API endpoints ──────────────────────────────────────────────────

@app.route("/api/optimizer/status")
@require_key
def api_optimizer_status():
    """Optimizer state: epoch, confidence, exploration, losses, pending approvals."""
    try:
        from core.param_history import load_optimizer_state, is_optimizer_enabled, load_pending_approvals
        state = load_optimizer_state()
        enabled = is_optimizer_enabled()
        pending = load_pending_approvals() or []
        return jsonify({
            "enabled": enabled,
            "state": state,
            "pending_approvals_count": len(pending),
        })
    except Exception as e:
        return jsonify({"error": str(e), "state": None}), 200


@app.route("/api/optimizer/history")
@require_key
def api_optimizer_history():
    """Last N optimizer cycles from JSONL log."""
    try:
        limit = int(request.args.get("limit", 50))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid 'limit' parameter"}), 400
    log_path = BASE_DIR / "outputs" / "optimizer_log.jsonl"
    entries = []
    if log_path.exists():
        try:
            lines = log_path.read_text().strip().split("\n")
            for line in lines[-limit:]:
                try:
                    entries.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    pass
        except Exception:
            pass
    return jsonify(entries)


@app.route("/api/optimizer/proposals")
@require_key
def api_optimizer_proposals():
    """List pending optimizer proposals awaiting human approval."""
    try:
        from core.param_history import load_pending_approvals
        pending = load_pending_approvals() or []
        return jsonify({"proposals": pending, "count": len(pending)})
    except Exception as e:
        return jsonify({"error": str(e), "proposals": []}), 200


@app.route("/api/optimizer/approve", methods=["POST"])
@require_key
def api_optimizer_approve():
    """Approve a pending optimizer proposal by index."""
    try:
        data = request.get_json(silent=True) or {}
        index = data.get("index")
        if index is None:
            return jsonify({"error": "Missing 'index' field"}), 400

        from core.param_history import load_pending_approvals, save_pending_approvals, save_override_batch
        pending = load_pending_approvals() or []

        if not isinstance(index, int) or index < 0 or index >= len(pending):
            return jsonify({"error": f"Invalid index {index}, {len(pending)} proposals pending"}), 400

        proposal = pending.pop(index)
        save_pending_approvals(pending)

        # Apply the approved override
        param_key = proposal.get("param_key", "")
        proposed_value = proposal.get("proposed_value")
        if param_key and proposed_value is not None:
            save_override_batch({param_key: proposed_value}, approved_by="dashboard")

        return jsonify({"approved": proposal, "remaining": len(pending)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/optimizer/reject", methods=["POST"])
@require_key
def api_optimizer_reject():
    """Reject a pending optimizer proposal by index."""
    try:
        data = request.get_json(silent=True) or {}
        index = data.get("index")
        if index is None:
            return jsonify({"error": "Missing 'index' field"}), 400

        from core.param_history import load_pending_approvals, save_pending_approvals
        pending = load_pending_approvals() or []

        if not isinstance(index, int) or index < 0 or index >= len(pending):
            return jsonify({"error": f"Invalid index {index}, {len(pending)} proposals pending"}), 400

        rejected = pending.pop(index)
        save_pending_approvals(pending)
        return jsonify({"rejected": rejected, "remaining": len(pending)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/optimizer/pause", methods=["POST"])
@require_key
def api_optimizer_pause():
    """Kill switch: pause/resume the optimizer."""
    try:
        data = request.get_json(silent=True) or {}
        enabled = data.get("enabled", False)

        from clients.supabase_client import get_client
        get_client().table("kv_store").upsert(
            {"key": "optimizer_enabled", "value": enabled},
            on_conflict="key",
        ).execute()

        return jsonify({"optimizer_enabled": enabled})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Setup Wizard API ─────────────────────────────────────────────────────────

_SETUP_API_KEYS = [
    {"key": "ANTHROPIC_API_KEY", "label": "Anthropic (Claude)", "required": True,
     "help": "https://console.anthropic.com", "category": "llm"},
    {"key": "ELEVENLABS_API_KEY", "label": "ElevenLabs (TTS)", "required": True,
     "help": "https://elevenlabs.io", "category": "tts"},
    {"key": "FAL_KEY", "label": "fal.ai (Images)", "required": True,
     "help": "https://fal.ai/dashboard/keys", "category": "images"},
    {"key": "PEXELS_API_KEY", "label": "Pexels (Stock Footage)", "required": True,
     "help": "https://www.pexels.com/api/new/", "category": "footage"},
    {"key": "SUPABASE_URL", "label": "Supabase URL", "required": False,
     "help": "https://supabase.com", "category": "database"},
    {"key": "SUPABASE_KEY", "label": "Supabase Key", "required": False,
     "help": "https://supabase.com", "category": "database"},
    {"key": "TELEGRAM_BOT_TOKEN", "label": "Telegram Bot Token", "required": False,
     "help": "https://t.me/BotFather", "category": "notifications"},
    {"key": "TELEGRAM_CHAT_ID", "label": "Telegram Chat ID", "required": False,
     "help": "https://t.me/userinfobot", "category": "notifications"},
]


@app.route("/api/setup/status")
@require_key
def api_setup_status():
    """Return setup status: which keys are configured, current profile, providers."""
    keys_status = []
    for entry in _SETUP_API_KEYS:
        val = os.getenv(entry["key"], "")
        keys_status.append({
            **entry,
            "configured": bool(val and val.strip()),
        })

    # Read current profile
    profile = "documentary"
    try:
        from core.config import cfg
        profile = cfg.get("profile", "documentary")
    except Exception:
        pass

    # List available profiles
    profiles_dir = BASE_DIR / "profiles"
    available_profiles = []
    if profiles_dir.exists():
        for f in sorted(profiles_dir.glob("*.yaml")):
            if f.name.startswith("_"):
                continue
            name = f.stem
            # Read first few lines for description
            desc = ""
            try:
                with open(f) as fh:
                    for line in fh:
                        if line.strip().startswith("description:"):
                            desc = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
            available_profiles.append({"name": name, "description": desc})

    # Current providers
    providers = {}
    try:
        from core.config import cfg
        psec = cfg.get("providers")
        if psec:
            for ptype in ["llm", "tts", "images", "footage", "upload"]:
                section = psec.get(ptype)
                if section:
                    providers[ptype] = section.get("name") or section.get("provider", "")
    except Exception:
        pass

    # Available providers
    try:
        from providers.registry import list_providers
        available_providers = list_providers()
    except Exception:
        available_providers = {}

    # Check if setup is complete (all required keys present)
    required_configured = all(
        k["configured"] for k in keys_status if k["required"]
    )

    return jsonify({
        "keys": keys_status,
        "profile": profile,
        "available_profiles": available_profiles,
        "providers": providers,
        "available_providers": available_providers,
        "setup_complete": required_configured,
    })


@app.route("/api/setup/validate", methods=["POST"])
@require_key
def api_setup_validate():
    """Validate an API key by making a lightweight test call."""
    data = request.get_json(silent=True) or {}
    key_name = data.get("key", "")
    key_value = data.get("value", "")

    if not key_name or not key_value:
        return jsonify({"valid": False, "error": "Missing key name or value"}), 400

    result = {"key": key_name, "valid": False, "error": ""}

    try:
        if key_name == "ANTHROPIC_API_KEY":
            import requests
            r = requests.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": key_value,
                    "anthropic-version": "2023-06-01",
                },
                timeout=10,
            )
            result["valid"] = r.status_code == 200

        elif key_name == "ELEVENLABS_API_KEY":
            import requests
            r = requests.get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": key_value},
                timeout=10,
            )
            result["valid"] = r.status_code == 200
            if result["valid"]:
                info = r.json()
                sub = info.get("subscription", {})
                result["info"] = {
                    "character_limit": sub.get("character_limit", 0),
                    "character_count": sub.get("character_count", 0),
                }

        elif key_name == "FAL_KEY":
            # fal.ai doesn't have a simple validation endpoint,
            # but we can check format
            result["valid"] = key_value.startswith("fal_") or len(key_value) > 20
            if not result["valid"]:
                result["error"] = "Key should start with 'fal_'"

        elif key_name == "PEXELS_API_KEY":
            import requests
            r = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": key_value},
                params={"query": "test", "per_page": 1},
                timeout=10,
            )
            result["valid"] = r.status_code == 200

        elif key_name in ("SUPABASE_URL", "SUPABASE_KEY"):
            # Just check format
            if key_name == "SUPABASE_URL":
                result["valid"] = key_value.startswith("http")
            else:
                result["valid"] = len(key_value) > 20
        elif key_name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            result["valid"] = len(key_value) > 5
        else:
            result["error"] = f"Unknown key: {key_name}"

        if not result["valid"] and not result["error"]:
            result["error"] = "Key validation failed"

    except Exception as e:
        result["error"] = str(e)

    return jsonify(result)


@app.route("/api/setup/save", methods=["POST"])
@require_key
def api_setup_save():
    """Save setup configuration to .env and obsidian.yaml."""
    data = request.get_json(silent=True) or {}
    saved = []
    errors = []

    # Save API keys to .env
    keys_to_save = data.get("keys", {})
    if keys_to_save:
        env_path = BASE_DIR / ".env"
        try:
            # Read existing .env
            existing = {}
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            existing[k.strip()] = v.strip()

            # Update with new keys
            for k, v in keys_to_save.items():
                if v and v.strip():
                    existing[k] = v.strip()
                    # Also set in current process
                    os.environ[k] = v.strip()
                    saved.append(k)

            # Write .env
            with open(env_path, "w") as f:
                f.write("# Obsidian Engine — Environment Configuration\n")
                f.write("# Auto-saved by Setup Wizard\n\n")
                for k, v in sorted(existing.items()):
                    f.write(f"{k}={v}\n")

        except Exception as e:
            errors.append(f"Failed to save .env: {e}")

    # Save profile to obsidian.yaml
    profile = data.get("profile")
    providers_config = data.get("providers")
    if profile or providers_config:
        yaml_path = BASE_DIR / "obsidian.yaml"
        try:
            content = yaml_path.read_text()

            if profile:
                import re
                content = re.sub(
                    r'^profile:\s*\S+',
                    f'profile: {profile}',
                    content,
                    flags=re.MULTILINE,
                )
                saved.append(f"profile={profile}")

            if providers_config:
                for ptype, pname in providers_config.items():
                    import re
                    # Find the provider section and update the name
                    pattern = rf'(  {ptype}:\n    name:\s*)\S+'
                    replacement = rf'\g<1>{pname}'
                    content = re.sub(pattern, replacement, content)
                    saved.append(f"providers.{ptype}={pname}")

            yaml_path.write_text(content)

        except Exception as e:
            errors.append(f"Failed to save obsidian.yaml: {e}")

    return jsonify({
        "saved": saved,
        "errors": errors,
        "success": len(errors) == 0,
    })


def require_login(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        # If no password set, skip auth
        if not DASHBOARD_PASSWORD:
            return f(*args, **kwargs)
        if not session.get('authenticated'):
            # For API calls, return 401
            is_api = (
                request.headers.get('Accept', '')
                .startswith('application/json')
                or request.path.startswith('/api')
            )
            if is_api:
                return jsonify({"error": "Not authenticated"}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapped


@app.route("/assets/<path:filename>")
@require_login
def dashboard_assets(filename):
    """Serve dashboard static assets from dist/assets/."""
    assets_dir = _DASHBOARD_DIST_DIR / "assets"
    if not assets_dir.exists():
        return "Not found", 404
    return send_from_directory(str(assets_dir), filename)


@app.route("/login", methods=["GET", "POST"])
def login():
    if not DASHBOARD_PASSWORD:
        return redirect("/")
    if request.method == "POST":
        pw = request.form.get("password", "")
        if hmac.compare_digest(pw, DASHBOARD_PASSWORD):
            session['authenticated'] = True
            return redirect("/")
        return (
            _LOGIN_HTML.replace("__ERROR__", "Invalid password"),
            200,
            {"Content-Type": "text/html"},
        )
    return (
        _LOGIN_HTML.replace("__ERROR__", ""),
        200,
        {"Content-Type": "text/html"},
    )


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@require_login
def dashboard():
    # Serve new Preact dashboard if built, else fall back to old HTML
    if _NEW_DASHBOARD_HTML:
        html = _NEW_DASHBOARD_HTML.replace("__TRIGGER_KEY__", TRIGGER_KEY)
    else:
        html = _DASHBOARD_HTML.replace("__TRIGGER_KEY__", TRIGGER_KEY)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# ── Public start function (called by scheduler.py) ───────────────────────────

def start_server():
    """Start Flask in a daemon thread. Returns immediately."""
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    t = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0", port=PORT, debug=False,
            use_reloader=False, threaded=True,
        ),
        daemon=True,
    )
    t.start()
    print(f"[Server] Dashboard \u2192 http://0.0.0.0:{PORT}")
    return t


# ── Login HTML ────────────────────────────────────────────────────────────────

_LOGIN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OBSIDIAN ARCHIVE — LOGIN</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{height:100vh;background:#020408;color:#b0cce0;font-family:'Courier New',monospace;
  display:flex;align-items:center;justify-content:center;
  background-image:linear-gradient(rgba(30,58,90,0.07) 1px,transparent 1px),
  linear-gradient(90deg,rgba(30,58,90,0.07) 1px,transparent 1px);
  background-size:40px 40px}
.login-box{width:380px;max-width:90vw;padding:40px;background:rgba(10,18,32,0.9);
  border:1px solid #1e3a5a;border-top:3px solid #8B5CF6;
  box-shadow:0 0 60px rgba(0,0,0,.8)}
.login-brand{font-size:1rem;letter-spacing:5px;color:#e0f0ff;font-weight:bold;text-align:center;margin-bottom:6px;
  background:linear-gradient(135deg,#8B5CF6,#06B6D4,#10B981);-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;background-clip:text}
.login-sub{font-size:.6rem;letter-spacing:4px;color:#4a7090;text-align:center;margin-bottom:30px}
.login-input{width:100%;background:#0e1a30;border:1px solid #1e3a5a;color:#e0f0ff;
  padding:12px 16px;font-family:'Courier New',monospace;font-size:.85rem;outline:none;
  letter-spacing:2px;margin-bottom:16px;transition:border-color .2s}
.login-input:focus{border-color:#7C3AED}
.login-btn{width:100%;background:linear-gradient(135deg,#7C3AED,#4C1D95);border:none;
  color:#fff;font-weight:bold;padding:14px;font-family:'Courier New',monospace;
  font-size:.85rem;letter-spacing:4px;cursor:pointer;transition:all .2s;
  box-shadow:0 0 25px rgba(124,58,237,0.4)}
.login-btn:hover{box-shadow:0 0 40px rgba(124,58,237,0.6);transform:translateY(-1px)}
.login-err{color:#EF4444;font-size:.72rem;text-align:center;margin-top:12px;min-height:18px;letter-spacing:1px}
</style></head><body>
<div class="login-box">
<div class="login-brand">OBSIDIAN ARCHIVE</div>
<div class="login-sub">PIPELINE CONTROL INTERFACE</div>
<form method="POST">
<input class="login-input" type="password" name="password"
  placeholder="ENTER ACCESS CODE" autofocus>
<button class="login-btn" type="submit">AUTHENTICATE</button>
</form>
<div class="login-err">__ERROR__</div>
</div></body></html>"""



# ── Dashboard HTML ────────────────────────────────────────────────────────────

_DASHBOARD_HTML_FILE = BASE_DIR / "dashboard.html"

def _load_dashboard():
    """Load dashboard HTML from file."""
    try:
        return _DASHBOARD_HTML_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            "<html><body><h1>Dashboard not found</h1>"
            "<p>Expected: " + str(_DASHBOARD_HTML_FILE)
            + "</p></body></html>"
        )

_DASHBOARD_HTML = _load_dashboard()



if __name__ == "__main__":
    print(f"[Server] Starting standalone on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
