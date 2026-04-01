"""
Agent 04 - Script Writer
Writes the full narration script as plain text.
Model: Sonnet 4.6
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.agent_wrapper import call_agent
from intel.dna_loader import get_dna, get_agent_guidance

DNA = get_dna(["identity", "voice", "story_structure", "content_strategy", "channel_intelligence"])


def extract_acts(text: str) -> dict:
    """Split script into acts by word proportion rather than character position.
    Cold open is the first ~3% (1-2 disorienting sentences), hook is the next ~4%
    (stakes escalation), then acts follow standard documentary structure."""
    words = text.split()
    n = len(words)

    def section(start_pct, end_pct):
        return " ".join(words[int(n * start_pct):int(n * end_pct)])

    return {
        "cold_open": section(0.00, 0.03),
        "hook":      section(0.03, 0.07),
        "act1":      section(0.07, 0.28),
        "act2":      section(0.28, 0.67),
        "act3":      section(0.67, 0.90),
        "ending":    section(0.90, 1.00),
    }


def run(research, angle, blueprint, quality_feedback: str = ""):
    topic = research.get("topic", "Unknown")
    # Tiered length support
    tier = blueprint.get("length_tier", "STANDARD").upper()
    tier_caps = {"STANDARD": 10, "DEEP_DIVE": 18, "EPIC": 25}
    tier_word_caps = {"STANDARD": 1300, "DEEP_DIVE": 2340, "EPIC": 3250}
    max_mins = tier_caps.get(tier, 10)
    max_words = tier_word_caps.get(tier, 1300)
    try:
        estimated_mins = min(float(blueprint.get("estimated_length_minutes", 10)), max_mins)
    except (TypeError, ValueError):
        estimated_mins = max_mins
    target_words = min(int(estimated_mins * 130), max_words)

    print(f"[Script Writer] Writing script for: {topic}")
    print(f"[Script Writer] Target: ~{target_words} words ({estimated_mins} minutes)")

    system = f"""You are a documentary script writer for The Obsidian Archive YouTube channel.

{DNA}

Tone: cinematic, dramatic, like a Netflix documentary narrator — think Voices of the Past, Fall of Civilizations.

CRITICAL — FORMAT FOR DRAMATIC AI VOICEOVER:
- Use em dashes — like this — for mid-sentence dramatic pauses
- Use short punchy sentences. One idea. Then stop.
- Use ... for slow ominous trailing off...
- Vary sentence length wildly. Short hits hard. Then a longer sentence slowly builds the tension, pulling the listener deeper.
- Start major reveals on their own line with a line break before it
- Never use parentheses, brackets, or headers
- Write HOW it should sound. If something is sinister, write it sinister.
- Whisper-style lines: "No one knew." — just three words, devastating.
- Build to chapter endings with escalating sentence rhythm
STRUCTURE — Cold Open and Hook are two DISTINCT beats, not one:
- COLD OPEN (first 1-2 sentences): Pure sensation. Something feels wrong. A fact that
  disorients. DO NOT explain, name, or contextualize. The viewer should feel before they
  understand. Example: "A text vanishes for a thousand years. When it resurfaces, the
  author is already a ghost."
- HOOK (next 3-5 sentences): Now name the stakes. Who, what, why it matters. This is
  where curiosity becomes commitment. The mystery planted in the cold open gets its
  first shape — but NOT its answer.
- The cold open and hook MUST serve different functions. If both explain, the hook has
  nowhere to go. If both mystify, the viewer has no anchor.

Rules:
- Present tense throughout
- Match the hook register (TENSION, DREAD_THROUGH_BEAUTY, MYSTERY, or INTIMACY) — not always maximum action
- Named characters only, exact dates and numbers
- Short sentences at revelation moments
- Include moments of WARMTH or WONDER in Act 1 — humanize before darkening
- Allow ABSURDITY in Act 2 when history is stranger than fiction — "this actually happened" beats
- Build dread through Act 2
- Twist/reframe must feel inevitable not surprising
- Final line lands in silence
- NO filler, NO "in this video", NO "welcome back"

PERSONALITY — you are not a Wikipedia narrator. You are a human storyteller who is genuinely fascinated, disturbed, or amazed by what you're telling. Show it:
- Include at least one unexpected analogy or modern parallel ("It's like finding out your GPS has been lying to you — for three centuries")
- Include at least one moment of genuine narrator reaction ("And here's where this story stops being history and starts being horror")
- Allow yourself moments of dark humor when the history is absurd enough to warrant it
- Use "you" to address the viewer directly at least twice — make them a character in the story

POV SHIFTS — shift perspective at least once in the script. Show the same event from two different viewpoints. "To the emperor, this was a routine decree. To the 3,000 prisoners in the dungeon below, it was a death sentence."

