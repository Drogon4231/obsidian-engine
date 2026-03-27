"""
Topic deduplication store for The Obsidian Archive.
Uses SQLite to store covered topics.
Similarity check: Claude Haiku compares new topic against past topics semantically.
Falls back to keyword matching if Claude is unavailable.
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parent.parent))

DB_PATH = Path(__file__).resolve().parent.parent / "outputs" / "topic_store.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS covered_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        angle TEXT,
        title TEXT,
        youtube_id TEXT,
        covered_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def _claude_similarity_check(new_topic: str, new_angle: str, past_topics: list[dict]) -> tuple[bool, str]:
    """
    Ask Claude Haiku whether the new topic is semantically too similar to any past topic.
    Returns (is_duplicate: bool, matched_topic: str).
    """
    if not past_topics:
        return False, ""

    try:
        from core.agent_wrapper import call_agent

        past_list = "\n".join(
            f"- {r['topic']}" + (f" (angle: {r['angle']})" if r.get("angle") else "")
            for r in past_topics[:30]  # limit to 30 most recent
        )

        result = call_agent(
            "topic_store",
            system_prompt=(
                "You are a content deduplication checker for a history YouTube channel. "
                "Determine if a new topic is too similar to previously covered topics — "
                "meaning it would cover the same core event, person, or angle already done. "
                "Different angles on the same event count as duplicates if they share the same hook/twist. "
                "Respond with JSON only: {\"is_duplicate\": true/false, \"matched\": \"matched topic or empty string\"}"
            ),
            user_prompt=(
                f"NEW TOPIC: {new_topic}"
                + (f"\nNEW ANGLE: {new_angle}" if new_angle else "")
                + f"\n\nPREVIOUSLY COVERED:\n{past_list}"
            ),
            max_tokens=120,
            effort_offset=-1,  # Haiku-level task
        )
        if isinstance(result, dict):
            return bool(result.get("is_duplicate", False)), result.get("matched", "")
    except Exception as e:
        print(f"[topic_store] Claude check failed: {e} — falling back to keyword match")

    return False, ""


def _keyword_match(topic: str, past_topics: list[dict]) -> tuple[bool, str]:
    """Simple keyword fallback: substring match on topic text."""
    topic_lower = topic.lower()
    for row in past_topics:
        row_topic = (row.get("topic") or "").lower()
        if row_topic and (row_topic in topic_lower or topic_lower in row_topic):
            return True, row["topic"]
    return False, ""


def is_duplicate(topic: str, angle: str = "") -> tuple[bool, str]:
    """
    Check if this topic+angle was already covered.
    Returns (is_duplicate: bool, matched_topic: str).
    Uses Claude Haiku for semantic comparison, falls back to keyword match.
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT topic, angle FROM covered_topics ORDER BY covered_at DESC"
    ).fetchall()
    conn.close()

    if not rows:
        return False, ""

    past = [{"topic": r[0], "angle": r[1]} for r in rows]

    # Try Claude semantic check first
    is_dup, matched = _claude_similarity_check(topic, angle, past)
    if is_dup:
        return True, matched

    # Fallback: keyword match
    return _keyword_match(topic, past)


def record_topic(topic: str, angle: str = "", title: str = "", youtube_id: str = "") -> None:
    """Record a covered topic to the store."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO covered_topics (topic, angle, title, youtube_id, covered_at) VALUES (?,?,?,?,?)",
        (topic, angle, title, youtube_id, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()


def list_covered(limit: int = 20) -> list[dict]:
    """Return recent covered topics."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT topic, angle, title, youtube_id, covered_at FROM covered_topics ORDER BY covered_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [{"topic": r[0], "angle": r[1], "title": r[2], "youtube_id": r[3], "covered_at": r[4]} for r in rows]
