"""
Agent 02 — Originality Agent
Finds the unique angle nobody else has covered.
Model: Sonnet 4.6 (creative reasoning + gap finding)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent_wrapper import call_agent
from intel.dna_loader import get_dna, get_agent_guidance
import json

DNA = get_dna(["identity", "content_strategy", "experiments"])

SYSTEM_PROMPT = f"""You are the Originality Agent for The Obsidian Archive YouTube channel.

{DNA}

Your job: Given research on a topic, find the angle nobody else has covered on YouTube.
The Obsidian Archive must always approach topics from a unique, surprising, and defensible angle.

Your output must be a JSON object with this structure:
{{
  "topic": "string",
  "dominant_youtube_angles": ["what existing videos cover about this topic"],
  "gaps_identified": ["angles/details existing videos all missed"],
  "chosen_angle": "string — the specific unique angle for this video",
  "angle_justification": "string — why this angle is surprising and defensible",
  "twist_potential": "string — what the twist reveal will be",
  "central_figure": "string — the one named human at the centre of THIS angle",
  "hook_moment": "string — the specific mid-action scene to open on",
  "angle_uniqueness_score": 8,
  "angle_uniqueness_notes": "string — explanation of how unique this angle is (1-10 scale, 10 = completely novel)",
  "is_experiment": false,
  "experiment_rule_broken": null
}}

Return ONLY valid JSON. No preamble, no markdown fences.
"""

def get_covered_angles() -> list:
    """Load all past video titles/topics from Supabase as the covered angles archive."""
    try:
        from clients.supabase_client import get_client
        client = get_client()
        result = client.table("videos").select("topic, title").execute()
        angles = []
        for row in result.data or []:
            title = row.get("title") or row.get("topic", "")
            if title:
                angles.append(title)
        return angles
    except Exception as e:
        print(f"[Originality Agent] Warning: could not load covered angles from Supabase: {e}")
        return []


def run(research: dict, is_experiment: bool = False) -> dict:
    topic = research.get("topic", "Unknown topic")
    print(f"[Originality Agent] Finding unique angle for: {topic}")

    COVERED_ANGLES_ARCHIVE = get_covered_angles()
    print(f"[Originality Agent] Loaded {len(COVERED_ANGLES_ARCHIVE)} covered angles from archive")

    # Step 1: Search YouTube for existing coverage
    youtube_search = call_agent(
        "02_originality_agent",
        system_prompt="You are researching what angles YouTube history channels have already covered on a topic. Search YouTube and the web to find the most common angles, titles, and narratives used by existing videos on this topic.",
        user_prompt=f"Search for YouTube videos about: {topic}\nList the most common angles, narrative approaches, and what these videos focus on. What do they all have in common? What do they tend to ignore?",
        max_tokens=2000,
        use_search=True,
        expect_json=False,
        stage_num=2,
        topic=topic,
    )

    # Step 2: Find the gap
    guidance = get_agent_guidance("agent_02")
    effective_system = SYSTEM_PROMPT + (f"\n\nANALYTICS GUIDANCE:\n{guidance}" if guidance else "")

    result = call_agent(
        "02_originality_agent",
        system_prompt=effective_system,
        user_prompt=f"""Topic: {topic}
Is experiment video: {is_experiment}

Research fact sheet:
{json.dumps(research, indent=2)}

Existing YouTube coverage found:
{youtube_search}

Previously covered angles in our archive (DO NOT repeat these):
{json.dumps(COVERED_ANGLES_ARCHIVE, indent=2)}

Find the angle that:
1. No existing YouTube video has taken
2. Is NOT in our archive
3. Uses the suppressed details and contradictions in the research
4. Has strong twist reveal potential
5. Can be built around one named human figure
6. Opens on a cinematic mid-action moment

