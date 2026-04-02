"""Phase Script — stages 1-5 (Research through Verification)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.log import get_logger
from pipeline.state import save_state

logger = get_logger(__name__)
from pipeline.validators import (
    check_research, check_angle, check_blueprint,
    check_script, check_pacing, check_verification,
)
from pipeline.helpers import score_hook, clean_script
from pipeline.series import detect_series_potential, get_retention_optimal_length, queue_series_part2

if TYPE_CHECKING:
    from pipeline.context import PipelineContext
    from pipeline.runner import StageRunner


def _check_and_warn(issues, stage_name):
    """Print quality warnings (pure output, no state)."""
    if issues:
        logger.warning(f"\n\u26a0\ufe0f  {stage_name} quality issues:")
        for issue in issues:
            logger.warning(f"   - {issue}")


def _enrich_research_with_parent(ctx) -> None:
    """Inject Part 1 context into current research so later agents know what was covered."""
    parent = ctx.parent_context or {}
    series_meta = ctx.series_meta or {}
    part_num = series_meta.get("series_part", 2)
    part_focus = series_meta.get("part_focus", "")

    parent_research = parent.get("research") or {}
    parent_script = parent.get("script") or {}
    parent_angle = parent.get("angle") or {}

    ctx.research["_series_context"] = {
        "series_part": part_num,
        "part_focus": part_focus,
        "parent_topic": series_meta.get("parent_topic", ""),
        "parent_angle": parent_angle.get("chosen_angle", ""),
        "parent_twist": parent_angle.get("twist_potential", ""),
        "parent_script_summary": parent_script.get("full_script", "")[:1500],
        "parent_core_facts_covered": parent_research.get("core_facts", []),
        "parent_cliffhanger": (parent.get("series_plan") or {}).get(
            f"part_{part_num - 1}_cliffhanger", ""),
    }
    logger.info(f"[Series] Enriched research with Part {part_num - 1} context "
                f"({len(ctx.research['_series_context']['parent_core_facts_covered'])} facts from parent)")


def run_script_phase(ctx: PipelineContext, runner: StageRunner) -> None:
    """Execute stages 1-5: Research → Originality → Narrative → Script → Verification."""
    a01 = ctx.agents["a01"]
    a02 = ctx.agents["a02"]
    a03 = ctx.agents["a03"]
    a04 = ctx.agents["a04"]
    a04b = ctx.agents.get("a04b")
    a05 = ctx.agents["a05"]

    is_continuation = bool(ctx.series_meta and ctx.series_meta.get("series_part", 1) > 1)

    # ── Stage 1: Research ────────────────────────────────────────────────────
    ctx.research = runner.run_stage(1, "Research", a01.run, ctx.topic)
    # Enrich research with parent context for series continuations
    if is_continuation and ctx.parent_context and ctx.research:
        _enrich_research_with_parent(ctx)
    _check_and_warn(check_research(ctx.research or {}), "Research")

    # ── Stage 2: Originality ─────────────────────────────────────────────────
    ctx.angle = runner.run_stage(2, "Originality", a02.run, ctx.research, ctx.is_experiment)
    _check_and_warn(check_angle(ctx.angle or {}), "Originality")

    # ── Stage 3: Narrative ───────────────────────────────────────────────────
    ctx.blueprint = runner.run_stage(3, "Narrative", a03.run, ctx.research, ctx.angle)
    _check_and_warn(check_blueprint(ctx.blueprint or {}), "Narrative")

    # ── Blueprint alignment check ────────────────────────────────────────────
    if ctx.blueprint:
        _check_blueprint_alignment(ctx.blueprint)

    # ── Retention-driven length enforcement ──────────────────────────────────
    if ctx.blueprint and not runner.done(4):
        optimal_len = get_retention_optimal_length()
        if optimal_len:
            current_est = ctx.blueprint.get("estimated_length_minutes", 10)
            if abs(current_est - optimal_len) > 2:
                ctx.blueprint["estimated_length_minutes"] = min(optimal_len, 15)
                logger.info(f"[Retention] Adjusted blueprint length: {current_est:.0f} \u2192 {ctx.blueprint['estimated_length_minutes']:.0f} min")

    # ── Multi-part series detection (skip for continuations — already in a series)
    ctx.series_plan = None
    if not is_continuation and ctx.blueprint and ctx.research and not runner.done(4):
        ctx.series_plan = detect_series_potential(ctx.research, ctx.blueprint)
        if ctx.series_plan:
            _apply_series_plan(ctx)

    # ── Stage 4: Script ──────────────────────────────────────────────────────
    ctx.script = runner.run_stage(4, "Script", a04.run, ctx.research, ctx.angle, ctx.blueprint)
    if ctx.script:
        _post_process_script(ctx, runner, a04)

    # ── Script Doctor ────────────────────────────────────────────────────────
    if a04b and ctx.script and ctx.blueprint:
        _run_script_doctor(ctx, runner, a04, a04b)

    # ── Hook consistency check ───────────────────────────────────────────────
    if ctx.script and ctx.blueprint:
        _check_hook_consistency(ctx)

    # ── Stage 5: Verification ────────────────────────────────────────────────
    ctx.verification = runner.run_stage(5, "Verification", a05.run, ctx.script, ctx.research)
    _check_and_warn(check_verification(ctx.verification or {}), "Verification")

    # Apply script corrections from verification
    if ctx.verification and ctx.script:
        _apply_verification_corrections(ctx)

    # Hard gate: REQUIRES_REWRITE retry loop
    if ctx.verification and ctx.verification.get("overall_verdict") == "REQUIRES_REWRITE":
        _handle_requires_rewrite(ctx, runner, a04, a05)


def _check_blueprint_alignment(blueprint: dict) -> None:
    """Verify reveal placement matches emotional blueprint."""
    try:
        act3 = blueprint.get("act3", {})
        reveal_seq = act3.get("reveal_sequence", [])
        est_mins = blueprint.get("estimated_length_minutes", 10)

        act1_beats = len(blueprint.get("act1", {}).get("key_beats", []))
        act2_beats = len(blueprint.get("act2", {}).get("evidence_sequence", []))
        act3_beats = len(reveal_seq)
        total_beats = act1_beats + act2_beats + act3_beats
        if total_beats > 0:
            reveal_start_pct = (act1_beats + act2_beats) / total_beats
            if reveal_start_pct < 0.40 or reveal_start_pct > 0.60:
                logger.warning(
                    f"[Blueprint] Reveal at ~{reveal_start_pct:.0%} of beats, "
                    f"expected 40-60%. Acts: {act1_beats}/{act2_beats}/{act3_beats} beats, "
                    f"est {est_mins:.0f}min"
                )

        reflection = blueprint.get("reflection_beat", {})
        if reflection and reflection.get("duration_seconds", 0) < 8:
            logger.warning("[Blueprint] Reflection beat < 8 seconds \u2014 may not give revelation time to land")
    except Exception:
        pass


def _apply_series_plan(ctx: PipelineContext) -> None:
    """Modify blueprint for Part 1 of series and queue Part 2."""
    series_plan = ctx.series_plan
    blueprint = ctx.blueprint

    part1_focus = series_plan.get("part_1_focus", "")
    cliffhanger = series_plan.get("part_1_cliffhanger", "")
    if part1_focus:
        blueprint["series_part"] = 1
        blueprint["series_plan"] = series_plan
        if blueprint.get("ending"):
            blueprint["ending"]["reframe"] = cliffhanger
            blueprint["ending"]["final_line"] = (
                series_plan.get("part_1_cliffhanger", blueprint["ending"].get("final_line", ""))
            )
            blueprint["ending"]["cta"] = "Part 2 drops next. Subscribe so you don't miss it."
        blueprint["part_1_cliffhanger"] = cliffhanger
        blueprint["part_1_constraint"] = (
            f"IMPORTANT: This is Part 1 of a 2-part series. "
            f"Focus ONLY on: {part1_focus}. "
            f"End on this cliffhanger: {cliffhanger}. "
            f"Do NOT reveal the twist or resolution \u2014 save that for Part 2."
        )
        logger.info("[Series] Blueprint modified for Part 1")
        queue_series_part2(ctx.topic, series_plan, ctx.research,
                           state_path=str(ctx.state_path))

    ctx.state["series_plan"] = series_plan
    save_state(ctx.state, ctx.state_path)


def _post_process_script(ctx: PipelineContext, runner: StageRunner, a04) -> None:
    """Word count check, quality rewrite, hook scoring, clean_script."""
    script = ctx.script
    word_count = len(script.get("full_script", "").split())
    if word_count < 1000:
        logger.warning(f"[Script] Too short ({word_count} words, minimum 1000) — requesting expansion")
        needed = 1000 - word_count + 100  # Ask for extra buffer
        try:
            from core.agent_wrapper import call_agent
            expanded = call_agent(
                "04_script_writer",
                system_prompt=(
                    "You are a script expander. You receive a documentary script that is too short. "
                    "Expand it by adding more detail, archival specifics, and vivid narration. "
                    "Do NOT change the structure, hook, or ending. Keep the same voice and tone. "
                    "Return the COMPLETE expanded script as a JSON object with a 'full_script' key."
                ),
                user_prompt=(
                    f"This script is {word_count} words but needs at least 1,000 words. "
                    f"Add approximately {needed} more words by deepening existing sections.\n\n"
                    f"Current script:\n{script.get('full_script', '')}"
                ),
                max_tokens=8000,
                stage_num=4,
                topic=ctx.topic,
            )
            if isinstance(expanded, dict) and expanded.get("full_script"):
                new_count = len(expanded["full_script"].split())
                if new_count >= 1000:
                    logger.info(f"[Script] Expansion successful: {word_count} → {new_count} words")
                    ctx.script = expanded
                    script = expanded
                    word_count = new_count
                else:
                    logger.warning(f"[Script] Expansion still short: {new_count} words")
        except Exception as expand_err:
            logger.warning(f"[Script] Expansion failed: {expand_err}")

        # Final check after retry
        word_count = len(script.get("full_script", "").split())
        if word_count < 1000:
            raise Exception(
                f"Pipeline halted: script too short ({word_count} words, minimum 1000) "
                "even after expansion attempt."
            )

    # ── Script duration target check (1400-word minimum for 8-11 min video) ──
    if word_count < 1200:
        logger.error(f"[Script] Word count {word_count} is below 1200-word floor for 8-11 min target")
        try:
            from server.notify import _tg
            _tg(
                f"[Script] Word count critically low: {word_count} words\n"
                f"Topic: {ctx.topic}\n"
                f"Target: 1400+ words for 8-11 min video"
            )
        except Exception:
            pass
    elif word_count < 1400:
        logger.warning(f"[Script] Script below 1400-word target for 8-11 min video ({word_count} words)")

    issues = check_script(script)
    _check_and_warn(issues, "Script")
    _check_and_warn(check_pacing(script), "Pacing")

    # Score hook
    hook_scores = score_hook(script.get("full_script", ""))
    if hook_scores:
        ctx.state["hook_scores"] = hook_scores
        save_state(ctx.state, ctx.state_path)

    # Quality rewrite loop
    if len(issues) >= 3 and not runner.done(5):
        logger.info(f"[Pipeline] Script quality low ({len(issues)} issues) \u2014 attempting quality rewrite...")
        feedback = "Fix these quality issues:\n" + "\n".join(f"- {i}" for i in issues)
        for _qr in range(2):
            try:
                improved = a04.run(ctx.research, ctx.angle, ctx.blueprint, quality_feedback=feedback)
                if improved and improved.get("full_script"):
                    improved["full_script"] = clean_script(improved["full_script"])
                    new_issues = check_script(improved)
                    if len(new_issues) < len(issues):
                        ctx.script = improved
                        script = improved
                        runner.mark(4, script)
                        issues = new_issues
                        logger.info(f"[Pipeline] \u2713 Script quality improved ({len(new_issues)} issues remain)")
                        break
            except Exception as qr_err:
                logger.warning(f"[Pipeline] Quality rewrite {_qr+1} failed: {qr_err}")

    # Always clean meta text
    script["full_script"] = clean_script(script.get("full_script", ""))


def _run_script_doctor(ctx: PipelineContext, runner: StageRunner, a04, a04b) -> None:
    """Script Doctor gate: max 2 rewrite attempts, must reach avg >= 7.0."""
    _sd_max_attempts = 2
    for _sd_attempt in range(_sd_max_attempts + 1):
        try:
            doctor_result = a04b.run(ctx.script, ctx.blueprint)
            if doctor_result and doctor_result.get("approved", True):
                ctx.state["script_doctor_scores"] = doctor_result.get("scores", {})
                save_state(ctx.state, ctx.state_path)
                break
            # Soft enforcement: warn + Telegram alert when Script Doctor rejects
            _sd_feedback = doctor_result.get("feedback", "")
            _sd_scores = doctor_result.get("scores", {})
            _sd_avg = doctor_result.get("average_score", 0)
            logger.warning(f"[Pipeline] Script Doctor rejected script "
                           f"(avg {_sd_avg}/10, attempt {_sd_attempt + 1}/{_sd_max_attempts + 1})")
            try:
                from server.notify import _tg
                _tg(f"Script Doctor rejected (attempt {_sd_attempt + 1}/{_sd_max_attempts + 1})\n"
                    f"Avg score: {_sd_avg}/10\n"
                    f"Scores: {_sd_scores}\n"
                    f"Feedback: {(_sd_feedback or 'none')[:500]}")
            except Exception:
                pass

            if _sd_attempt < _sd_max_attempts:
                feedback = _sd_feedback
                if feedback:
                    logger.info(f"[Pipeline] Script Doctor: needs revision (attempt {_sd_attempt + 1}/{_sd_max_attempts}) \u2014 rewriting...")
                    improved = a04.run(ctx.research, ctx.angle, ctx.blueprint, quality_feedback=feedback)
                    if improved and improved.get("full_script"):
                        improved["full_script"] = clean_script(improved["full_script"])
                        ctx.script = improved
                        runner.mark(4, ctx.script)
                        logger.info(f"[Pipeline] Script Doctor: revision {_sd_attempt + 1} applied")
                    else:
                        break
                else:
                    break
            else:
                avg = doctor_result.get("average_score", 0)
                ctx.state["script_doctor_scores"] = doctor_result.get("scores", {})
                save_state(ctx.state, ctx.state_path)
                raise RuntimeError(
                    f"Script Doctor gate FAILED after {_sd_max_attempts} rewrites: "
                    f"avg score {avg}/10 (need \u22657.0). Scores: {doctor_result.get('scores', {})}"
                )
        except RuntimeError:
            raise
        except Exception as sd_err:
            logger.warning(f"[Pipeline] Script Doctor failed (non-fatal): {sd_err}")
            break


def _check_hook_consistency(ctx: PipelineContext) -> None:
    """Verify script opening references blueprint hook."""
    _hook = ctx.blueprint.get("hook")
    hook_scene = _hook.get("opening_scene", "") if isinstance(_hook, dict) else ""
    if hook_scene:
        opening = ctx.script.get("full_script", "")[:500].lower()
        hook_words = [w.lower() for w in hook_scene.split() if len(w) > 4][:5]
        matches = sum(1 for w in hook_words if w in opening)
        if matches < 2:
            logger.warning("[Pipeline] \u26a0\ufe0f  Hook consistency: script opening may not match blueprint hook")
            logger.warning(f"[Pipeline]    Blueprint hook: {hook_scene[:100]}")
            logger.warning(f"[Pipeline]    Script opening: {ctx.script.get('full_script', '')[:100]}")


def _apply_verification_corrections(ctx: PipelineContext) -> None:
    """Apply script corrections from verification back to full_script."""
    corrections = ctx.verification.get("script_corrections", [])
    if corrections:
        full_script = ctx.script.get("full_script", "")
        applied = 0
        for correction in corrections:
            orig = correction.get("original_text", "")
            fixed = correction.get("corrected_text", "")
            if orig and fixed and orig in full_script:
                full_script = full_script.replace(orig, fixed, 1)
                applied += 1
        ctx.script["full_script"] = full_script
        logger.info(f"[Pipeline] Applied {applied}/{len(corrections)} script corrections from verification")


def _handle_requires_rewrite(ctx: PipelineContext, runner: StageRunner, a04, a05) -> None:
    """Auto-retry up to 2 times when verification returns REQUIRES_REWRITE."""
    logger.warning("[Pipeline] REQUIRES_REWRITE \u2014 attempting auto-retry (max 2 attempts)...")
    retry_success = False
    for _retry in range(2):
        logger.info(f"[Pipeline] Retry {_retry+1}/2 \u2014 regenerating script...")
        try:
            ctx.script = a04.run(ctx.research, ctx.angle, ctx.blueprint)
            if ctx.script:
                ctx.script["full_script"] = clean_script(ctx.script.get("full_script", ""))
            ctx.verification = a05.run(ctx.script, ctx.research)
            if ctx.verification and ctx.verification.get("overall_verdict") != "REQUIRES_REWRITE":
                logger.info(f"[Pipeline] \u2713 Retry {_retry+1} passed verification")
                runner.mark(4, ctx.script)
                runner.mark(5, ctx.verification)
                retry_success = True
                break
        except Exception as re_err:
            logger.error(f"[Pipeline] Retry {_retry+1} error: {re_err}")
    if not retry_success:
        raise Exception(
            "FATAL: Fact verification requires full rewrite after 2 retry attempts. "
            "Twist reveal could not be verified by 2+ sources."
        )
