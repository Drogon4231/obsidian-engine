"""
Channel DNA loader.
Each agent requests only the sections it needs — keeps prompts lean and caching effective.
"""

# Full Channel DNA distilled into structured sections.
# In production this would be read from the live docx/database.
# Agents request sections by key.

DNA_SECTIONS = {

    "identity": """
=== CHANNEL IDENTITY ===
Channel: The Obsidian Archive
Mission: Uncover sinister, suppressed, and deliberately forgotten chapters of human history.
Pitch: "History's darkest secrets. Told for the first time."
Core angle: The real story was different all along. Every video ends with a twist reveal.

What we are NOT:
- Not a textbook recap of well-known history
- Not sensationalist — darkness serves truth, not shock value
- Not conspiratorial — every claim is sourced and verified
- Not neutral — power corrupts, truth matters
""",

    "voice": """
=== VOICE & TONE ===
Primary tone: Cinematic and dramatic — like a Netflix documentary.
The voice carries the weight of knowing something the audience doesn't yet know.

Tone qualities:
- Gravitas: Measured, deliberate. Each sentence lands.
- Intimacy: Speaks to one viewer, not a crowd.
- Dread: Builds unease without announcing it.
- Precision: Exact names, dates, places always.
- Revelation: Every video builds toward something unexpected.

Language rules:
- Present tense narration ("he walks" not "he walked")
- Short sentences at moments of revelation. Longer sentences to build dread.
- No passive voice — someone always did something to someone.
- Named characters only — never "a soldier", always "Sergeant Aldric Voss"
- Numbers are specific — never "thousands died", always "an estimated 14,000 perished in 11 days"
- No filler phrases — never "in this video we'll explore", just start the story

Personality signatures:
- Address the viewer directly with "you" at least twice — make them a character
- Include unexpected modern analogies to make history visceral ("It's like finding out your city's water supply was poisoned — for eight years")
- Allow genuine narrator reactions at moments of absurdity or horror ("And this is where history stops making sense")
- Dark humor when the history warrants it — deadpan delivery of genuinely bizarre facts
- POV shifts: show the same event from two perspectives at least once per video
""",

    "content_strategy": """
=== CONTENT STRATEGY ===
Core angle: The real story was different all along. Every video ends with a twist reveal.

Era coverage (all HIGH priority):
- Ancient (Egypt, Rome, Greece): cover-ups, assassinations, suppressed cults, poisoned emperors
- Medieval & Renaissance: inquisitions, plague manipulation, forbidden knowledge, dark courts
- Colonial & Revolutionary: genocide reframing, hidden resistance, manufactured heroes
- Modern (1800s–1900s): war crimes, state manipulation, industrial atrocities

Video length tiers:
- STANDARD: Most topics → 8–10 minutes (1,000–1,300 words). Default tier.
- DEEP DIVE: Topics with rich scholarly debate or multiple factions → 15–18 minutes (1,950–2,340 words). Use when standard would oversimplify.
- EPIC: Rare (1 per month max). Multi-layer civilisation-scale stories → 22–25 minutes (2,860–3,250 words).
- Never pad for length. Never cut for brevity. Length follows the story.

Originality rules:
- Before every video: identify the dominant YouTube angle on this topic
- Find what all existing videos missed or ignored
- Check archive — never repeat an angle previously covered
- The angle must be: sourced, specific, surprising
""",

    "story_structure": """
=== SIGNATURE STORY STRUCTURE ===

COLD OPEN (0:00 – 0:08):
- A single devastating line or image BEFORE the hook begins
- Flash-forward to the emotional climax or aftermath
- Examples: "In the end, they burned the city for three days. But that's not the dark part."
- Or a quiet, beautiful moment that gains horror in hindsight
- This is NOT the hook — it's a 1-2 sentence promise of what's coming

HOOK (0:08 – 0:45):
- Vary the emotional register — NOT always tension-first. Choose what fits:
  * TENSION: Start mid-action, maximum danger (default for conspiracy/assassination topics)
  * DREAD THROUGH BEAUTY: Open with something peaceful that the viewer knows will be destroyed
  * MYSTERY: Open with an impossible question or paradox
  * INTIMACY: Close on one person's face, one decision, one moment of no return
- Structure: Scene → Stakes → Question
- Drop into a specific moment (name, place, year), show what's at risk, pose the question
- The viewer must feel: I need to know how this ends

ACT 1 — The Accepted Narrative (0:45 – 25%):
- Tell the story everyone thinks they know
- Build conventional wisdom clearly — do NOT hint at the twist
- Let the audience believe it fully
- Include a moment of WARMTH or WONDER — humanize the protagonist before the story darkens

ACT 2 — The Cracks Appear (25% – 65%):
- Introduce anomalies, silenced voices, buried documents
- Each piece is a small fracture in the accepted story
- Pacing builds — sentences get shorter — dread accumulates
- Allow moments of ABSURDITY when history is stranger than fiction ("this actually happened")

ACT 3 — The Real Story (65% – 90%):
- THE TWIST REVEAL — the real story was different all along
- Must be earned — every Act 2 clue clicks into place here
- The reveal is an inevitability, not a surprise

ENDING (90% – 100%):
- Reframe everything the viewer thought they knew
- Last line makes them sit quietly before reaching for comments
- No "like and subscribe" — the story ends the video
- One clean CTA line after a beat

Mandatory elements:
- One named human at the centre of every story
- One moment of genuine archival detail per video (real quote, document, date)
- One cliffhanger between Act 1 and Act 2
- Twist reveal supported by at least TWO independent verified sources
""",

    "confidence_scores": """
=== DNA CONFIDENCE SCORES (v1.0 — all assumptions, 30%) ===
All rules start at 30% confidence. This means: follow them unless strong creative reason to deviate.
As analytics data comes in, scores update automatically.

Current rules at 30% confidence:
- Open mid-action hook
- Present tense narration
- Twist reveal ending
- One named human per story
- Dark thumbnail aesthetic
- 10–15 min standard length
- Ancient + Medieval priority
- Orchestral tension music
- Desaturated visual palette
- Max 4-word thumbnail text
""",

    "experiments": """
=== EXPERIMENTATION BUDGET ===
20% of weekly videos deliberately break one high-confidence rule to test new patterns.
At 1 video/day: 1–2 videos per week are designated experiments.
Never experiment with Fact Verification — accuracy is never a variable.
""",
}


