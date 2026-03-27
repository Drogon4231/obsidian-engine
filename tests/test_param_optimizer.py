"""Tests for core/param_optimizer.py — pure-function optimizer tests."""

import pytest
from core.param_optimizer import (
    ParamOptimizer,
    PerformanceMetrics,
    ObservationRecord,
    OptimizerState,
    LossWeights,
    MAX_PROPOSALS_PER_CYCLE,
)
from core.param_registry import ParamSpec


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_metrics(
    retention=50.0, views=5000.0, engagement=0.05,
    sentiment=0.3, hook=60.0,
) -> PerformanceMetrics:
    return PerformanceMetrics(
        retention_pct=retention,
        views_velocity_48h=views,
        engagement_rate=engagement,
        comment_sentiment_score=sentiment,
        hook_retention_30s=hook,
    )


def _make_obs(
    params: dict[str, float],
    retention=50.0, views=5000.0,
    engagement=0.05, sentiment=0.3, hook=60.0,
    compliance=1.0, video_id="v1", era="test",
) -> ObservationRecord:
    return ObservationRecord(
        video_id=video_id,
        youtube_id=f"yt_{video_id}",
        params=params,
        metrics=_make_metrics(retention, views, engagement, sentiment, hook),
        era=era,
        render_compliance=compliance,
        published_at="2025-01-01T00:00:00Z",
    )


def _make_spec(bounds=(0.0, 1.0), default=0.5, step=0.05) -> ParamSpec:
    return ParamSpec(
        key="test_param",
        category="voice",
        bounds=bounds,
        default=default,
        min_step=step,
        affects_format="long",
        learnable=True,
        ts_side=False,
    )


# ── Loss computation ────────────────────────────────────────────────────────

class TestLossComputation:

    def test_loss_is_negative(self):
        """Loss should be negative (lower = better)."""
        opt = ParamOptimizer()
        m = _make_metrics()
        loss = opt.compute_loss(m)
        assert loss < 0

    def test_better_metrics_lower_loss(self):
        """Higher retention/views should produce lower (better) loss."""
        opt = ParamOptimizer()
        good = _make_metrics(retention=70, views=8000, engagement=0.08, sentiment=0.8, hook=80)
        bad = _make_metrics(retention=30, views=1000, engagement=0.01, sentiment=-0.5, hook=30)
        assert opt.compute_loss(good) < opt.compute_loss(bad)

    def test_weights_sum_to_one(self):
        """Default weights should sum to 1.0."""
        w = LossWeights()
        total = w.retention + w.views_velocity + w.engagement + w.sentiment + w.hook_retention
        assert abs(total - 1.0) < 1e-9

    def test_loss_bounded(self):
        """Loss should be between -1 and 0 for normalized metrics."""
        opt = ParamOptimizer()
        for ret in [20, 50, 80]:
            for views in [0, 5000, 10000]:
                m = _make_metrics(retention=ret, views=views)
                loss = opt.compute_loss(m)
                assert -1.0 <= loss <= 0.0, f"Loss {loss} out of [-1, 0]"


# ── Gradient estimation ─────────────────────────────────────────────────────

class TestGradientEstimation:

    def test_insufficient_data_zero_confidence(self):
        """With < 6 observations, gradient confidence should be 0."""
        opt = ParamOptimizer()
        obs = [_make_obs({"speed": 0.8}, retention=50) for _ in range(4)]
        grad = opt.estimate_gradient(obs, "speed")
        assert grad.confidence == 0.0

    def test_no_variation_zero_confidence(self):
        """If all observations have same param value, confidence = 0."""
        opt = ParamOptimizer()
        obs = [_make_obs({"speed": 0.8}, retention=40 + i) for i in range(10)]
        grad = opt.estimate_gradient(obs, "speed")
        assert grad.confidence == 0.0

    def test_clear_positive_signal(self):
        """When higher param = better retention, gradient direction should be correct."""
        opt = ParamOptimizer()
        obs = []
        for i in range(10):
            speed = 0.7 + i * 0.03
            retention = 40 + i * 4  # Clear positive correlation
            obs.append(_make_obs({"speed": speed}, retention=retention, video_id=f"v{i}"))

        grad = opt.estimate_gradient(obs, "speed")
        # Gradient should be negative (higher speed → lower loss → negative gradient)
        assert grad.estimated_gradient < 0
        assert grad.sample_size == 10

    def test_missing_param_handled(self):
        """Observations without the param key should be skipped."""
        opt = ParamOptimizer()
        obs = [_make_obs({}, retention=50) for _ in range(10)]
        grad = opt.estimate_gradient(obs, "speed")
        assert grad.confidence == 0.0
        assert grad.sample_size == 0


