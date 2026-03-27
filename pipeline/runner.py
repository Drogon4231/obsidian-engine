"""StageRunner — encapsulates stage execution, skip logic, and state recording."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.log import get_logger
from pipeline.state import save_state

logger = get_logger(__name__)

if TYPE_CHECKING:
    from pipeline.context import PipelineContext


class StageRunner:
    """Manages stage execution lifecycle: skip checks, timing, marking, budget."""

    def __init__(self, ctx: PipelineContext) -> None:
        self.ctx = ctx

    # ── Skip gate ────────────────────────────────────────────────────────────

    def done(self, stage: int) -> bool:
        """Check if a numbered stage can be skipped on resume."""
        from pipeline.validators import validate_stage_output

        ctx = self.ctx
        if not ctx.resume or stage not in ctx.state.get("completed_stages", []):
            return False
        return validate_stage_output(stage, ctx.state.get(f"stage_{stage}"))

    # ── State recording (locked) ─────────────────────────────────────────────

    def mark(self, stage: int, data, elapsed: float | None = None) -> None:
        """Record numbered stage completion under lock + save state."""
        ctx = self.ctx
        with ctx.stage_lock:
            ctx.state[f"stage_{stage}"] = data
            if stage not in ctx.state["completed_stages"]:
                ctx.state["completed_stages"].append(stage)
            if elapsed is not None:
                timings = ctx.state.setdefault("stage_timings", {})
                timings[str(stage)] = elapsed
            save_state(ctx.state, ctx.state_path)

    def mark_metadata(self, key: str, value) -> None:
        """Set arbitrary state key + save under lock (for parallel phases)."""
        ctx = self.ctx
        with ctx.stage_lock:
            ctx.state[key] = value
            save_state(ctx.state, ctx.state_path)

    # ── Unlocked save (sequential phases only) ───────────────────────────────

    def save_state_unlocked(self) -> None:
        """Save state without lock — only call when no parallel threads are alive."""
        save_state(self.ctx.state, self.ctx.state_path)

    # ── Numbered stage execution ─────────────────────────────────────────────

    def run_stage(self, num: int, name: str, fn, *args):
        """Execute a numbered pipeline stage with skip check, timing, recovery."""
        ctx = self.ctx
        if num < ctx.from_stage or self.done(num):
            logger.info(f"[Stage {num:02d}] {name}: SKIPPED")
            return ctx.state.get(f"stage_{num}")

        logger.info(f"\n{'='*60}")
        logger.info(f"  STAGE {num:02d} — {name.upper()}")
        logger.info(f"{'='*60}")

        t0 = time.time()
        try:
            result = fn(*args)
        except Exception as stage_err:
            try:
                from core import pipeline_doctor
                result = pipeline_doctor.intervene(num, name, fn, args, stage_err, recent_logs=[])
            except ImportError:
                raise stage_err
            except Exception as doctor_err:
                logger.warning(f"[Stage {num:02d}] Pipeline doctor also failed: {doctor_err}")
                raise stage_err

        elapsed = round(time.time() - t0, 1)
        self.mark(num, result, elapsed=elapsed)
        logger.info(f"[Stage {num:02d}] \u2713 Done in {elapsed}s")

        # Budget check after each stage completes
        if ctx.budget_cap > 0:
            try:
                from core.cost_tracker import check_budget
                check_budget(ctx.budget_cap, name)
            except ImportError:
                pass
            # BudgetExceededError propagates up

        return result

    # ── Short stage execution (string keys, locked) ──────────────────────────

    def run_short_stage(self, key: str, name: str, fn, *args):
        """Short video pipeline stages — tracked separately with string keys."""
        ctx = self.ctx
        completed = ctx.state.get("completed_short_stages") or []
        if key in completed:
            logger.info(f"  SHORT STAGE \u2014 {name.upper()}: SKIPPED")
            result = ctx.state.get(f"stage_{key}")
            if not result:
                logger.warning(f"  \u26a0\ufe0f  SHORT STAGE \u2014 {name}: state key 'stage_{key}' missing on resume \u2014 downstream stages may fail")
            return result

        logger.info(f"\n{'='*60}")
        logger.info(f"  SHORT STAGE \u2014 {name.upper()}")
        logger.info(f"{'='*60}")

        t0 = time.time()
        result = fn(*args)
        elapsed = round(time.time() - t0, 1)

        with ctx.stage_lock:
            ctx.state[f"stage_{key}"] = result
            completed = ctx.state.get("completed_short_stages") or []  # re-read under lock
            completed.append(key)
            ctx.state["completed_short_stages"] = completed
            save_state(ctx.state, ctx.state_path)

        logger.info(f"  SHORT STAGE \u2014 {name}: Done in {elapsed}s")
        return result
