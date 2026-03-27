"""
Agent 07b - Visual Continuity
Establishes a "visual bible" for each video — consistent art style, color palette,
character descriptions, and recurring motifs — then restructures every scene's image
prompt so AI-generated frames look like they came from the same documentary.

Runs after 07_scene_breakdown and before image generation.
Model: Sonnet 4.6
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.agent_wrapper import call_agent


def run(scene_data: dict) -> dict:
    scenes = scene_data.get("scenes", [])
    topic = scene_data.get("topic", "")
    total_scenes = len(scenes)

    if not scenes:
        print("[Visual Continuity] No scenes to process")
        return scene_data

    print(f"[Visual Continuity] Creating visual bible for {total_scenes} scenes...")

    # Build a compact representation of all scenes for the prompt
    scenes_summary = []
    for i, scene in enumerate(scenes):
        scenes_summary.append({
            "scene_id": scene.get("scene_id", i + 1),
            "narration": scene.get("narration", ""),
            "visual_description": scene.get("visual_description", ""),
            "visual_type": scene.get("visual_type", ""),
            "mood": scene.get("mood", ""),
            "characters_mentioned": scene.get("characters_mentioned", []),
            "year": scene.get("year", ""),
            "location": scene.get("location", ""),
            "narrative_position": scene.get("narrative_position", ""),
            "is_reveal_moment": scene.get("is_reveal_moment", False),
        })

    system = f"""You are a visual director creating a VISUAL BIBLE for a documentary video.

Your job is to ensure that every AI-generated image in this video looks like it came from
the SAME documentary — not a random collection of unrelated images from different artists.

You will receive all {total_scenes} scenes. You must produce:

1. A VISUAL BIBLE (top-level consistency rules):
   - art_style: A 20-30 word style description that will be appended to EVERY image prompt.
     This is the single most important thing — it locks the entire video to one look.
     BAD: "cinematic style"
     GOOD: "oil painting with visible brushstrokes, warm amber lighting, desaturated background, Renaissance chiaroscuro influence, muted earth tones with selective vivid reds"
   - color_palette: Exactly 3-4 hex colors that unify the video's look. Pick from the topic's
     era/mood — cold blues for tragedy, warm ambers for golden ages, etc.
   - character_descriptions: An array of objects, each with "name" and "description" keys,
     giving a CONSISTENT visual description (clothing, approximate age, distinctive features,
     build). Every time this character appears across scenes, they must look the SAME.
     BAD: [{{"name": "Caesar", "description": "a Roman leader"}}]
     GOOD: [{{"name": "Caesar", "description": "gaunt man in his 50s, receding hairline, deep-set eyes, white toga with purple border, golden laurel wreath, sharp aquiline nose, thin lips pressed together"}}]
   - recurring_motifs: 2-3 visual metaphors to weave through the video. These create
     subconscious visual continuity.
     Example: ["a cracked hourglass symbolizing time running out", "ravens perched in the background as omens", "a single candle flame growing dimmer scene by scene"]

2. For EACH scene, a restructured prompt with:
   - core_composition: 20-30 word core image description — the WHAT of the image. Specific,
     cinematic, frozen-moment.
     BAD: "a king looking sad"
     GOOD: "LOW ANGLE: King Henry slumped on oak throne, crown tilted, single candle guttering, empty great hall stretching into shadow"
   - style_suffix: Copy the art_style from the bible verbatim. Same for every scene.
   - visual_treatment: One of "standard" | "close_portrait" | "wide_establishing" | "artifact_detail" | "map_overhead" | "text_overlay_dark"
     Use variety — don't repeat the same treatment three times in a row. Guidelines:
     * "close_portrait" for emotional character moments
     * "wide_establishing" for new locations, opening shots
     * "artifact_detail" for objects, documents, weapons
     * "map_overhead" for geographic/journey context
     * "text_overlay_dark" for key dates or claims
     * "standard" for everything else
   - is_breathing_room: boolean — true if this scene should be a moment of visual silence
     (image holds longer, no caption overlay, music drops to ambient). Set this to true for
     1-2 scenes only, typically right after the emotional climax or the reveal moment.
     This gives the audience a beat to absorb what just happened.

Output strict JSON with this structure:
{{
  "visual_bible": {{
    "art_style": "...",
    "color_palette": ["#hex1", "#hex2", "#hex3"],
    "character_descriptions": [{{"name": "Name", "description": "visual description..."}}],
    "recurring_motifs": ["motif1", "motif2"]
  }},
  "enhanced_scenes": [
    {{
      "scene_id": 1,
      "core_composition": "...",
      "style_suffix": "...",
      "visual_treatment": "standard",
      "is_breathing_room": false
    }},
    ...
  ]
}}

Output ONLY the JSON. No preamble."""

    prompt = f"""Create a visual bible and enhanced image prompts for this {total_scenes}-scene documentary.

Topic: {topic}

Scenes:
{json.dumps(scenes_summary, indent=2)}

Return the visual bible and one enhanced prompt object per scene."""

    result = call_agent(
        "07b_visual_continuity",
        system_prompt=system,
        user_prompt=prompt,
        max_tokens=8000,
        stage_num=7,
        topic=topic,
    )

    # Extract results
    visual_bible = result.get("visual_bible", {})
    enhanced_scenes = result.get("enhanced_scenes", [])

    # Convert character_descriptions from array of {name, description} to dict
    # (schema uses array because Anthropic structured output forbids dynamic keys)
    char_list = visual_bible.get("character_descriptions", [])
    if isinstance(char_list, list):
        visual_bible["character_descriptions"] = {
            c["name"]: c["description"] for c in char_list
            if isinstance(c, dict) and "name" in c and "description" in c
        }
        result["visual_bible"] = visual_bible

    # Build a lookup by scene_id for merging
    enhanced_lookup = {}
    for es in enhanced_scenes:
        sid = es.get("scene_id")
        if sid is not None:
            enhanced_lookup[sid] = es

    # Merge enhanced prompts back into scene data
    breathing_count = 0
    for scene in scenes:
        sid = scene.get("scene_id", 0)
        enhanced = enhanced_lookup.get(sid, {})

        if enhanced:
            # Build the full enhanced visual_description from the restructured prompt
            core = enhanced.get("core_composition", scene.get("visual_description", ""))
            style = enhanced.get("style_suffix", visual_bible.get("art_style", ""))
            scene["visual_description"] = f"{core}. {style}" if style else core

            scene["core_composition"] = enhanced.get("core_composition", "")
            scene["style_suffix"] = enhanced.get("style_suffix", "")
            scene["visual_treatment"] = enhanced.get("visual_treatment", "standard")
            scene["is_breathing_room"] = enhanced.get("is_breathing_room", False)
        else:
            # Fallback: append art style to existing description
            art_style = visual_bible.get("art_style", "")
            if art_style and scene.get("visual_description"):
                scene["visual_description"] = f"{scene['visual_description']}. {art_style}"
            scene["core_composition"] = scene.get("visual_description", "")
            scene["style_suffix"] = visual_bible.get("art_style", "")
            scene["visual_treatment"] = "standard"
            scene["is_breathing_room"] = False

        if scene.get("is_breathing_room"):
            breathing_count += 1

    print(f"[Visual Continuity] {total_scenes} scenes enhanced, {breathing_count} breathing room moments")

    return {
        "scenes": scenes,
        "visual_bible": visual_bible,
        "total_scenes": total_scenes,
        "topic": topic,
    }
