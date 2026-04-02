"""
Agent 06 — SEO Agent
Generates YouTube-optimised titles, description, tags, and chapter markers.
Model: Haiku 4.5 — pattern-based task, no deep reasoning needed.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent_wrapper import call_agent
from intel.dna_loader import get_dna, get_agent_guidance
from intel.channel_insights import get_search_intelligence, get_engagement_intelligence
import json

DNA = get_dna(["identity", "content_strategy", "channel_intelligence"])


def _fmt_ts(seconds) -> str:
    """Format seconds as M:SS for chapter markers."""
    try:
        s = int(float(seconds))
        return f"{s // 60}:{s % 60:02d}"
    except (ValueError, TypeError):
        return "0:00"

SYSTEM_PROMPT = f"""You are the SEO Agent for The Obsidian Archive YouTube channel.

{DNA}

Your job: Generate YouTube-optimised metadata from the final verified script.
Every title must create a curiosity gap. Every tag must be strategically chosen.

YouTube SEO principles for this channel:
- Titles: 60–70 characters max, high curiosity gap, hint at the twist without revealing it
- Titles must feel cinematic, not clickbait — think documentary poster, not tabloid
- Description: First 2 lines visible before "show more" — must hook immediately
- Tags: mix of broad (history, dark history) and specific (Julius Caesar, Roman Empire)
- CRITICAL: Tags must be plain text only — NO special characters like < > " & = [ ] curly braces, NO hashtag symbols, NO commas within a single tag
- Chapter markers improve watch time — place at every major story beat

Your output must be a JSON object with this structure:
{{
  "topic": "string",
  "title_variants": [
    {{"title": "string", "character_count": number, "strategy": "string"}}
  ],
  "recommended_title": "string",
  "description": {{
    "hook_lines": "string — first 2 lines (visible before show more)",
    "full_description": "string — complete description with sources",
    "hashtags": ["#hashtag1", "#hashtag2"]
  }},
  "tags": ["tag1", "tag2"],
  "chapter_markers": [
    {{"timestamp": "0:00", "label": "string"}}
  ],
  "thumbnail_text": "string — max 4 words for thumbnail overlay",
  "thumbnail_concepts": [
    {{"concept": "string — visual description", "text_overlay": "string", "rationale": "string"}}
  ],
  "end_screen_cta": "string — the one CTA line for end screen"
}}

Return ONLY valid JSON. No preamble, no markdown fences.
"""


def run(script: dict, verification: dict, angle: dict) -> dict:
    topic = script.get("topic", "Unknown")
    print(f"[SEO Agent] Generating metadata for: {topic}")

    sources = verification.get("source_list_for_description", [])

    guidance = get_agent_guidance("agent_06")
    effective_system = SYSTEM_PROMPT + (f"\n\nANALYTICS GUIDANCE:\n{guidance}" if guidance else "")

    # Inject search and engagement intelligence
    try:
        search_intel = get_search_intelligence()
        if search_intel:
            effective_system += f"\n\n{search_intel}"
        engagement_intel = get_engagement_intelligence()
        if engagement_intel:
            effective_system += f"\n\n{engagement_intel}"
    except Exception:
        pass

    result = call_agent(
        "06_seo_agent",
        system_prompt=effective_system,
        user_prompt=f"""Topic: {topic}
Angle: {angle.get('chosen_angle', 'N/A')}
Twist reveal (DO NOT reveal in title): {angle.get('twist_potential', 'N/A')}
Central figure: {angle.get('central_figure', 'N/A')}
Estimated duration: {script.get('estimated_duration_minutes', 8)} minutes
Era: Ancient / Medieval / Colonial / Modern history

Full script summary:
Hook: {script.get('script', {}).get('hook', '')[:300]}
Twist: {script.get('script', {}).get('act3', '')[:200]}
Final line: {script.get('script', {}).get('ending', '')[-200:]}

Verified sources for description:
{json.dumps(sources, indent=2)}

Generate all SEO metadata.

For chapter markers, use this timing structure based on {script.get('estimated_duration_minutes')} minute runtime:
- 0:00 — Hook/opening (first 7% of runtime)
- {_fmt_ts(script.get('estimated_duration_minutes', 8) * 60 * 0.07)} — Act 1: The accepted narrative
- {_fmt_ts(script.get('estimated_duration_minutes', 8) * 60 * 0.28)} — Act 2: The cracks appear
- {_fmt_ts(script.get('estimated_duration_minutes', 8) * 60 * 0.67)} — Act 3: The real story
- {_fmt_ts(script.get('estimated_duration_minutes', 8) * 60 * 0.90)} — Ending/reflection
Add 2-3 additional chapter markers within Act 2 at major evidence beats.

For titles: create 5 variants. Each must:
1. Create strong curiosity gap
2. Hint at darkness without cheap clickbait
3. Feel like a documentary title, not a tabloid headline
4. Be 60–70 characters
5. Include the central figure's name when possible
6. NEVER use parenthetical suffixes like '(Part 1: The X)' in titles. Each title must stand alone as a complete, compelling statement. Series parts should be signaled through content, not labels.

CRITICAL SEO RULES:
- The target keyword MUST appear in the FIRST LINE of the full_description field.
- The target keyword MUST also be included in the tags array.
- Do NOT modify the narrative title format — keep titles cinematic and curiosity-driven.
- SEO discoverability is achieved through description and tags, NOT through keyword-stuffing titles.""",
        max_tokens=4000,
        stage_num=6,
        topic=topic,
    )

    if isinstance(result, list):
        result = result[0] if result and isinstance(result[0], dict) else {"tags": result}
    print(f"[SEO Agent] Recommended title: {result.get('recommended_title', 'N/A')}")
    print(f"[SEO Agent] Tags generated: {len(result.get('tags', []))}")
    return result


if __name__ == "__main__":
    print("SEO Agent requires full pipeline input. Run via orchestrator.")
