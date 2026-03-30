"""
Agent 04b - Script Evaluator (upgraded from Script Doctor)
Evaluates a script on 7 scored dimensions + structural checks.
Sits between the script writer (04) and scene breakdown (07).
Either approves the script or provides specific rewrite feedback.
Model: Sonnet 4.6 (~$0.30/run)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.agent_wrapper import call_agent

# ── Scoring constants ────────────────────────────────────────────────────────
SCORED_DIMENSIONS = [
    "hook_strength",
    "emotional_pacing",
    "personality",
    "pov_shifts",
    "voice_consistency",
    "factual_grounding",
    "emotional_arc",
    "breathability",
    "revelation_craft",
]
APPROVAL_THRESHOLD = 7.0
DEFAULT_SCORE = 5

PREFIX = "[ScriptEvaluator]"


def _compute_scores(result: dict) -> dict:
    """Extract and clamp dimension scores from Claude's response."""
    scores = {}
    for dim in SCORED_DIMENSIONS:
        raw = result.get(dim, DEFAULT_SCORE)
        try:
            val = int(raw)
        except (TypeError, ValueError):
            val = DEFAULT_SCORE
        scores[dim] = max(1, min(10, val))
    return scores


def _check_rehooks(full_script: str, danger_zones: list[float] = None) -> list[str]:
    """Check for re-hook patterns near retention danger zone positions.

    Returns list of missing zone warnings. Empty list = all zones covered.
    """
    if not full_script or not danger_zones:
        return []

    rehook_patterns = [
        "but what", "here's what", "that wasn't", "stay with me",
        "this is where", "forget everything", "it gets", "worse than",
        "nobody talks about", "changes everything", "the worst part",
        "and then", "not the end", "just the beginning", "you won't believe",
        "here's the thing", "but here's", "wait — ", "hold on",
    ]

    words = full_script.split()
    n = len(words)
    missing = []

    for zone_pct in danger_zones:
        # Check ±5% around the danger zone position
        center = int(n * zone_pct)
        window_start = max(0, center - int(n * 0.05))
        window_end = min(n, center + int(n * 0.05))
        window_text = " ".join(words[window_start:window_end]).lower()

        has_rehook = any(p in window_text for p in rehook_patterns)
        if not has_rehook:
            missing.append(f"{int(zone_pct * 100)}%")

    return missing


def _check_exposition_placement(full_script: str) -> bool:
    """Check that heavy exposition isn't front-loaded in the first 10% of the script.

    Returns True if exposition placement is OK (not front-loaded).
    Heuristic: count explanatory markers in first 10% vs rest. If density in
    first 10% is more than 3x the density in the rest, flag it.
    """
    if not full_script or len(full_script) < 200:
        return True

    words = full_script.split()
    n = len(words)
    boundary = max(int(n * 0.10), 10)

    first_10 = " ".join(words[:boundary]).lower()
    rest = " ".join(words[boundary:]).lower()

    expo_markers = [
        "was known as", "was born in", "which meant", "this meant",
        "in other words", "to understand", "for context", "historically",
        "it should be noted", "it is important", "background",
    ]

    first_hits = sum(1 for m in expo_markers if m in first_10)
    rest_hits = sum(1 for m in expo_markers if m in rest)

    # Normalize by word count
    first_density = first_hits / max(boundary, 1)
    rest_density = rest_hits / max(n - boundary, 1)

    # If first 10% has 3x+ the exposition density, it's front-loaded
    if rest_density == 0:
        return first_hits <= 1  # OK if at most 1 marker in opening
    return first_density < rest_density * 3


