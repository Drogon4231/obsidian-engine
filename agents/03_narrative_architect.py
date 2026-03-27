"""
Agent 03 — Narrative Architect
Designs the full story structure — no actual writing, just the blueprint.
Supports multiple narrative structures for variety.
Model: Sonnet 4.6 (story planning requires depth)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent_wrapper import call_agent
from intel.dna_loader import get_dna, get_agent_guidance
from intel.channel_insights import get_retention_intelligence
import json

DNA = get_dna(["story_structure", "voice", "content_strategy", "channel_intelligence"])

SYSTEM_PROMPT = f"""You are the Narrative Architect for The Obsidian Archive YouTube channel.

{DNA}

Your job: Given research and a chosen unique angle, design the complete story blueprint.
You do NOT write the script — you design the architecture the Script Writer will follow.

You MUST vary your narrative structure. Choose ONE of these structures based on what fits the topic best:
- CLASSIC: Hook → Accepted narrative → Cracks appear → Twist reveal → Reflection
- MYSTERY: Open with the twist/death/event → Work backwards to explain how we got here → Reveal the why
- DUAL_TIMELINE: Alternate between two time periods that converge at the climax
- COUNTDOWN: Start at the end, count backwards through key decisions that led to disaster
- TRIAL: Present the case for and against, with evidence, ending with the verdict
- REFRAME: No hidden truth is revealed — instead, the KNOWN truth is recontextualised. The ending makes the viewer see familiar history differently. "You already knew this. But you never thought about what it means." Use for topics where the facts are well-established but their implications are not.

Choose the structure that creates maximum dramatic tension for THIS specific topic. Do NOT always use CLASSIC.

COLD OPEN: Every video begins with a 1-2 sentence cold open BEFORE the hook. This is a flash-forward to the emotional climax or a quiet, devastating line that gains meaning later. It sets the tone for the entire video.

HOOK VARIETY: Do NOT always open with maximum tension. Choose the hook register that fits:
- TENSION: Mid-action danger (default for conspiracy/assassination)
- DREAD THROUGH BEAUTY: Something peaceful the viewer knows will be destroyed
- MYSTERY: An impossible question or paradox
- INTIMACY: One person, one decision, one moment of no return

POV SHIFTS: The best documentaries shift perspective at least once. Include at least one moment where the narration pivots: "To the emperor, this was routine. To the 3,000 prisoners below, it was a death sentence." Plan where this shift happens.

REFLECTION BEAT: After the climax in Act 3, include a planned "breathing room" moment — 8-12 seconds of silence (no narration) where the image holds and the music carries the emotion. This lands the twist before the ending wraps up. Mark this in your pacing_notes.

EMOTIONAL BLUEPRINT: Your story structure must serve this emotional arc (by video percentage):
- 0-5%: INTRIGUE — curiosity gap, urgent hook (145-155 WPM, low music)
- 5-25%: CONTEXT — measured setup, building the world (120-130 WPM)
- 25-45%: RISING — tension building, stakes rising (130-140 WPM)
- 45-55%: FIRST REVEAL — slow down, let the revelation land (95-110 WPM, deep black transition)
- 55-70%: ESCALATION — intensify, faster cuts (135-145 WPM, high music)
- 70-82%: CLIMAX — peak intensity, devastation (100-115 WPM, hard cut transitions)
- 82-88%: SILENCE — near-zero music, hushed voice, extended black hold (80-95 WPM)
- 88-100%: RESOLUTION — music swell, reflective close (105-120 WPM)
Place your major reveal between 45-55% of the story. The silence beat (82-88%) is critical — plan for it explicitly in your pacing_notes. Act boundaries should roughly align with these phase transitions.