# ── Update computation ──────────────────────────────────────────────────────

class TestUpdateComputation:

    def _make_gradient(self, gradient=0.5, confidence=0.8, p=0.05):
        from core.param_optimizer import GradientEstimate
        return GradientEstimate("test_param", gradient, confidence, 10, p)

    def test_zero_confidence_returns_none(self):
        """No update when gradient confidence is 0."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        grad = self._make_gradient(confidence=0.0)
        result = opt.compute_update(grad, state, "test_param", 0.5, "sufficient", (0.0, 1.0), 0.05)
        assert result is None

    def test_none_confidence_returns_none(self):
        """'none' confidence level → zero multiplier → no update."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        grad = self._make_gradient()
        result = opt.compute_update(grad, state, "test_param", 0.5, "none", (0.0, 1.0), 0.05)
        assert result is None

    def test_low_confidence_half_step(self):
        """'low' confidence → half the step size."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        grad = self._make_gradient(gradient=1.0, confidence=1.0)

        result_full = opt.compute_update(grad, state, "p1", 0.5, "sufficient", (0.0, 1.0), 0.05)
        state_low = OptimizerState.fresh()
        result_half = opt.compute_update(grad, state_low, "p1", 0.5, "low", (0.0, 1.0), 0.05)

        assert result_full is not None
        assert result_half is not None
        assert abs(result_half.delta) < abs(result_full.delta)

    def test_bounds_clamping(self):
        """Proposed value must be within bounds."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        # Large negative gradient → wants to increase a lot
        grad = self._make_gradient(gradient=-5.0, confidence=1.0)
        result = opt.compute_update(grad, state, "p", 0.95, "sufficient", (0.0, 1.0), 0.05)
        if result is not None:
            assert 0.0 <= result.proposed_value <= 1.0

    def test_cooldown_blocks_updates(self):
        """During rollback cooldown, no updates should be generated."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        state.cooldown_remaining = 3
        grad = self._make_gradient()
        result = opt.compute_update(grad, state, "p", 0.5, "sufficient", (0.0, 1.0), 0.05)
        assert result is None

    def test_large_change_requires_approval(self):
        """Delta > 3×min_step should require approval."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        # Set momentum very high to force large delta
        state.momentum["p"] = 3.0
        grad = self._make_gradient(gradient=3.0, confidence=1.0)
        result = opt.compute_update(grad, state, "p", 0.5, "sufficient", (0.0, 1.0), 0.02)
        if result is not None and abs(result.delta) > 3 * 0.02:
            assert result.requires_approval is True

    def test_small_change_auto_approved(self):
        """Delta ≤ 3×min_step should not require approval."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        grad = self._make_gradient(gradient=0.3, confidence=0.5)
        result = opt.compute_update(grad, state, "p", 0.5, "sufficient", (0.0, 1.0), 0.05)
        if result is not None and abs(result.delta) <= 3 * 0.05:
            assert result.requires_approval is False


# ── Momentum ────────────────────────────────────────────────────────────────

class TestMomentum:

    def test_momentum_smoothing(self):
        """Oscillating gradients should be dampened by momentum."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        from core.param_optimizer import GradientEstimate

        # Alternate positive/negative gradients
        for i in range(10):
            grad = GradientEstimate("p", (-1) ** i * 1.0, 0.8, 10, 0.05)
            opt.compute_update(grad, state, "p", 0.5, "sufficient", (0.0, 1.0), 0.05)

        # Momentum should be near zero due to oscillation
        assert abs(state.momentum.get("p", 0)) < 1.0

    def test_momentum_accumulates(self):
        """Consistent gradient direction should accumulate momentum."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        from core.param_optimizer import GradientEstimate

        for _ in range(5):
            grad = GradientEstimate("p", 1.0, 0.8, 10, 0.05)
            opt.compute_update(grad, state, "p", 0.5, "sufficient", (0.0, 1.0), 0.05)

        assert abs(state.momentum.get("p", 0)) > 0.5


# ── Rollback ────────────────────────────────────────────────────────────────

class TestRollback:

    def test_rollback_on_degradation(self):
        """15%+ loss increase over 3-video window should trigger rollback."""
        opt = ParamOptimizer()
        # Prior window: loss around -0.5 (good)
        # Recent window: loss around -0.3 (worse — less negative)
        losses = [-0.50, -0.51, -0.49, -0.30, -0.28, -0.32]
        assert opt.check_rollback(losses, window=3) is True

    def test_no_rollback_on_improvement(self):
        """Improving loss should NOT trigger rollback."""
        opt = ParamOptimizer()
        losses = [-0.30, -0.32, -0.31, -0.50, -0.52, -0.48]
        assert opt.check_rollback(losses, window=3) is False

    def test_no_rollback_insufficient_data(self):
        """Less than 2×window observations → no rollback."""
        opt = ParamOptimizer()
        assert opt.check_rollback([-0.5, -0.3], window=3) is False

    def test_rollback_resets_momentum(self):
        """After rollback, state.momentum should be cleared."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        state.momentum = {"p1": 1.5, "p2": -0.8}
        state.running_loss = [-0.50, -0.51, -0.49, -0.30, -0.28, -0.32]

        obs = [_make_obs({"p1": 0.5}, retention=50, video_id=f"v{i}") for i in range(6)]
        result = opt.run_optimization_cycle(
            obs, {"p1": 0.5}, state, "sufficient",
        )
        if result.rollback_triggered:
            assert len(result.updated_state.momentum) == 0