def run(script_data: dict, blueprint: dict) -> dict:
    """Evaluate a script on 7 quality dimensions + structural checks.

    Args:
        script_data: Output from Agent 04 (script writer). Must contain 'full_script'
                     and 'script' dict with act breakdowns.
        blueprint:   Output from Agent 03 (blueprint). Used for context on intended
                     structure, hook register, and tone.

    Returns:
        dict with keys:
            approved (bool): True if average score >= 7
            scores (dict): Individual scores for each dimension (1-10)
            average_score (float): Mean of all 7 scores
            feedback (str): Specific improvement notes
            specific_fixes (list): Actionable fix items
            reflection_beat_present (bool): Whether a pause/silence beat exists
            exposition_placement_ok (bool): Whether exposition isn't front-loaded
            script_data (dict): The original script_data passed through
    """
    topic = script_data.get("topic", "Unknown")
    full_script = script_data.get("full_script", "")
    script_acts = script_data.get("script", {})

    print(f"{PREFIX} Evaluating script for: {topic}")

    system = """You are a senior script evaluator for The Obsidian Archive, a cinematic history YouTube channel.

Your job is to evaluate narration scripts on 7 dimensions, each scored 1-10:

1. hook_strength: Does the cold open + hook immediately grab attention? Does it create an irresistible question or image? (1 = generic opener, 10 = impossible to click away)

2. emotional_pacing: Does tension rise and fall naturally across acts? Are there breathing moments — brief pauses where the audience can absorb a revelation before the next wave hits? Does it avoid monotone intensity? (1 = flat or relentless, 10 = masterful ebb and flow)

3. personality: Does this feel like a HUMAN wrote it? Are there quirky observations, unexpected analogies, darkly funny asides, or moments of genuine awe? (1 = AI-generic, 10 = unmistakably authored)

4. pov_shifts: Does the narration shift perspectives at least once? Examples: "To the emperor, this was a minor inconvenience..." vs "To the prisoners, it was the end of everything." POV shifts create dimensionality. (1 = single flat perspective, 10 = rich multi-perspective storytelling)

5. voice_consistency: Does it match The Obsidian Archive voice — gravitas, intimacy, dread, precision? Short punchy sentences mixed with longer building ones? Em dashes for dramatic pauses? Does it avoid cliches, filler, and YouTube-speak? (1 = wrong channel entirely, 10 = pure Obsidian Archive DNA)

6. factual_grounding: Do claims feel specific and credible? Are there exact dates, named figures, and concrete details rather than vague generalities? Does the script cite primary sources or archival material where relevant? (1 = vague hand-waving, 10 = every claim feels anchored)

7. emotional_arc: Does the story have a complete, satisfying arc? Setup → tension → climax → resolution? Does the ending earn its weight? Does the audience feel changed by the end? (1 = no arc, events just happen, 10 = inevitable, devastating arc)

8. breathability: How well the script breathes. 10 = natural pauses every 2-3 sentences via em-dashes, ellipses, short punchy sentences (≤8 words), rhetorical questions. Pauses distributed evenly — not all in the intro. 1 = dense wall-of-text exposition with no breaks. Also measures sentence-length variance — monotonous sentence lengths score ≤4.

9. revelation_craft: How well revelations are deployed. 10 = clear setup→delay→payoff pattern, at least one moment of deliberate omission (trailing thought, loaded pause, meaning conveyed through what ISN'T said). 1 = revelations stated flatly with no buildup or impact.

STRUCTURAL CHECKS (report as booleans):
- reflection_beat_present: Is there a moment of quiet/pause/contemplation after the Act 3 climax but before the ending? This beat lets the revelation settle.
- exposition_front_loaded: Is there heavy explanatory context dumped in the first 10% before the hook has landed? The opening should pull you in, not lecture.
- open_loop: Does the script maintain at least one unresolved question or mystery for ≥30% of its length? Answer true/false.

Also provide:
- specific_fixes: A JSON array of 1-5 concrete, actionable fixes. Each fix should reference a specific section or line and explain exactly what to change. Format: [{"section": "act1|act2|act3|hook|ending|cold_open", "issue": "what's wrong", "fix": "exactly how to fix it"}]

Return your evaluation as JSON with this exact structure:
{
    "hook_strength": <int 1-10>,
    "emotional_pacing": <int 1-10>,
    "personality": <int 1-10>,
    "pov_shifts": <int 1-10>,
    "voice_consistency": <int 1-10>,
    "factual_grounding": <int 1-10>,
    "emotional_arc": <int 1-10>,
    "breathability": <int 1-10>,
    "revelation_craft": <int 1-10>,
    "reflection_beat_present": <bool>,
    "exposition_front_loaded": <bool>,
    "open_loop": <bool>,
    "specific_fixes": [{"section": "...", "issue": "...", "fix": "..."}],
    "feedback": "<overall assessment — strongest moment AND weakest moment, plus how to fix the weak spot>"
}

Be rigorous but fair. A score of 7 means "good, publishable." A score of 9-10 means "exceptional."
If the reflection beat is missing, one of your specific_fixes MUST address it.
If exposition is front-loaded, one of your specific_fixes MUST address it."""

    hook_register = blueprint.get("hook_register", "TENSION")
    cold_open = blueprint.get("cold_open", "")

    # Series cliffhanger protection — inject constraint
    cliffhanger = blueprint.get("part_1_cliffhanger", "")
    series_constraint = ""
    if cliffhanger:
        series_constraint = (
            f"\n\nSERIES CLIFFHANGER PROTECTION: This is Part 1 of a series. "
            f"The final 30 words of this script are LOCKED — they must end on this cliffhanger: "
            f"\"{cliffhanger}\". Do NOT suggest fixes that resolve, soften, or complete the ending. "
            f"Your quality pass ends at the reflection beat. The cliffhanger is untouchable."
        )
        system += series_constraint

    prompt = f"""Evaluate this script for The Obsidian Archive.

TOPIC: {topic}
ANGLE: {script_data.get("angle", "N/A")}
INTENDED HOOK REGISTER: {hook_register}
WORD COUNT: {script_data.get("word_count", "unknown")}
LENGTH TIER: {script_data.get("length_tier", "STANDARD")}

--- INTENDED COLD OPEN ---
{cold_open if cold_open else "(none specified)"}

--- FULL SCRIPT ---
{full_script}

--- ACT BREAKDOWN ---
Cold Open: {script_acts.get("cold_open", "(not extracted)")}

Hook: {script_acts.get("hook", "(not extracted)")}

Act 1: {script_acts.get("act1", "(not extracted)")[:500]}...

Act 2: {script_acts.get("act2", "(not extracted)")[:500]}...

Act 3: {script_acts.get("act3", "(not extracted)")[:500]}...

Ending: {script_acts.get("ending", "(not extracted)")}

Score each dimension 1-10, check structural elements, and provide specific fixes."""

    result = call_agent(
        "04b_script_doctor",
        system_prompt=system,
        user_prompt=prompt,
        max_tokens=3000,
        stage_num=4,
        topic=topic,
    )

    # ── Extract scores ────────────────────────────────────────────────────────
    scores = _compute_scores(result)
    avg_score = round(sum(scores.values()) / len(scores), 1)
    approved = avg_score >= APPROVAL_THRESHOLD

    # ── Structural checks ─────────────────────────────────────────────────────
    reflection_beat_present = bool(result.get("reflection_beat_present", False))
    exposition_front_loaded = bool(result.get("exposition_front_loaded", False))
    open_loop = bool(result.get("open_loop", False))
    if not open_loop:
        print(f"{PREFIX} WARNING: Script lacks sustained open loop (unresolved question for ≥30% of length)")
    # Also run our own heuristic check for exposition placement
    exposition_placement_ok = _check_exposition_placement(full_script) and not exposition_front_loaded

    # ── Specific fixes ────────────────────────────────────────────────────────
    specific_fixes = result.get("specific_fixes", [])
    if not isinstance(specific_fixes, list):
        specific_fixes = []
    # Validate fix structure
    validated_fixes = []
    for fix in specific_fixes:
        if isinstance(fix, dict) and fix.get("issue"):
            validated_fixes.append({
                "section": fix.get("section", "unknown"),
                "issue": fix.get("issue", ""),
                "fix": fix.get("fix", ""),
            })
    specific_fixes = validated_fixes[:5]

    # ── Feedback assembly ─────────────────────────────────────────────────────
    feedback = result.get("feedback", "No feedback provided.")

    # Append structural notes if issues detected
    structural_notes = []
    if not reflection_beat_present:
        structural_notes.append(
            "REFLECTION BEAT MISSING: Add a moment of quiet contemplation "
            "between the Act 3 climax and the ending — let the weight settle "
            "before the final line."
        )
    if not exposition_placement_ok:
        structural_notes.append(
            "EXPOSITION FRONT-LOADED: Move background context later — the first "
            "10% must hook the audience, not explain the setup. Lead with action, "
            "mystery, or a striking image."
        )

    # Re-hook check at retention danger zones
    try:
        from intel.channel_insights import load_insights
        _insights = load_insights()
        if _insights:
            drop_offs = _insights.get("retention_analysis", {}).get("drop_off_points", [])
            if drop_offs:
                danger_zones = []
                for z in drop_offs:
                    fz = float(z)
                    danger_zones.append(fz if fz <= 1 else fz / 100)
            else:
                danger_zones = [0.05, 0.25, 0.50, 0.75]
            missing = _check_rehooks(full_script, danger_zones)
            if missing:
                structural_notes.append(
                    f"RE-HOOKS MISSING at {', '.join(missing)} mark. "
                    "Add pattern-interrupt micro-hooks at these retention danger zones: "
                    "curiosity gaps, twist teases, or forward references."
                )
                print(f"{PREFIX} Re-hooks missing at: {', '.join(missing)}")
    except Exception as _rehook_err:
        print(f"{PREFIX} WARNING: Re-hook check failed: {_rehook_err}")

    if structural_notes:
        feedback += " " + " ".join(structural_notes)

    status = "APPROVED" if approved else "NEEDS_REVISION"
    print(f"{PREFIX} Score: {avg_score}/10 — {status}")
    print(f"{PREFIX} Breakdown: {scores}")
    print(f"{PREFIX} Reflection beat: {'present' if reflection_beat_present else 'MISSING'}")
    print(f"{PREFIX} Exposition placement: {'OK' if exposition_placement_ok else 'FRONT-LOADED'}")
    print(f"{PREFIX} Open loop: {'yes' if open_loop else 'NO'}")
    if specific_fixes:
        print(f"{PREFIX} Specific fixes: {len(specific_fixes)}")

    return {
        "approved": approved,
        "scores": scores,
        "average_score": avg_score,
        "feedback": feedback,
        "specific_fixes": specific_fixes,
        "reflection_beat_present": reflection_beat_present,
        "exposition_placement_ok": exposition_placement_ok,
        "open_loop": open_loop,
        "script_data": script_data,
    }


if __name__ == "__main__":
    print("Run via orchestrator.")