{"Since this is an EXPERIMENT video: deliberately choose an angle that breaks one of our standard DNA rules. Specify which rule you're testing in experiment_rule_broken." if is_experiment else ""}""",
        max_tokens=2000,
        stage_num=2,
        topic=topic,
    )

    if isinstance(result, list):
        result = {"chosen_angle": result[0] if result else "", "angles": result}
    # Step 3: Verify angle uniqueness — search YouTube for the chosen angle specifically
    chosen_angle = result.get("chosen_angle", "")
    if chosen_angle:
        print("[Originality Agent] Checking uniqueness of chosen angle...")
        try:
            angle_search = call_agent(
                "02_originality_agent",
                system_prompt="You are checking whether a specific video angle/narrative has already been covered on YouTube. Search for YouTube videos that take this exact angle or very similar approach. Count how many videos cover this same angle closely. Be honest — if multiple videos already cover this, say so.",
                user_prompt=f"Search YouTube for videos about '{topic}' that specifically take this angle: '{chosen_angle}'\nHow many existing videos cover this exact angle or something very similar? List them if found.",
                max_tokens=1500,
                use_search=True,
                expect_json=False,
                stage_num=2,
                topic=topic,
            )

            # Use Claude to evaluate uniqueness based on the search results
            uniqueness_eval = call_agent(
                "02_originality_agent",
                system_prompt="You evaluate angle uniqueness. Given YouTube search results about a specific angle, determine: 1) How many existing videos cover this exact angle (0, 1, 2, 3+)? 2) Score uniqueness 1-10 (10=completely novel, 1=heavily covered). Return JSON: {\"existing_video_count\": number, \"uniqueness_score\": number, \"assessment\": \"string\"}",
                user_prompt=f"Topic: {topic}\nAngle: {chosen_angle}\n\nYouTube search results:\n{angle_search}\n\nHow unique is this angle?",
                max_tokens=500,
                effort_offset=-1,  # Haiku for simple evaluation
                stage_num=2,
                topic=topic,
            )

            score = uniqueness_eval.get("uniqueness_score", 5)
            existing = uniqueness_eval.get("existing_video_count", 0)
            result["angle_uniqueness_score"] = score
            result["angle_uniqueness_notes"] = uniqueness_eval.get("assessment", "")

            if existing >= 3:
                print(f"[Originality Agent] WARNING: {existing} videos already cover this angle (score: {score}/10)")
                print(f"[Originality Agent] Consider a more unique take: {uniqueness_eval.get('assessment', '')[:200]}")
            else:
                print(f"[Originality Agent] Angle uniqueness: {score}/10 ({existing} similar videos found)")
        except Exception as e:
            print(f"[Originality Agent] Warning: Angle uniqueness check failed: {e}")
            result.setdefault("angle_uniqueness_score", 5)
            result.setdefault("angle_uniqueness_notes", "Uniqueness check failed — defaulting to medium")

    print(f"[Originality Agent] Chosen angle: {result.get('chosen_angle', 'N/A')}")
    print(f"[Originality Agent] Twist potential: {result.get('twist_potential', 'N/A')}")
    return result


if __name__ == "__main__":
    # Test with dummy research
    dummy_research = {
        "topic": "The assassination of Julius Caesar",
        "era": "Ancient Rome",
        "core_facts": ["Caesar was stabbed 23 times", "The conspirators numbered over 60"],
        "key_figures": [{"name": "Marcus Junius Brutus", "role": "Lead conspirator", "significance": "Caesar's trusted friend"}],
        "suppressed_details": ["Caesar may have welcomed death", "Some conspirators were Caesar's own appointees"],
        "contradictions": ["Suetonius says Caesar stopped resisting after seeing Brutus"],
        "archival_gems": ["Caesar's last words remain disputed — Suetonius records silence, not 'Et tu Brute'"],
        "research_gaps": [],
        "timeline": [],
        "primary_sources": [],
    }
    result = run(dummy_research)
    print(json.dumps(result, indent=2))
