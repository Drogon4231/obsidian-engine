"""Pipeline state persistence."""
import json
import os

from core.log import get_logger

logger = get_logger(__name__)

def load_state(state_path):
    if state_path.exists():
        try:
            with open(state_path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("[State] WARNING: corrupted state file (not a dict) — starting fresh")
                return {}
            return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[State] WARNING: corrupted state file ({e}) — starting fresh")
            return {}
    return {}

def save_state(state, state_path):
    # Write to temp file first, then atomic rename to prevent corruption
    tmp_path = state_path.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(state_path)