REFLECTION BEAT — after the main revelation in Act 3, include a natural pause point. Write a short sentence (5-8 words) followed by a line break and then the ending. This creates a moment of silence where the weight of the revelation can land.
WORD COUNT TARGET: Target 1,200-1,600 words for long-form documentaries (produces 8-11 minute videos at ~140 WPM). Scripts under 1,000 words are too short for the documentary format.

Output ONLY the raw narration script. No JSON. No headers. No labels. Just the words."""

    if quality_feedback:
        system += f"\n\nQUALITY FEEDBACK FROM PREVIOUS DRAFT — fix these issues in this version:\n{quality_feedback}"

    cold_open = blueprint.get("cold_open", "")
    hook_register = blueprint.get("hook_register", "TENSION")

    prompt = f"""Topic: {topic}
Angle: {angle.get("chosen_angle")}
Central figure: {angle.get("central_figure")}
Target length: ~{target_words} words
Length tier: {tier}

{"COLD OPEN (write these 1-2 sentences FIRST, before the hook):" + chr(10) + cold_open + chr(10) if cold_open else ""}
HOOK REGISTER: {hook_register}
HOOK - open on this scene (using {hook_register} register):
{blueprint.get("hook", {}).get("opening_scene", "")}

ACT 1 - tell this story:
{blueprint.get("act1", {}).get("summary", "")}

ACT 2 - introduce these cracks:
{blueprint.get("act2", {}).get("summary", "")}

ACT 3 - the twist reveal:
{blueprint.get("act3", {}).get("summary", "")}

ENDING - close with:
{blueprint.get("ending", {}).get("final_line", "")}

POV SHIFT (include this perspective change):
{blueprint.get("pov_shift", {}).get("line", "Include at least one perspective shift")}

REFLECTION BEAT (after Act 3 reveal, include a pause moment):
{blueprint.get("reflection_beat", {}).get("placement", "After the main revelation")}

Key facts to weave in naturally:
{chr(10).join(f"- {f}" for f in research.get("core_facts", [])[:8])}

Archival detail to include verbatim:
{research.get("archival_gems", [""])[0] if research.get("archival_gems") else ""}