Your output must be a JSON object with this structure:
{{
  "topic": "string",
  "chosen_angle": "string",
  "structure_type": "CLASSIC | MYSTERY | DUAL_TIMELINE | COUNTDOWN | TRIAL | REFRAME",
  "length_tier": "STANDARD | DEEP_DIVE | EPIC",
  "estimated_length_minutes": number,
  "cold_open": "string — 1-2 devastating sentences that flash-forward to the climax or set the emotional tone. This plays BEFORE the hook.",
  "hook_register": "TENSION | DREAD_THROUGH_BEAUTY | MYSTERY | INTIMACY",
  "hook": {{
    "opening_scene": "string — specific moment to open on (register-appropriate, not always action)",
    "stakes": "string — what is at risk in this moment",
    "opening_question": "string — the question the video answers"
  }},
  "act1": {{
    "title": "string — varies by structure type (e.g. 'The Accepted Narrative' for CLASSIC, 'The Crime Scene' for MYSTERY, 'Timeline A' for DUAL_TIMELINE, 'The Final Moment' for COUNTDOWN, 'The Prosecution' for TRIAL)",
    "summary": "string — what this act covers in the chosen structure",
    "key_beats": ["array of story beats to cover"],
    "cliffhanger": "string — what question/tension closes Act 1"
  }},
  "act2": {{
    "title": "string — varies by structure type (e.g. 'The Cracks Appear' for CLASSIC, 'Rewinding the Clock' for MYSTERY, 'Timeline B / Convergence' for DUAL_TIMELINE, 'The Decisions' for COUNTDOWN, 'The Defense' for TRIAL)",
    "summary": "string — how tension builds in the chosen structure",
    "evidence_sequence": ["ordered list of evidence/beats to introduce"],
    "tension_peak": "string — the moment of maximum dread before the reveal"
  }},
  "act3": {{
    "title": "string — varies by structure type (e.g. 'The Real Story' for CLASSIC, 'The Why' for MYSTERY, 'The Collision' for DUAL_TIMELINE, 'The First Domino' for COUNTDOWN, 'The Verdict' for TRIAL)",
    "summary": "string — the twist reveal or climax",
    "reveal_sequence": ["how the reveal unfolds beat by beat"],
    "sources_for_reveal": ["the 2+ sources that back the twist"]
  }},
  "ending": {{
    "reframe": "string — how this changes everything the viewer thought",
    "final_line": "string — the last sentence of the video",
    "cta": "string — one clean line after the story ends"
  }},
  "pov_shift": {{
    "location": "string — where in the story does the perspective shift (e.g. 'end of Act 2')",
    "from_perspective": "string — whose view we start with",
    "to_perspective": "string — whose view we shift to",
    "line": "string — the exact pivot sentence"
  }},
  "reflection_beat": {{
    "placement": "string — where this moment of silence goes (e.g. 'after Act 3 reveal')",
    "visual": "string — what image holds during the silence",
    "duration_seconds": "number — 8 to 12 seconds"
  }},
  "archival_moment": "string — the one real quote/document/detail to include",
  "emotional_arc": "string — the emotional journey from open to close",
  "pacing_notes": "string — where to accelerate, where to breathe, where to hold silence"
}}

Return ONLY valid JSON. No preamble, no markdown fences.
"""


def run(research: dict, angle: dict) -> dict:
    topic = research.get("topic", "Unknown")
    print(f"[Narrative Architect] Designing story structure for: {topic}")
    print(f"[Narrative Architect] Angle: {angle.get('chosen_angle', 'N/A')}")

    guidance = get_agent_guidance("agent_03")
    effective_system = SYSTEM_PROMPT + (f"\n\nANALYTICS GUIDANCE:\n{guidance}" if guidance else "")

    # Inject retention curve and pacing intelligence
    try:
        retention_intel = get_retention_intelligence()
        if retention_intel:
            effective_system += f"\n\n{retention_intel}"
    except Exception:
        pass

    # Inject content quality intelligence (which structures perform best)
    try:
        from intel.channel_insights import get_content_quality_intelligence, get_content_quality_recommendation
        cq_intel = get_content_quality_intelligence()
        if cq_intel:
            effective_system += f"\n\n{cq_intel}"
        cq_rec = get_content_quality_recommendation("narrative_architect")
        if cq_rec:
            effective_system += f"\n\nCONTENT STRUCTURE RECOMMENDATION: {cq_rec}"
    except Exception:
        pass

    # Inject exemplar hooks from top-performing videos
    try:
        from intel.channel_insights import get_exemplar_hooks
        exemplars = get_exemplar_hooks()
        if exemplars:
            effective_system += f"\n\n{exemplars}"
    except Exception:
        pass

    result = call_agent(
        "03_narrative_architect",
        system_prompt=effective_system,
        user_prompt=f"""Topic: {topic}