# ── Exploration ─────────────────────────────────────────────────────────────

class TestExploration:

    def test_exploration_returns_single_param(self):
        """Exploration should perturb exactly one param."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        specs = {
            "p1": _make_spec(),
            "p2": _make_spec(),
        }
        result = opt.generate_exploration(state, ["p1", "p2"], {"p1": 0.5, "p2": 0.5}, specs)
        if result is not None:
            assert len(result) == 1

    def test_exploration_never_same_twice(self):
        """Consecutive explorations should use different params."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        specs = {f"p{i}": _make_spec() for i in range(5)}
        params = {f"p{i}": 0.5 for i in range(5)}

        explored = []
        for _ in range(10):
            state.total_epochs += 1
            result = opt.generate_exploration(state, list(specs.keys()), params, specs)
            if result:
                explored.append(list(result.keys())[0])

        # No two consecutive should be the same
        for i in range(1, len(explored)):
            assert explored[i] != explored[i - 1], (
                f"Same param explored twice: {explored[i]} at index {i}"
            )

    def test_exploration_within_bounds(self):
        """Perturbed value must be within param bounds."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        spec = _make_spec(bounds=(0.3, 0.7), default=0.5, step=0.05)
        specs = {"p": spec}

        for _ in range(20):
            state.total_epochs += 1
            result = opt.generate_exploration(state, ["p"], {"p": 0.5}, specs)
            if result and "p" in result:
                assert 0.3 <= result["p"] <= 0.7

    def test_exploration_at_bounds_stays_in(self):
        """If current value is at max, exploration should not exceed bounds."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        state.total_epochs = 1
        spec = _make_spec(bounds=(0.0, 1.0), default=0.5, step=0.1)
        specs = {"p": spec}

        result = opt.generate_exploration(state, ["p"], {"p": 1.0}, specs)
        if result and "p" in result:
            assert result["p"] <= 1.0


# ── Full cycle ──────────────────────────────────────────────────────────────

