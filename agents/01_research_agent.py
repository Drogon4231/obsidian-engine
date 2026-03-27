"""
Agent 01 — Research Agent
Uses web search to deep dive the topic and build a structured fact sheet.
Model: Sonnet 4.6 (complex multi-source synthesis)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent_wrapper import call_agent
from intel.dna_loader import get_dna
import json

DNA = get_dna(["identity", "content_strategy"])

SYSTEM_PROMPT = f"""You are the Research Agent for The Obsidian Archive YouTube channel.

{DNA}

Your job: Given a topic, conduct deep research and produce a comprehensive fact sheet.
Focus on: little-known facts, primary sources, real names/dates/places, suppressed narratives,
contradictions in mainstream accounts, genuine archival details.

You MUST return a JSON object with this exact structure:
{{
  "topic": "string",
  "era": "string",
  "core_facts": ["array of key verified facts"],
  "key_figures": [{{"name": "string", "role": "string", "significance": "string"}}],
  "timeline": [{{"date": "string", "event": "string"}}],
  "suppressed_details": ["facts mainstream accounts tend to omit"],
  "primary_sources": ["real documents, quotes, records that exist"],
  "contradictions": ["places where mainstream narrative contradicts evidence"],
  "archival_gems": ["specific quotes, documents, dates that feel authentic and cinematic"],
  "research_gaps": ["what we couldn't verify — flags for fact checker"]
}}

Return ONLY valid JSON. No preamble, no markdown fences.
"""


def run(topic: str) -> dict:
    print(f"[Research Agent] Researching: {topic}")

    # Step 1: Web search for raw material
    search_results = call_agent(
        "01_research_agent",
        system_prompt="You are a historical research assistant. Search for accurate information about the given topic. Find key figures, specific dates, lesser-known facts, and contradictions in mainstream accounts.",
        user_prompt=f"Research this historical topic: {topic}\n\nFind: key figures, specific dates, lesser-known facts, suppressed aspects, contradictions.",
        max_tokens=8000,
        use_search=True,
        expect_json=False,
        effort_offset=-1,  # Haiku for search
        stage_num=1,
        topic=topic,
    )

    # Step 2: Structure into fact sheet
    result = call_agent(
        "01_research_agent",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"""Topic: {topic}

Raw research gathered:
{search_results}

Now structure this into a precise fact sheet JSON. Prioritise:
- Specific names over generic descriptions
- Exact dates over approximate ones
- Lesser-known facts over well-known ones
- Suppressed or contradicted narratives
- Anything that could form the basis of a twist reveal""",
        max_tokens=8000,
        stage_num=1,
        topic=topic,
    )

    if isinstance(result, list):
        result = {"core_facts": result}
    print(f"[Research Agent] Found {len(result.get('core_facts', []))} core facts, "
          f"{len(result.get('key_figures', []))} key figures")
    return result


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "The assassination of Julius Caesar"
    result = run(topic)
    print(json.dumps(result, indent=2))
