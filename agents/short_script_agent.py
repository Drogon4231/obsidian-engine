"""
Short Script Agent
Writes a 45-60 second YouTube Shorts script (~130 words).
Structure: Hook (2s) → Claim (15s) → Tension (18s) → Payoff (12s) → CTA (8s)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent_wrapper import call_agent
from intel.dna_loader import get_dna
from intel.channel_insights import get_shorts_intelligence
import json

DNA = get_dna(["identity", "content_strategy"])

SYSTEM_PROMPT = f"""You are the Shorts Script Agent for The Obsidian Archive YouTube channel.

{DNA}

Your job: Write a punchy 45-60 second YouTube Shorts script (~130 words) for a historical topic.

SHORTS SCRIPT STRUCTURE (must follow exactly):
1. HOOK (2-3 seconds, 8-12 words): One shocking statement or question. Start mid-story. No preamble.
2. CLAIM (15 seconds, 40-50 words): The most disturbing or surprising fact. Visceral. Specific.
3. TENSION (18 seconds, 45-55 words): Escalate — who knew, what was hidden, why it matters.
4. PAYOFF (12 seconds, 25-35 words): The twist — but cut it short. Leave them wanting the full story.
5. CTA (5 seconds, 12-15 words): "The full documentary is on The Obsidian Archive — link in description."

RULES:
- Total word count: 120-145 words ONLY
- Every sentence must earn its place — no filler
- Write for AUDIO — narration, not text to read
- The hook must work as a caption in the first 2 seconds — it must STOP the scroll
- Do NOT reveal the full story — tease it mercilessly
- Tone: documentary gravitas, not TikTok hype

SHORTS-SPECIFIC RETENTION TACTICS:
- First 2 words must create a pattern interrupt ("They ate...", "The Pope's...", "Nobody survived...")
- Use sentence fragments and em-dashes for spoken punch — NOT long compound sentences
- Include ONE specific number or date in the first 10 seconds (specificity = credibility)
- The TENSION section should feel like rapid-fire revelations, not narration
- End the PAYOFF mid-thought if possible — incomplete loops drive viewers to the full video
- No warm-up, no context-setting — start IN the most disturbing moment

STANDALONE STORYTELLING:
- This Short must be satisfying on its own — a complete mini-story, not just a trailer
- The PAYOFF should resolve ONE question while opening a BIGGER one
- Example: "The poison worked. The emperor was dead. But nobody asked the real question — who supplied the poison? And why did they want the NEXT emperor on the throne even more?"
- The Short should make the viewer feel like they learned something, AND that there's a deeper story
- Never say "watch the full video" — instead, end on an unresolved question that makes the viewer seek out more

Return a JSON object with this exact structure:
{{
  "hook": "string — the opening line only",
  "full_script": "string — complete narration (all 5 parts joined, no section headers)",
  "word_count": number,
  "estimated_seconds": number,
  "cta_line": "The full documentary is on The Obsidian Archive — link in description.",
  "short_title": "string — YouTube Short title ≤ 60 chars, ends with #Shorts",
  "short_description": "string — 3 lines: hook + channel plug + hashtags #Shorts #History #DarkHistory",
  "short_tags": ["tag1", "tag2", "tag3"]
}}

Return ONLY valid JSON. No preamble, no markdown fences.
"""


def run(research_data: dict, angle_data: dict) -> dict:
    topic = research_data.get("topic", research_data.get("chosen_topic", "Unknown"))
    print(f"[Short Script] Writing Shorts script for: {topic}")

    # Extract key facts from research (handle different schema keys)
    key_facts = (
        research_data.get("core_facts")
        or research_data.get("key_facts")
        or research_data.get("facts", [])
    )

    # Extract angle info (handle different schema keys)
    unique_angle = (
        angle_data.get("unique_angle")
        or angle_data.get("chosen_angle")
        or angle_data.get("angle", "")
    )
    twist = (
        angle_data.get("twist_potential")
        or angle_data.get("gap_in_coverage")
        or angle_data.get("twist", "")
    )
    central_figure = (
        angle_data.get("central_figure")
        or angle_data.get("key_figure", "")
    )

    # Inject shorts performance intelligence (top hooks, best eras, conversion data)
    try:
        shorts_intel = get_shorts_intelligence()
    except Exception as e:
        print(f"[Short Script] Warning: could not load shorts intelligence: {e}")
        shorts_intel = ""
    intel_block = f"\n\nSHORTS PERFORMANCE DATA:\n{shorts_intel}" if shorts_intel else ""

    result = call_agent(
        "short_script_agent",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"""Topic: {topic}

Chosen angle: {unique_angle}
Twist (DO NOT fully reveal): {twist}
Central figure: {central_figure}

Key facts from research:
{json.dumps(key_facts[:6], indent=2)}{intel_block}

Write the 45-60 second Shorts script. The hook must be impossible to scroll past.
Make every word earn its place — this is narration for a 9:16 portrait video.""",
        max_tokens=2000,
        topic=topic,
    )

    # Inject topic for downstream use
    result["topic"] = topic

    wc = result.get("word_count", len(result.get("full_script", "").split()))
    est = result.get("estimated_seconds", round(wc / 2.5))
    print(f"[Short Script] {wc} words | ~{est}s | {result.get('short_title', 'N/A')}")
    return result


if __name__ == "__main__":
    print("Short Script Agent requires pipeline input. Run via orchestrator.")
