"""Concurrent stress tests for StageRunner thread safety."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline.context import PipelineContext
from pipeline.runner import StageRunner


def _make_ctx(tmp_path: Path) -> PipelineContext:
    """Create a PipelineContext wired to a tmp state file."""
    ctx = PipelineContext(
        topic="thread-safety-test",
        state_path=tmp_path / "state.json",
    )
    ctx.state = {"completed_stages": [], "completed_short_stages": []}
    return ctx


# ---------------------------------------------------------------------------
# 1. Concurrent mark() — no data loss
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("pipeline.runner.save_state")
def test_concurrent_mark_no_data_loss(mock_save, tmp_path):
    """15 threads call mark() on different stages simultaneously.

    Verify all stages in completed_stages, all stage_N keys present, all
    timings recorded.
    """
    ctx = _make_ctx(tmp_path)
    runner = StageRunner(ctx)

    def _mark(stage_num: int):
        runner.mark(stage_num, {"result": stage_num}, elapsed=stage_num * 0.1)

    with ThreadPoolExecutor(max_workers=15) as pool:
        futs = [pool.submit(_mark, i) for i in range(1, 16)]
        for f in as_completed(futs):
            f.result()  # raises if any thread failed

    assert sorted(ctx.state["completed_stages"]) == list(range(1, 16))
    for i in range(1, 16):
        assert ctx.state[f"stage_{i}"] == {"result": i}
    timings = ctx.state["stage_timings"]
    assert len(timings) == 15
    for i in range(1, 16):
        assert str(i) in timings


# ---------------------------------------------------------------------------
# 2. Concurrent mark_metadata() — all keys present
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("pipeline.runner.save_state")
def test_concurrent_mark_metadata_all_keys(mock_save, tmp_path):
    """20 threads call mark_metadata() with distinct keys.

    Verify all 20 keys present with correct values.
    """
    ctx = _make_ctx(tmp_path)
    runner = StageRunner(ctx)

    def _meta(idx: int):
        runner.mark_metadata(f"meta_{idx}", idx * 10)

    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = [pool.submit(_meta, i) for i in range(20)]
        for f in as_completed(futs):
            f.result()

    for i in range(20):
        assert ctx.state[f"meta_{i}"] == i * 10


# ---------------------------------------------------------------------------
# 3. Mixed mark() and mark_metadata() consistency
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("pipeline.runner.save_state")
def test_mixed_mark_and_metadata_consistency(mock_save, tmp_path):
    """Interleaved mark() and mark_metadata() from 20 threads.

    Verify both stage data and metadata keys are consistent.
    """
    ctx = _make_ctx(tmp_path)
    runner = StageRunner(ctx)

    def _work(idx: int):
        if idx % 2 == 0:
            runner.mark(idx, {"even": idx}, elapsed=float(idx))
        else:
            runner.mark_metadata(f"odd_{idx}", idx)

    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = [pool.submit(_work, i) for i in range(20)]
        for f in as_completed(futs):
            f.result()

    # Even indices -> stages
    for i in range(0, 20, 2):
        assert ctx.state[f"stage_{i}"] == {"even": i}
        assert i in ctx.state["completed_stages"]

    # Odd indices -> metadata keys
    for i in range(1, 20, 2):
        assert ctx.state[f"odd_{i}"] == i


# ---------------------------------------------------------------------------
# 4. Concurrent run_stage()
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("pipeline.runner.save_state")
def test_concurrent_run_stage(mock_save, tmp_path):
    """12 concurrent run_stage() calls with simple lambda fns.

    Verify all return correct results and state is fully populated.
    """
    ctx = _make_ctx(tmp_path)
    ctx.from_stage = 1
    ctx.resume = False
    ctx.budget_cap = 0
    runner = StageRunner(ctx)

    def _run(stage_num: int):
        return runner.run_stage(
            stage_num, f"test-{stage_num}", lambda n=stage_num: n * 100
        )

    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(_run, i): i for i in range(1, 13)}
        results = {}
        for f in as_completed(futs):
            stage = futs[f]
            results[stage] = f.result()

    for i in range(1, 13):
        assert results[i] == i * 100
        assert ctx.state[f"stage_{i}"] == i * 100
        assert i in ctx.state["completed_stages"]

    assert len(ctx.state["stage_timings"]) == 12


# ---------------------------------------------------------------------------
# 5. Stage timings complete
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("pipeline.runner.save_state")
def test_stage_timings_complete(mock_save, tmp_path):
    """20 concurrent marks. Verify stage_timings dict has all 20 entries."""
    ctx = _make_ctx(tmp_path)
    runner = StageRunner(ctx)

    def _mark(stage_num: int):
        runner.mark(stage_num, f"data-{stage_num}", elapsed=stage_num + 0.5)

    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = [pool.submit(_mark, i) for i in range(1, 21)]
        for f in as_completed(futs):
            f.result()

    timings = ctx.state["stage_timings"]
    assert len(timings) == 20
    for i in range(1, 21):
        assert str(i) in timings
        assert timings[str(i)] == i + 0.5


# ---------------------------------------------------------------------------
# 6. Stress: 50 concurrent metadata writes across 20 workers
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("pipeline.runner.save_state")
def test_stress_50_concurrent_metadata(mock_save, tmp_path):
    """50 concurrent mark_metadata() calls across 20 workers.

    Verify zero exceptions and all 50 keys present.
    """
    ctx = _make_ctx(tmp_path)
    runner = StageRunner(ctx)
    errors: list[Exception] = []

    def _meta(idx: int):
        try:
            runner.mark_metadata(f"stress_{idx}", {"i": idx})
        except Exception as exc:
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = [pool.submit(_meta, i) for i in range(50)]
        for f in as_completed(futs):
            f.result()

    assert len(errors) == 0, f"Unexpected errors: {errors}"
    for i in range(50):
        assert ctx.state[f"stress_{i}"] == {"i": i}


# ---------------------------------------------------------------------------
# 7. No duplicate completed_stages under contention
# ---------------------------------------------------------------------------

@pytest.mark.unit
@patch("pipeline.runner.save_state")
def test_no_duplicate_completed_stages(mock_save, tmp_path):
    """20 threads mark the same stage simultaneously (barrier for max contention).

    Verify exactly 1 entry in completed_stages.
    """
    ctx = _make_ctx(tmp_path)
    runner = StageRunner(ctx)
    barrier = threading.Barrier(20)

    def _mark(_: int):
        barrier.wait()  # all threads release at once
        runner.mark(99, "shared-data", elapsed=1.0)

    with ThreadPoolExecutor(max_workers=20) as pool:
        futs = [pool.submit(_mark, i) for i in range(20)]
        for f in as_completed(futs):
            f.result()

    assert ctx.state["completed_stages"].count(99) == 1
    assert ctx.state["stage_99"] == "shared-data"
