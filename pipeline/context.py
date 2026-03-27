"""PipelineContext — explicit container replacing closure variable capture."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineContext:
    """All state that was previously captured by nested closures in run_pipeline()."""

    # Identity (immutable after init)
    topic: str = ""
    slug: str = ""
    ts: str = ""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    state_path: Path = field(default_factory=lambda: Path("state.json"))
    resume: bool = False
    from_stage: int = 1
    is_experiment: bool = False

    # Mutable state (same dict object throughout lifetime)
    state: dict = field(default_factory=dict)

    # Thread safety
    stage_lock: threading.Lock = field(default_factory=threading.Lock)

    # Budget (loaded once)
    budget_cap: float = 0.0

    # Cost tracking
    cost_run_id: str = ""
    cost_tracker: object = None  # core.cost_tracker module or None

    # Pipeline timing
    start_time: float = field(default_factory=time.time)

    # Agents dict (loaded once by phase_setup, read-only after)
    agents: dict = field(default_factory=dict)

    # Series plan (set in phase_script, read in phase_prod)
    series_plan: dict | None = None

    # Intermediate results (set by each phase, read by later phases)
    research: dict | None = None
    angle: dict | None = None
    blueprint: dict | None = None
    script: dict | None = None
    verification: dict | None = None
    seo: dict | None = None
    scenes_data: dict | None = None
    audio_data: dict | None = None
    footage_data: dict | None = None
    manifest: dict | None = None
    tts_script: dict | None = None