Chosen angle: {angle.get('chosen_angle')}
Central figure: {angle.get('central_figure')}
Hook moment: {angle.get('hook_moment')}
Twist potential: {angle.get('twist_potential')}

Full research:
{json.dumps(research, indent=2)}

Full angle brief:
{json.dumps(angle, indent=2)}

Design the complete story blueprint. Remember:
- FIRST choose the best narrative structure (CLASSIC, MYSTERY, DUAL_TIMELINE, COUNTDOWN, TRIAL, or REFRAME) for THIS topic
- Set structure_type to your chosen structure
- Write a cold_open — 1-2 devastating sentences that play BEFORE the hook
- Choose a hook_register (TENSION, DREAD_THROUGH_BEAUTY, MYSTERY, or INTIMACY) — do NOT always use TENSION
- The hook should open on or near {angle.get('hook_moment')} but adapt to your chosen register
- Choose a length_tier: STANDARD (8-10 min) for most topics, DEEP_DIVE (15-18 min) for topics with rich scholarly debate, EPIC (22-25 min) rarely for civilisation-scale stories
- Adapt the act titles and flow to match your chosen structure
- Act 1 should include a moment of warmth or wonder — humanize before darkening
- Act 2 builds tension but allow moments of absurdity when history is stranger than fiction
- The twist/reframe in Act 3 must be earned by everything before it
- The final line must land in silence
- Do NOT default to CLASSIC — pick the structure that creates the most dramatic tension""",
        max_tokens=8000,
        stage_num=3,
        topic=topic,
    )

    if isinstance(result, list):
        result = result[0] if result and isinstance(result[0], dict) else {"acts": result}
    # Enforce length caps per tier
    tier = result.get("length_tier", "STANDARD").upper()
    tier_caps = {"STANDARD": 10, "DEEP_DIVE": 18, "EPIC": 25}
    max_mins = tier_caps.get(tier, 10)
    if "estimated_length_minutes" in result:
        try:
            result["estimated_length_minutes"] = min(float(result["estimated_length_minutes"]), max_mins)
        except (TypeError, ValueError):
            result["estimated_length_minutes"] = max_mins
    # Default missing fields for backward compatibility
    result.setdefault("cold_open", "")
    result.setdefault("hook_register", "TENSION")
    result.setdefault("length_tier", "STANDARD")
    result.setdefault("pov_shift", {"location": "", "from_perspective": "", "to_perspective": "", "line": ""})
    result.setdefault("reflection_beat", {"placement": "after Act 3 reveal", "visual": "", "duration_seconds": 10})

    structure = result.get("structure_type", "UNKNOWN")
    print(f"[Narrative Architect] Structure: {structure}")
    print(f"[Narrative Architect] Estimated length: {result.get('estimated_length_minutes')} minutes")
    print(f"[Narrative Architect] Emotional arc: {result.get('emotional_arc', 'N/A')}")
    return result


if __name__ == "__main__":
    dummy_angle = {
        "topic": "The assassination of Julius Caesar",
        "chosen_angle": "Caesar deliberately provoked his own assassination as a final act of political genius",
        "central_figure": "Julius Caesar",
        "hook_moment": "The moment Caesar sees Brutus among the assassins and stops resisting",
        "twist_potential": "Caesar knew the plot, chose not to stop it, and engineered his own martyrdom",
    }
    dummy_research = {
        "topic": "The assassination of Julius Caesar",
        "era": "Ancient Rome, 44 BC",
        "core_facts": ["Caesar was stabbed 23 times on the Ides of March", "He had been warned repeatedly"],
        "suppressed_details": ["Caesar dismissed his bodyguard the day before", "Suetonius records Caesar stopped resisting after seeing Brutus"],
        "contradictions": ["Caesar had multiple warnings but took no protective action"],
        "archival_gems": ["Suetonius: 'he drew the toga over his face' — a deliberate gesture of acceptance"],
        "key_figures": [{"name": "Julius Caesar", "role": "Dictator", "significance": "The victim who may have chosen his fate"}],
        "timeline": [{"date": "March 14, 44 BC", "event": "Caesar dismisses his bodyguard"}],
        "primary_sources": ["Suetonius, The Twelve Caesars", "Plutarch, Life of Caesar"],
        "research_gaps": [],
    }
    result = run(dummy_research, dummy_angle)
    print(json.dumps(result, indent=2))