Write the complete script now. Every word counts."""

    # If this is Part 1 of a series, inject the constraint
    part1_constraint = blueprint.get("part_1_constraint", "")
    if part1_constraint:
        prompt += f"\n\n{part1_constraint}"

    # If this is Part 2+ of a series, inject continuation context
    series_ctx = research.get("_series_context")
    if series_ctx and series_ctx.get("series_part", 1) > 1:
        part_num = series_ctx["series_part"]
        parent_script_summary = series_ctx.get("parent_script_summary", "")
        cliffhanger = series_ctx.get("parent_cliffhanger", "")
        prompt += (
            f"\n\nSERIES CONTINUATION — Part {part_num}:\n"
            f"Part {part_num - 1} ended on: \"{cliffhanger}\"\n"
            f"This part focuses on: {series_ctx.get('part_focus', 'continuation')}\n"
        )
        if parent_script_summary:
            prompt += (
                f"\nHere is the end of Part {part_num - 1}'s script for tone/voice continuity:\n"
                f"---\n{parent_script_summary[-800:]}\n---\n"
                f"\nOpen by briefly recapping the cliffhanger (1-2 sentences, not a full summary), "
                f"then immediately continue the story. Match the voice and tone of Part {part_num - 1}."
            )

    guidance = get_agent_guidance("agent_04")
    if guidance:
        system += f"\n\nANALYTICS GUIDANCE:\n{guidance}"

    # Inject script intelligence (hook type ranking, pacing, engagement)
    try:
        from intel.channel_insights import get_script_intelligence
        script_intel = get_script_intelligence()
        if script_intel:
            system += f"\n\n{script_intel}"
    except Exception:
        pass

    # Inject content quality correlation intelligence
    try:
        from intel.channel_insights import get_content_quality_recommendation
        cq_rec = get_content_quality_recommendation("script_writer")
        if cq_rec:
            system += f"\n\nCONTENT QUALITY DATA: {cq_rec}"
    except Exception:
        pass

    # Inject exemplar hooks from top-performing videos
    try:
        from intel.channel_insights import get_exemplar_hooks
        exemplars = get_exemplar_hooks()
        if exemplars:
            system += f"\n\n{exemplars}"
    except Exception:
        pass

    # Soft injection: retention danger zone pacing (only if channel_insights.json has data)
    try:
        from intel.channel_insights import load_insights
        insights = load_insights()
        if insights:
            retention = insights.get("retention_analysis", {})
            drop_offs = retention.get("drop_off_points", [])
            if drop_offs:
                zones_pct = [f"{int(float(z) if float(z) <= 1 else float(z))}%" if float(z) > 1
                             else f"{int(float(z)*100)}%" for z in drop_offs]
            else:
                # Use default danger zones
                zones_pct = ["5%", "25%", "50%", "75%"]

            if insights.get("data_quality", {}).get("confidence_level", "none") != "none":
                system += (
                    f"\n\nRE-HOOKS (retention danger zone micro-hooks):\n"
                    f"Viewers drop off at: {', '.join(zones_pct)}.\n"
                    f"At EACH danger zone, insert a RE-HOOK — a 1-2 sentence pattern interrupt:\n"
                    f"  - Forward reference: 'But what happens next changes everything.'\n"
                    f"  - Curiosity gap: 'And here's what nobody talks about.'\n"
                    f"  - Twist tease: 'That wasn't the worst part.'\n"
                    f"  - Direct address: 'Stay with me — this is where it gets dark.'\n"
                    f"  - Reframe: 'Forget everything you just learned. It's worse.'\n"
                    f"NEVER place exposition or slow setup at a danger zone. "
                    f"Each re-hook must create a micro-cliffhanger that makes scrolling away feel like a loss."
                )
                print(f"[Script Writer] Re-hooks injected at danger zones: {', '.join(zones_pct)}")
    except Exception as e:
        print(f"[Script Writer] Retention data injection skipped: {e}")

    full_script = call_agent(
        "04_script_writer",
        system_prompt=system,
        user_prompt=prompt,
        max_tokens=16000,
        expect_json=False,
        stage_num=4,
        topic=topic,
    )

    word_count = len(full_script.split())
    print(f"[Script Writer] Written: {word_count} words")

    # Self-evaluation: rate the script and rewrite if below threshold
    if not quality_feedback:  # Only self-eval on first draft (not on rewrites)
        try:
            eval_result = call_agent(
                "04_script_writer",
                system_prompt=(
                    "You are a script quality evaluator for a dark history documentary channel. "
                    "Rate this script on 4 dimensions (1-10 each). Return ONLY JSON:\n"
                    '{"hook_strength": N, "emotional_pacing": N, "personality": N, "information_density": N, '
                    '"weakest_area": "brief note on what to fix", "overall": N}'
                ),
                user_prompt=f"Script ({word_count} words):\n\n{full_script[:12000]}",
                max_tokens=200,
                effort_offset=-1,  # Sonnet for evaluation
                stage_num=4,
                topic=topic,
            )
            avg_score = eval_result.get("overall", 7)
            print(f"[Script Writer] Self-eval: {avg_score}/10 "
                  f"(hook:{eval_result.get('hook_strength', '?')}, "
                  f"pacing:{eval_result.get('emotional_pacing', '?')}, "
                  f"personality:{eval_result.get('personality', '?')}, "
                  f"density:{eval_result.get('information_density', '?')})")
            if avg_score < 7:
                weakness = eval_result.get("weakest_area", "needs improvement")
                print(f"[Script Writer] Score below 7 — rewriting with feedback: {weakness}")
                return run(research, angle, blueprint,
                           quality_feedback=f"Previous draft scored {avg_score}/10. Fix: {weakness}")
        except Exception as e:
            print(f"[Script Writer] Self-eval failed (non-fatal): {e}")

    # Extract claims using sliding window to avoid splitting facts at period boundaries
    import re
    claim_keywords = ["died", "killed", "murdered", "poisoned", "wrote", "recorded", "stated",
                      "executed", "conquered", "destroyed", "founded", "discovered", "invented"]
    sentences = re.split(r'(?<=[.!?])\s+', full_script)
    claims = []
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if len(sent) > 15 and any(w in sent.lower() for w in claim_keywords):
            claims.append({"claim": sent[:150], "location": "script", "source_hint": "historical record"})

    acts = extract_acts(full_script)
    result = {
        "topic": topic,
        "angle": angle.get("chosen_angle", ""),
        "estimated_duration_minutes": estimated_mins,
        "length_tier": tier,
        "word_count": word_count,
        "full_script": full_script,
        "script": {
            "cold_open": acts.get("cold_open", ""),
            "hook":   acts["hook"],
            "act1":   acts["act1"],
            "act2":   acts["act2"],
            "act3":   acts["act3"],
            "ending": acts["ending"],
            "cta": "If this changed how you see history - subscribe. The archive goes deeper."
        },
        "claims_requiring_verification": claims[:8],
        "visual_cues": []
    }

    print(f"[Script Writer] Claims flagged: {len(claims[:8])}")
    return result

if __name__ == "__main__":
    print("Run via orchestrator.")
