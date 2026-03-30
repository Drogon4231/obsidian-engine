"""
Neural-network-inspired parameter optimizer for the Obsidian pipeline.

Pure computation — no I/O, no Supabase, no file access.
Given observations (param snapshots + YouTube metrics), produces update proposals.

Reuses statistical functions from intel/correlation_engine.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict


# ── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class PerformanceMetrics:
    retention_pct: float           # 0-100
    views_velocity_48h: float      # views in first 48h
    engagement_rate: float         # (likes+comments) / views, 0-1
    comment_sentiment_score: float  # -1 to 1
    hook_retention_30s: float      # 0-100, retention at 30s mark


@dataclass
class ObservationRecord:
    video_id: str
    youtube_id: str
    params: dict[str, float]
    metrics: PerformanceMetrics
    era: str
    render_compliance: float  # 0-1, from render_verification
    published_at: str         # ISO datetime


@dataclass
class LossWeights:
    retention: float = 0.35
    views_velocity: float = 0.20
    engagement: float = 0.20
    sentiment: float = 0.10
    hook_retention: float = 0.15


@dataclass
class GradientEstimate:
    param_key: str
    estimated_gradient: float
    confidence: float      # 0-1
    sample_size: int
    p_value: float | None


@dataclass
class UpdateProposal:
    param_key: str
    current_value: float
    proposed_value: float
    delta: float
    gradient: float
    momentum: float
    confidence: float
    requires_approval: bool
    reason: str


@dataclass
class OptimizerState:
    momentum: dict[str, float] = field(default_factory=dict)
    running_loss: list[float] = field(default_factory=list)
    exploration_queue: list[str] = field(default_factory=list)
    exploration_direction: dict[str, int] = field(default_factory=dict)  # +1 or -1
    last_explored_param: str = ""
    epoch: int = 0
    total_epochs: int = 0
    cooldown_remaining: int = 0  # videos remaining in rollback cooldown
    next_exploration: dict[str, float] | None = None
    normalization_min: dict[str, float] = field(default_factory=dict)
    normalization_max: dict[str, float] = field(default_factory=dict)

    @classmethod
    def fresh(cls) -> OptimizerState:
        return cls()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> OptimizerState:
        if not d:
            return cls.fresh()
        return cls(
            momentum=d.get("momentum", {}),
            running_loss=d.get("running_loss", []),
            exploration_queue=d.get("exploration_queue", []),
            exploration_direction=d.get("exploration_direction", {}),
            last_explored_param=d.get("last_explored_param", ""),
            epoch=d.get("epoch", 0),
            total_epochs=d.get("total_epochs", 0),
            cooldown_remaining=d.get("cooldown_remaining", 0),
            next_exploration=d.get("next_exploration"),
            normalization_min=d.get("normalization_min", {}),
            normalization_max=d.get("normalization_max", {}),
        )


@dataclass
class OptimizationResult:
    proposals: list[UpdateProposal]
    rollback_triggered: bool
    rollback_params: dict[str, float] | None
    next_exploration: dict[str, float] | None
    updated_state: OptimizerState
    diagnostics: dict


# ── Statistical imports from correlation_engine ─────────────────────────────

def _correlate(xs: list, ys: list) -> tuple[float | None, float | None]:
    """Import correlation function from correlation_engine.
    Falls back to inline Spearman if import fails."""
    try:
        from intel.correlation_engine import _correlate as _ce_correlate
        return _ce_correlate(xs, ys)
    except Exception:
        return _inline_spearman(xs, ys)


def _inline_spearman(xs: list, ys: list) -> tuple[float | None, float | None]:
    """Minimal Spearman implementation as fallback."""
    n = len(xs)
    if n < 3:
        return None, None

    def rank(vals):
        indexed = sorted(enumerate(vals), key=lambda x: x[1])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(vals):
            j = i
            while j < len(vals) - 1 and indexed[j + 1][1] == indexed[j][1]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    rx, ry = rank(xs), rank(ys)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    den_x = sum((a - mean_x) ** 2 for a in rx) ** 0.5
    den_y = sum((b - mean_y) ** 2 for b in ry) ** 0.5
    if den_x * den_y < 1e-9:
        return None, None
    r = num / (den_x * den_y)
    # Approximate p-value via t-distribution
    if abs(r) >= 1.0:
        return r, 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    z = abs(t) * (1 - 1 / (4 * max(1, n - 2))) / math.sqrt(1 + t * t / (2 * max(1, n - 2)))
    p = math.erfc(z / math.sqrt(2))  # two-tailed
    return round(r, 4), round(min(p, 1.0), 6)


# ── Core Optimizer ──────────────────────────────────────────────────────────

# Confidence level → learning rate multiplier
CONFIDENCE_MULTIPLIERS = {
    "none": 0.0,
    "low": 0.5,
    "sufficient": 1.0,
}

MOMENTUM_BETA = 0.7
MOMENTUM_CAP = 3.0
APPROVAL_THRESHOLD_STEPS = 3  # delta > 3×min_step → requires approval
MAX_PROPOSALS_PER_CYCLE = 3
ROLLBACK_THRESHOLD = 0.15     # 15% loss increase triggers rollback
ROLLBACK_COOLDOWN_VIDEOS = 3
EXPLORATION_RATE_MIN = 0.30
EXPLORATION_DECAY_EPOCHS = 50
MIN_OBSERVATIONS_PER_GROUP = 3
P_VALUE_THRESHOLD = 0.15


class ParamOptimizer:
    """Neural-network-inspired parameter optimizer.

    Pure computation — no I/O. Receives data, returns recommendations.
    """

    def compute_loss(
        self,
        metrics: PerformanceMetrics,
        weights: LossWeights | None = None,
        state: OptimizerState | None = None,
    ) -> float:
        """Compute weighted loss from YouTube metrics.

        Loss is negative (lower = better performance).
        All metrics normalized to 0-1 via historical min/max.
        """
        w = weights or LossWeights()

        # Normalize each metric
        def norm(val: float, key: str, fallback_min: float, fallback_max: float) -> float:
            if state:
                lo = state.normalization_min.get(key, fallback_min)
                hi = state.normalization_max.get(key, fallback_max)
            else:
                lo, hi = fallback_min, fallback_max
            rng = hi - lo
            if rng < 1e-9:
                return 0.5
            return max(0.0, min(1.0, (val - lo) / rng))

        n_ret = norm(metrics.retention_pct, "retention_pct", 20.0, 80.0)
        n_vel = norm(metrics.views_velocity_48h, "views_velocity_48h", 0.0, 10000.0)
        n_eng = norm(metrics.engagement_rate, "engagement_rate", 0.0, 0.10)
        n_sent = norm(metrics.comment_sentiment_score, "sentiment", -1.0, 1.0)
        n_hook = norm(metrics.hook_retention_30s, "hook_retention_30s", 30.0, 90.0)

        # Negative loss (lower = better)
        return -(
            w.retention * n_ret
            + w.views_velocity * n_vel
            + w.engagement * n_eng
            + w.sentiment * n_sent
            + w.hook_retention * n_hook
        )

    def estimate_gradient(
        self,
        observations: list[ObservationRecord],
        param_key: str,
    ) -> GradientEstimate:
        """Estimate gradient for a single parameter via finite-difference.

        Splits observations by above/below median param value.
        Returns confidence=0 if insufficient data or not significant.
        """
        # Extract param values and losses
        pairs: list[tuple[float, float]] = []
        for obs in observations:
            val = obs.params.get(param_key)
            if val is None:
                continue
            if not math.isfinite(val):
                continue
            loss = self.compute_loss(obs.metrics)
            if not math.isfinite(loss):
                continue
            pairs.append((val, loss))

        if len(pairs) < MIN_OBSERVATIONS_PER_GROUP * 2:
            return GradientEstimate(param_key, 0.0, 0.0, len(pairs), None)

        # Check if param has enough variation
        param_vals = [p for p, _ in pairs]
        param_mean = sum(param_vals) / len(param_vals)
        param_var = sum((v - param_mean) ** 2 for v in param_vals) / len(param_vals)
        if param_var < 1e-12:
            return GradientEstimate(param_key, 0.0, 0.0, len(pairs), None)

        # Split by median
        median_val = sorted(param_vals)[len(param_vals) // 2]
        below = [(p, loss) for p, loss in pairs if p < median_val]
        above = [(p, loss) for p, loss in pairs if p >= median_val]

        # Ensure roughly balanced split (handle ties at median)
        if len(below) < MIN_OBSERVATIONS_PER_GROUP or len(above) < MIN_OBSERVATIONS_PER_GROUP:
            return GradientEstimate(param_key, 0.0, 0.0, len(pairs), None)

        # Compute mean loss and param for each group
        mean_loss_below = sum(loss for _, loss in below) / len(below)
        mean_loss_above = sum(loss for _, loss in above) / len(above)
        mean_param_below = sum(p for p, _ in below) / len(below)
        mean_param_above = sum(p for p, _ in above) / len(above)

        param_diff = mean_param_above - mean_param_below
        if abs(param_diff) < 1e-12:
            return GradientEstimate(param_key, 0.0, 0.0, len(pairs), None)

        gradient = (mean_loss_above - mean_loss_below) / param_diff

        # Compute correlation for confidence
        xs = [p for p, _ in pairs]
        ys = [loss for _, loss in pairs]
        r, p_val = _correlate(xs, ys)

        if r is None or p_val is None or p_val > P_VALUE_THRESHOLD:
            return GradientEstimate(param_key, gradient, 0.0, len(pairs), p_val)

        # Confidence based on sample size + p-value
        n = len(pairs)
        size_conf = min(1.0, max(0.3, (n - MIN_OBSERVATIONS_PER_GROUP * 2) / 8))
        p_conf = 1.0 - (p_val / P_VALUE_THRESHOLD) if p_val < P_VALUE_THRESHOLD else 0.0
        confidence = size_conf * p_conf

        # Confound check: see if other params varied with this one
        confidence = self._check_confounds(observations, param_key, confidence)

        return GradientEstimate(param_key, gradient, confidence, n, p_val)

    def _check_confounds(
        self,
        observations: list[ObservationRecord],
        param_key: str,
        base_confidence: float,
    ) -> float:
        """Reduce confidence if other params are correlated with this one."""
        target_vals = [obs.params.get(param_key, 0.0) for obs in observations]
        if len(target_vals) < 6:
            return base_confidence  # Not enough data for confound check

        for obs in observations:
            for other_key in obs.params:
                if other_key == param_key:
                    continue
                other_vals = [o.params.get(other_key, 0.0) for o in observations]
                if len(other_vals) != len(target_vals):
                    continue
                # Check if other param varies
                other_var = sum((v - sum(other_vals) / len(other_vals)) ** 2 for v in other_vals)
                if other_var < 1e-12:
                    continue
                r, _ = _correlate(target_vals, other_vals)
                if r is not None and abs(r) > 0.5:
                    base_confidence *= 0.5
                    break  # One confound is enough to penalize
            break  # Only check first observation's keys (all have same keys)

        return base_confidence

    def compute_update(
        self,
        gradient: GradientEstimate,
        state: OptimizerState,
        param_key: str,
        current_value: float,
        confidence_level: str,
        param_bounds: tuple[float, float],
        param_min_step: float,
    ) -> UpdateProposal | None:
        """Compute parameter update from gradient estimate.

        Returns None if no update warranted (zero confidence, in cooldown, etc).
        """
        if gradient.confidence <= 0:
            return None

        conf_mult = CONFIDENCE_MULTIPLIERS.get(confidence_level, 0.0)
        if conf_mult <= 0:
            return None

        # In cooldown → no updates
        if state.cooldown_remaining > 0:
            return None

        # Momentum update: EMA of gradient
        old_momentum = state.momentum.get(param_key, 0.0)
        new_momentum = MOMENTUM_BETA * old_momentum + (1 - MOMENTUM_BETA) * gradient.estimated_gradient
        state.momentum[param_key] = new_momentum

        # Direction from momentum (smoothed, not raw gradient)
        if abs(new_momentum) < 1e-12:
            return None
        direction = -1.0 if new_momentum > 0 else 1.0  # Negative gradient = increase param

        # Step size
        step = param_min_step * conf_mult
        magnitude = min(abs(new_momentum), MOMENTUM_CAP)
        raw_delta = direction * step * magnitude

        # Clamp to bounds
        lo, hi = param_bounds
        proposed = max(lo, min(hi, current_value + raw_delta))
        actual_delta = proposed - current_value

        if abs(actual_delta) < 1e-9:
            return None

        # Approval gate
        requires_approval = abs(actual_delta) > APPROVAL_THRESHOLD_STEPS * param_min_step

        reason = (
            f"gradient={gradient.estimated_gradient:.4f}, "
            f"momentum={new_momentum:.4f}, "
            f"confidence={gradient.confidence:.2f}, "
            f"p={gradient.p_value}"
        )

        return UpdateProposal(
            param_key=param_key,
            current_value=round(current_value, 6),
            proposed_value=round(proposed, 6),
            delta=round(actual_delta, 6),
            gradient=round(gradient.estimated_gradient, 6),
            momentum=round(new_momentum, 6),
            confidence=round(gradient.confidence, 4),
            requires_approval=requires_approval,
            reason=reason,
        )

    def check_rollback(self, running_loss: list[float], window: int = 3) -> bool:
        """Check if recent loss indicates quality degradation.

        Compares mean of last `window` losses vs the `window` before that.
        Returns True if >15% degradation detected.
        """
        if len(running_loss) < window * 2:
            return False

        recent = running_loss[-window:]
        prior = running_loss[-(window * 2):-window]

        mean_recent = sum(recent) / len(recent)
        mean_prior = sum(prior) / len(prior)

        # Loss is negative, so "worse" means more negative → lower value
        # Actually: loss is negative (lower = better). Degradation = loss went UP (less negative)
        # mean_recent > mean_prior means degradation
        if mean_prior == 0:
            return False

        # Use absolute comparison: if recent loss is worse (higher/less negative) by >15%
        degradation = (mean_recent - mean_prior) / abs(mean_prior)
        return degradation > ROLLBACK_THRESHOLD

    def generate_exploration(
        self,
        state: OptimizerState,
        learnable_params: list[str],
        current_params: dict[str, float],
        param_specs: dict,  # key -> ParamSpec
    ) -> dict[str, float] | None:
        """Generate a single-param perturbation for exploration.

        Round-robin through params. Alternates +/- direction.
        Returns {param_key: perturbed_value} or None.
        """
        if not learnable_params:
            return None

        # Exploration rate decay
        rate = max(EXPLORATION_RATE_MIN, 1.0 - state.total_epochs / EXPLORATION_DECAY_EPOCHS)

        # Deterministic "random": explore if epoch mod check passes
        # This is reproducible — same epoch always gives same decision
        if state.total_epochs > 0:
            explore_interval = max(1, int(1.0 / rate))
            if state.total_epochs % explore_interval != 0:
                return None

        # Build/refresh exploration queue
        if not state.exploration_queue:
            state.exploration_queue = list(learnable_params)

        # Pick next param (skip if same as last)
        param_key = None
        for _ in range(len(state.exploration_queue)):
            candidate = state.exploration_queue[0]
            state.exploration_queue = state.exploration_queue[1:]  # rotate
            if candidate != state.last_explored_param:
                param_key = candidate
                break
            state.exploration_queue.append(candidate)

        if param_key is None and state.exploration_queue:
            param_key = state.exploration_queue[0]
            state.exploration_queue = state.exploration_queue[1:]

        if param_key is None:
            return None

        spec = param_specs.get(param_key)
        if spec is None:
            return None

        # Alternate direction
        prev_dir = state.exploration_direction.get(param_key, -1)
        new_dir = -prev_dir  # Flip
        state.exploration_direction[param_key] = new_dir

        current = current_params.get(param_key, spec.default)
        perturbation = new_dir * spec.min_step
        proposed = max(spec.bounds[0], min(spec.bounds[1], current + perturbation))

        state.last_explored_param = param_key

        return {param_key: round(proposed, 6)}

    def _update_normalization(
        self,
        state: OptimizerState,
        observations: list[ObservationRecord],
    ) -> None:
        """Update min/max normalization bounds from observation metrics."""
        for obs in observations:
            m = obs.metrics
            for key, val in [
                ("retention_pct", m.retention_pct),
                ("views_velocity_48h", m.views_velocity_48h),
                ("engagement_rate", m.engagement_rate),
                ("sentiment", m.comment_sentiment_score),
                ("hook_retention_30s", m.hook_retention_30s),
            ]:
                if not math.isfinite(val):
                    continue
                if key not in state.normalization_min or val < state.normalization_min[key]:
                    state.normalization_min[key] = val
                if key not in state.normalization_max or val > state.normalization_max[key]:
                    state.normalization_max[key] = val

    def run_optimization_cycle(
        self,
        observations: list[ObservationRecord],
        current_params: dict[str, float],
        state: OptimizerState,
        confidence_level: str,
        learnable_params: list[str] | None = None,
        param_specs: dict | None = None,
    ) -> OptimizationResult:
        """Run a complete optimization cycle.

        Args:
            observations: Recent videos with matured metrics (48h+).
            current_params: Current active parameter values.
            state: Persisted optimizer state (momentum, exploration, etc).
            confidence_level: "none", "low", or "sufficient".
            learnable_params: Keys of params the optimizer can tune.
            param_specs: Dict of key -> ParamSpec for bounds/steps.

        Returns:
            OptimizationResult with proposals, rollback decision, and updated state.
        """
        # Validate inputs
        if confidence_level not in CONFIDENCE_MULTIPLIERS:
            raise ValueError(f"Invalid confidence_level: {confidence_level}")

        # Filter observations: only those with render_compliance >= 0.5
        # (low compliance = params weren't honored, unreliable for gradient)
        reliable_obs = [
            o for o in observations
            if (o.render_compliance or 0.0) >= 0.5
        ]

        state.epoch += 1
        state.total_epochs += 1

        # Update normalization bounds
        self._update_normalization(state, reliable_obs)

        # Compute losses for reliable observations
        losses = []
        for obs in reliable_obs:
            loss = self.compute_loss(obs.metrics, state=state)
            if math.isfinite(loss):
                losses.append(loss)

        # Update running loss
        if losses:
            avg_loss = sum(losses) / len(losses)
            state.running_loss.append(round(avg_loss, 6))
            # Keep last 20
            if len(state.running_loss) > 20:
                state.running_loss = state.running_loss[-20:]

        # Check rollback
        rollback_triggered = self.check_rollback(state.running_loss)
        rollback_params: dict[str, float] | None = None

        if rollback_triggered:
            # Revert to the params from the best recent observation
            best_obs = min(reliable_obs, key=lambda o: self.compute_loss(o.metrics, state=state))
            rollback_params = dict(best_obs.params)
            # Reset momentum
            state.momentum = {}
            state.cooldown_remaining = ROLLBACK_COOLDOWN_VIDEOS

        # Decrement cooldown
        if state.cooldown_remaining > 0:
            state.cooldown_remaining -= 1

        # Estimate gradients and compute updates (if not in rollback)
        proposals: list[UpdateProposal] = []
        gradient_diagnostics: dict[str, dict] = {}

        if not rollback_triggered and confidence_level != "none" and param_specs:
            target_params = learnable_params or list(param_specs.keys())
            for param_key in target_params:
                spec = param_specs.get(param_key)
                if spec is None or not spec.learnable:
                    continue

                gradient = self.estimate_gradient(reliable_obs, param_key)
                gradient_diagnostics[param_key] = {
                    "gradient": gradient.estimated_gradient,
                    "confidence": gradient.confidence,
                    "p_value": gradient.p_value,
                    "sample_size": gradient.sample_size,
                }

                if gradient.confidence <= 0:
                    continue

                current = current_params.get(param_key, spec.default)
                proposal = self.compute_update(
                    gradient, state, param_key, current,
                    confidence_level, spec.bounds, spec.min_step,
                )
                if proposal is not None:
                    proposals.append(proposal)

            # Limit to top N by confidence
            proposals.sort(key=lambda p: p.confidence, reverse=True)
            proposals = proposals[:MAX_PROPOSALS_PER_CYCLE]

        # Generate exploration for next video (skip during rollback cooldown)
        exploration = None
        if param_specs and state.cooldown_remaining <= 0:
            target_params = learnable_params or list(param_specs.keys())
            exploration = self.generate_exploration(
                state, target_params, current_params, param_specs
            )
        state.next_exploration = exploration

        diagnostics = {
            "epoch": state.epoch,
            "total_epochs": state.total_epochs,
            "observations_total": len(observations),
            "observations_reliable": len(reliable_obs),
            "confidence_level": confidence_level,
            "avg_loss": round(sum(losses) / len(losses), 6) if losses else None,
            "loss_trend": state.running_loss[-6:],
            "rollback_triggered": rollback_triggered,
            "cooldown_remaining": state.cooldown_remaining,
            "proposals_count": len(proposals),
            "exploration_param": list(exploration.keys())[0] if exploration else None,
            "exploration_rate": max(EXPLORATION_RATE_MIN, 1.0 - state.total_epochs / EXPLORATION_DECAY_EPOCHS),
            "gradient_signals": {
                k: v for k, v in gradient_diagnostics.items()
                if v["confidence"] > 0
            },
        }

        return OptimizationResult(
            proposals=proposals,
            rollback_triggered=rollback_triggered,
            rollback_params=rollback_params,
            next_exploration=exploration,
            updated_state=state,
            diagnostics=diagnostics,
        )