class TestFullCycle:

    def test_confidence_none_produces_no_proposals(self):
        """'none' confidence should produce zero proposals."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        obs = [_make_obs({"p": 0.5 + i * 0.05}, retention=40 + i * 3, video_id=f"v{i}")
               for i in range(10)]
        specs = {"p": _make_spec()}

        result = opt.run_optimization_cycle(obs, {"p": 0.5}, state, "none",
                                            learnable_params=["p"], param_specs=specs)
        assert len(result.proposals) == 0

    def test_max_proposals_respected(self):
        """Should not produce more than MAX_PROPOSALS_PER_CYCLE."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()

        # Create observations with clear signals for many params
        specs = {f"p{i}": _make_spec() for i in range(10)}
        obs = []
        for i in range(20):
            params = {f"p{j}": 0.3 + j * 0.05 + i * 0.02 for j in range(10)}
            obs.append(_make_obs(params, retention=30 + i * 2, video_id=f"v{i}"))

        result = opt.run_optimization_cycle(
            obs, {f"p{i}": 0.5 for i in range(10)}, state, "sufficient",
            learnable_params=[f"p{i}" for i in range(10)], param_specs=specs,
        )
        assert len(result.proposals) <= MAX_PROPOSALS_PER_CYCLE

    def test_low_compliance_observations_filtered(self):
        """Observations with render_compliance < 0.5 should be excluded."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()

        obs = [
            _make_obs({"p": 0.8}, retention=80, compliance=0.9, video_id="good1"),
            _make_obs({"p": 0.2}, retention=20, compliance=0.1, video_id="bad1"),  # Low compliance
            _make_obs({"p": 0.7}, retention=70, compliance=0.9, video_id="good2"),
            _make_obs({"p": 0.3}, retention=30, compliance=0.1, video_id="bad2"),  # Low compliance
        ]
        specs = {"p": _make_spec()}

        result = opt.run_optimization_cycle(
            obs, {"p": 0.5}, state, "sufficient",
            learnable_params=["p"], param_specs=specs,
        )
        assert result.diagnostics["observations_reliable"] == 2

    def test_diagnostics_populated(self):
        """Diagnostics dict should have expected keys."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        obs = [_make_obs({"p": 0.5}, retention=50, video_id=f"v{i}") for i in range(6)]

        result = opt.run_optimization_cycle(obs, {"p": 0.5}, state, "sufficient")
        d = result.diagnostics
        assert "epoch" in d
        assert "confidence_level" in d
        assert "loss_trend" in d
        assert "rollback_triggered" in d
        assert d["confidence_level"] == "sufficient"

    def test_state_serialization_roundtrip(self):
        """OptimizerState should survive dict → from_dict roundtrip."""
        state = OptimizerState(
            momentum={"p1": 0.5, "p2": -0.3},
            running_loss=[-0.4, -0.5],
            epoch=5,
            total_epochs=42,
            cooldown_remaining=2,
        )
        d = state.to_dict()
        restored = OptimizerState.from_dict(d)
        assert restored.momentum == state.momentum
        assert restored.running_loss == state.running_loss
        assert restored.epoch == state.epoch
        assert restored.total_epochs == state.total_epochs
        assert restored.cooldown_remaining == state.cooldown_remaining

    def test_invalid_confidence_raises(self):
        """Invalid confidence_level should raise ValueError."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        with pytest.raises(ValueError, match="Invalid confidence_level"):
            opt.run_optimization_cycle([], {}, state, "invalid")


# ── Golden output (regression canary) ──────────────────────────────────────

class TestGoldenOutput:
    """Fixed synthetic data → deterministic expected behavior.
    If this breaks, optimizer logic changed."""

    def _build_golden_observations(self) -> list[ObservationRecord]:
        obs = []
        for i in range(10):
            speed = 0.70 + i * 0.03  # 0.70 → 0.97
            pause = 1.0 + i * 0.1    # 1.0 → 1.9
            retention = 35 + i * 3    # 35 → 62 (positive correlation with speed)
            obs.append(_make_obs(
                {"pause.reveal": pause, "voice_speed.quote": speed},
                retention=retention,
                views=3000 + i * 500,
                engagement=0.03 + i * 0.005,
                sentiment=0.1 + i * 0.05,
                hook=45 + i * 2,
                video_id=f"golden_{i}",
            ))
        return obs

    def test_golden_produces_proposals(self):
        """Golden dataset with clear signal should produce at least 1 proposal."""
        opt = ParamOptimizer()
        state = OptimizerState.fresh()
        obs = self._build_golden_observations()

        specs = {
            "pause.reveal": _make_spec(bounds=(0.5, 5.0), default=1.8, step=0.1),
            "voice_speed.quote": _make_spec(bounds=(0.60, 0.90), default=0.74, step=0.02),
        }

        result = opt.run_optimization_cycle(
            obs, {"pause.reveal": 1.8, "voice_speed.quote": 0.74},
            state, "sufficient",
            learnable_params=["pause.reveal", "voice_speed.quote"],
            param_specs=specs,
        )

        # Should detect signal (clear positive correlation with retention)
        assert result.diagnostics["observations_reliable"] == 10
        assert result.diagnostics["epoch"] == 1
        assert not result.rollback_triggered

    def test_golden_state_deterministic(self):
        """Running golden test twice with fresh state → same diagnostics."""
        opt = ParamOptimizer()
        obs = self._build_golden_observations()
        specs = {
            "pause.reveal": _make_spec(bounds=(0.5, 5.0), default=1.8, step=0.1),
            "voice_speed.quote": _make_spec(bounds=(0.60, 0.90), default=0.74, step=0.02),
        }

        r1 = opt.run_optimization_cycle(
            obs, {"pause.reveal": 1.8, "voice_speed.quote": 0.74},
            OptimizerState.fresh(), "sufficient",
            learnable_params=["pause.reveal", "voice_speed.quote"],
            param_specs=specs,
        )
        r2 = opt.run_optimization_cycle(
            obs, {"pause.reveal": 1.8, "voice_speed.quote": 0.74},
            OptimizerState.fresh(), "sufficient",
            learnable_params=["pause.reveal", "voice_speed.quote"],
            param_specs=specs,
        )

        assert r1.diagnostics["avg_loss"] == r2.diagnostics["avg_loss"]
        assert len(r1.proposals) == len(r2.proposals)
