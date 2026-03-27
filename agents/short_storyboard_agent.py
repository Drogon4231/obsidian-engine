"""
Short Storyboard Agent
Generates 3-4 scene visual breakdown for a YouTube Short (9:16 portrait format).
Image prompts are composed for vertical framing — subject centred, lower 40% dark for captions.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent_wrapper import call_agent
from intel.dna_loader import get_dna

DNA = get_dna(["identity", "content_strategy"])

SYSTEM_PROMPT = f"""You are the Shorts Storyboard Agent for The Obsidian Archive YouTube channel.

{DNA}

Your job: Create a 3-4 scene visual storyboard for a 45-60 second YouTube Short in 9:16 PORTRAIT format.

CRITICAL — 9:16 PORTRAIT FRAMING RULES:
- All images are VERTICAL (tall, narrow) — think phone screen, not cinema screen
- Subject must be centred in the UPPER 60% of the frame
- Leave the LOWER 40% dark/empty — captions will appear there
- Avoid wide landscape compositions entirely
- Think: close-up face portraits, vertical stone columns, lone figure in tall doorway,
  vertical shaft of light, tower from below, altar from low angle

SCENE COUNT: Exactly 3-4 scenes to cover the full Short duration.

For each scene, the image_prompt must be:
- Extremely specific about vertical composition
- Cinematic, painterly, historically accurate
- High contrast lighting for drama (single torch, shaft of moonlight, firelight)
- No modern elements, watermarks, or text

Return a JSON object:
{{
  "scenes": [
    {{
      "scene_id": 1,
      "narration_segment": "string — the portion of script this scene covers (first few words...)",
      "duration_seconds": number,
      "image_prompt": "string — detailed 9:16 portrait composition, cinematic painting style",
      "mood": "dark" | "tense" | "dramatic" | "cold" | "reverent" | "wonder" | "warmth" | "absurdity"
    }}
  ],
  "total_scenes": number
}}

Duration of all scenes must sum to the estimated_seconds.
Return ONLY valid JSON. No preamble, no markdown fences.
"""


def run(short_script_data: dict) -> dict:
    full_script = short_script_data.get("full_script", "")
    topic       = short_script_data.get("topic", "Unknown")
    est_seconds = short_script_data.get("estimated_seconds", 50)
    hook        = short_script_data.get("hook", "")

    print(f"[Short Storyboard] Creating 9:16 portrait storyboard for: {topic}")

    result = call_agent(
        "short_storyboard_agent",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"""Topic: {topic}
Estimated Short duration: {est_seconds} seconds
Hook (first line): {hook}

Full narration script:
{full_script}

Create exactly 3-4 portrait-oriented (9:16) scenes.
Each image_prompt must explicitly describe a VERTICAL composition with the subject
in the upper 60% of the frame and darkness at the bottom for caption space.
Painterly, documentary aesthetic — oil-painting style, dramatic historical lighting.
Durations must sum to {est_seconds} seconds.""",
        max_tokens=2000,
        topic=topic,
    )

    scenes = result.get("scenes", [])
    result["total_scenes"] = len(scenes)
    print(f"[Short Storyboard] {result['total_scenes']} portrait scenes created")
    return result


if __name__ == "__main__":
    print("Short Storyboard Agent requires pipeline input. Run via orchestrator.")