def _load_channel_intelligence() -> str:
    """Dynamically load global channel intelligence block. Returns '' if unavailable."""
    try:
        from intel.channel_insights import get_global_intelligence_block, get_dna_confidence_block
        block = get_global_intelligence_block()
        conf  = get_dna_confidence_block()
        parts = [p for p in [block, conf] if p]
        return "\n\n".join(parts)
    except Exception:
        return ""


def _load_style_directive() -> str:
    """Load the active profile's style directive. Returns '' if unavailable."""
    try:
        from core.profile import get_style_directive
        return get_style_directive()
    except Exception:
        return ""


def get_dna(sections: list[str]) -> str:
    """Return concatenated DNA sections for the requested keys.
    Special key 'channel_intelligence' loads live analytics data dynamically.
    The active profile's style directive is always prepended."""
    parts = []

    # Inject profile style directive first (sets tone for all agents)
    style = _load_style_directive()
    if style:
        parts.append(f"=== CONTENT PROFILE ===\n{style}")

    for key in sections:
        if key == "channel_intelligence":
            block = _load_channel_intelligence()
            if block:
                parts.append(block.strip())
        elif key in DNA_SECTIONS:
            parts.append(DNA_SECTIONS[key].strip())
        else:
            print(f"[dna_loader] Warning: unknown section '{key}'")
    return "\n\n".join(parts)


def get_lessons() -> dict:
    """Load and return lessons_learned.json from the project root."""
    import json
    from pathlib import Path
    lessons_path = Path(__file__).resolve().parent.parent / "lessons_learned.json"
    if not lessons_path.exists():
        return {}
    try:
        with open(lessons_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"[dna_loader] Warning: could not load lessons_learned.json: {e}")
        return {}


def get_agent_guidance(agent_key: str) -> str:
    """Return guidance for a specific agent.
    Prefers channel_insights.py (data-backed), falls back to lessons_learned.json."""
    try:
        from intel.channel_insights import (
            get_topic_discovery_intelligence,
            get_seo_intelligence,
            get_narrative_intelligence,
            get_script_intelligence,
            get_scene_retention_intelligence,
        )
        mapping = {
            "agent_00": get_topic_discovery_intelligence,
            "agent_03": get_narrative_intelligence,
            "agent_04": get_script_intelligence,
            "agent_06": get_seo_intelligence,
            "agent_07": get_scene_retention_intelligence,
        }
        fn = mapping.get(agent_key)
        if fn:
            result = fn()
            if result:
                return result
    except Exception as e:
        print(f"[dna_loader] channel_insights fallback for {agent_key}: {e}")
    # Fallback to lessons_learned.json
    lessons = get_lessons()
    return lessons.get("agent_guidance", {}).get(agent_key, "")
