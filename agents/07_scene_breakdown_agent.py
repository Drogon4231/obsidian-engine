"""
Agent 07 - Scene Breakdown Agent
Splits script into scenes with rich metadata for each.
Model: Sonnet 4.6 (upgraded for richer scene analysis)
"""

import sys
import os
from typing import Optional
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.agent_wrapper import call_agent


def get_narrative_position(scene_idx: int, total_scenes: int) -> str:
    """Map scene index to narrative position using story-structure ratios."""
    pct = scene_idx / max(total_scenes - 1, 1)
    if pct < 0.07:
        return "hook"
    elif pct < 0.28:
        return "act1"
    elif pct < 0.67:
        return "act2"
    elif pct < 0.90:
        return "act3"
    else:
        return "ending"


def get_position_mood(position: str, scene_idx: int, total_scenes: int, current_mood: str = "") -> Optional[str]:
    """Act2 mood escalates from tense → dramatic toward the end; other positions return None.
    Preserves wonder/warmth/absurdity moods set by Claude — only overrides generic moods."""
    if position != "act2":
        return None
    # Don't override intentional emotional variety moods
    if current_mood in ("wonder", "warmth", "absurdity"):
        return None
    act2_start = int(total_scenes * 0.28)
    act2_end = int(total_scenes * 0.67)
    act2_len = max(act2_end - act2_start, 1)
    act2_progress = (scene_idx - act2_start) / act2_len
    return "dramatic" if act2_progress > 0.6 else "tense"


def get_retention_danger_zones() -> list:
    """
    Load channel_insights.json, find historical drop-off points.
    Return list of danger zones as percentages (e.g., [0.05, 0.25, 0.50, 0.75]).
    """
    try:
        from intel.channel_insights import load_insights
        insights = load_insights()
        if not insights:
            return []

        retention = insights.get("retention_analysis", {})

        # Check for explicit drop-off points
        drop_offs = retention.get("drop_off_points", [])
        if drop_offs:
            # Normalize to 0-1 range if they're percentages
            zones = []
            for point in drop_offs:
                val = float(point)
                if val > 1:
                    val = val / 100.0  # Convert from percentage to decimal
                zones.append(val)
            print(f"[Scene Breakdown] Retention danger zones from insights: {zones}")
            return sorted(zones)

        # Infer common danger zones from retention curve if available
        retention_curve = retention.get("retention_curve", [])
        if retention_curve and len(retention_curve) >= 4:
            zones = []
            for i in range(1, len(retention_curve)):
                prev = float(retention_curve[i - 1].get("retention", 100) if isinstance(retention_curve[i - 1], dict) else retention_curve[i - 1])
                curr = float(retention_curve[i].get("retention", 100) if isinstance(retention_curve[i], dict) else retention_curve[i])
                if prev - curr > 5:  # Significant drop (>5% drop)
                    pct = i / len(retention_curve)
                    zones.append(round(pct, 2))
            if zones:
                print(f"[Scene Breakdown] Retention danger zones inferred from curve: {zones}")
                return sorted(zones)

        # Default danger zones based on typical YouTube retention patterns
        print("[Scene Breakdown] Using default retention danger zones")
        return [0.05, 0.25, 0.50, 0.75]

    except Exception as e:
        print(f"[Scene Breakdown] Retention danger zone loading failed: {e}")
        return [0.05, 0.25, 0.50, 0.75]


def run(script_data, verification_data=None):
    full_script = script_data.get("full_script", "")
    topic = script_data.get("topic", "")
    word_count = len(full_script.split())

    # Scale scene count to script length
    target_scenes = max(15, min(35, word_count // 60))
    print(f"[Scene Breakdown] Breaking script into {target_scenes} scenes ({word_count} words)")

    # Load retention danger zones for pacing intelligence
    danger_zones = get_retention_danger_zones()
    retention_instruction = ""
    if danger_zones:
        zones_pct = [f"{int(z * 100)}%" for z in danger_zones]
        retention_instruction = f"""

RETENTION PACING (data-backed):
Viewers typically drop off at these points in the video: {', '.join(zones_pct)}.
Place high-tension moments or mini-cliffhangers at these danger zone timestamps. Never put exposition at a danger zone — always place reveals, twists, or shocking facts there.
For scenes that fall on a danger zone, include a "retention_hook" field — a brief (5-15 word) attention-recapture moment like a shocking question, a dramatic reveal teaser, or a pattern interrupt.
"""

    # Inject content quality scene intelligence
    cq_scene_intel = ""
    try:
        from intel.channel_insights import get_content_quality_recommendation
        cq_rec = get_content_quality_recommendation("scene_breakdown")
        if cq_rec:
            cq_scene_intel = f"\n\nSCENE STRUCTURE DATA: {cq_rec}"
    except Exception:
        pass

    system = f"""You are a documentary video editor breaking a narration script into exactly {target_scenes} scenes.
Each scene will drive AI image generation, so your visual descriptions must be CINEMATIC and SPECIFIC.

PACING WAVE — scene density must vary like a heartbeat, not a metronome:
- Hook scenes: 15-25 words (punchy, fast cuts)
- Act 1 setup: 30-45 words (measured, world-building)
- Act 2 escalation: 20-35 words (accelerating, tension)
- Reveal/climax: 10-20 words (devastatingly short — let the weight land)
- Breathing room: 5-10 words (near-silence, single image)
- Ending: 15-25 words (reflective, final thought)
Do NOT make every scene the same length. The variation IS the rhythm.

For each scene output:
- scene_id: sequential number starting at 1
- narration: the exact text for this scene (vary 5-45 words based on pacing wave above)
- duration_seconds: estimated speaking time (130 words per minute)
- visual_type: "historical_art" | "broll_atmospheric" | "broll_nature" | "map" | "text_overlay"
- visual_description: CINEMATIC image prompt (40-80 words) using CAMERA LANGUAGE — describe the SHOT, not just the scene. Include:
  * Shot type: CLOSE-UP, WIDE ESTABLISHING, MEDIUM, OVERHEAD, LOW ANGLE
  * Subject: specific people with clothing/armor, facial expression, body language
  * Setting: architecture, landscape, time of day, weather, light source
  * Action: what is happening in this exact frozen moment
  Think "cinematographer's shot brief", not "painting description."
  BAD: "a dark scene with a king"
  GOOD: "LOW ANGLE: King Henry slumped on his throne, crown tilted, candlelight catching the sweat on his brow, empty great hall stretching behind him into shadow, 1471"
- pexels_query: 3-5 word search query for Pexels footage
- wikimedia_query: specific artwork or artifact to search on Wikimedia
- mood: "dark" | "tense" | "reverent" | "cold" | "dramatic" | "wonder" | "warmth" | "absurdity"
  * wonder: moments of awe — vast architecture, impossible engineering, first discoveries
  * warmth: humanizing moments — genuine connection, tenderness before tragedy
  * absurdity: when history is stranger than fiction — bizarre true events that defy belief
- year: year or era mentioned in this scene (string, empty if none)
- location: primary location in this scene (string, empty if none)
- characters_mentioned: list of character names in this scene (array of strings)
- is_reveal_moment: true if this scene contains the twist reveal or major disclosure, false otherwise
- show_map: boolean — true if this scene mentions a specific location for the first time in the script
- show_timeline: boolean — true if this scene mentions a specific year or date
- lower_third: string or null — if a key figure is introduced for the first time, their "Name, Title" (e.g., "Emperor Claudius, Fourth Roman Emperor"). Null if no new figure is introduced.
- key_text: string or null — if there's a pivotal claim, date, or name that should appear on screen as a motion graphic overlay. Null if none.
- key_text_type: "date" | "claim" | "name" | null — the type of key_text for Remotion rendering
- retention_hook: string or null — if this scene falls near a viewer drop-off point, a brief attention-recapture moment (shocking question, dramatic reveal teaser, pattern interrupt). Null if not at a danger zone.
- visual_treatment: "standard" | "close_portrait" | "wide_establishing" | "artifact_detail" | "map_overhead" | "text_overlay_dark" — vary the visual treatment across scenes for pacing variety. Not every scene should be a standard establishing shot. Use:
  * close_portrait: for character introductions and emotional moments (face fills 60% of frame)
  * wide_establishing: for location reveals and scope moments
  * artifact_detail: for showing specific objects, documents, weapons
  * map_overhead: for geography and movement of armies/people
  * text_overlay_dark: for devastating quotes or statistics that should be read on screen
  * standard: default cinematic shot
- is_breathing_room: boolean — true for exactly 1-2 scenes that should have no narration overlay, just held image and music. Place these right AFTER major revelations to let the weight land. The narration text for these scenes should be very short (5-8 words) or a single powerful sentence.
- claim_confidence: "established" | "contested" | "speculative" | null — if this scene makes a historical claim:
  * "established": widely accepted by scholars with strong evidence
  * "contested": actively debated among historians, multiple interpretations exist
  * "speculative": the script is inferring or connecting dots without direct evidence
  * null: no specific historical claim in this scene (transitional, atmospheric)

CRITICAL: visual_description should paint a SPECIFIC historical moment, not abstract concepts.
BAD: "dark scene showing tension"
GOOD: "Emperor Claudius slumped at a marble banquet table, face ashen, golden chalice overturned, Roman senators watching in frozen horror, torchlit triclinium, 54 AD"
{retention_instruction}{cq_scene_intel}
Output ONLY a JSON array of scene objects. No preamble."""

    # Build verification context for claim confidence tagging
    verification_ctx = ""
    if verification_data:
        claims = verification_data.get("verified_claims", [])
        if claims:
            disputed = [c for c in claims if c.get("verdict") in ("DISPUTED", "UNVERIFIED")]
            speculative = [c for c in claims if c.get("confidence") == "LOW"]
            if disputed or speculative:
                verification_ctx = "\n\nCLAIM CONFIDENCE GUIDANCE (from fact verification):\n"
                for c in disputed:
                    verification_ctx += f"- CONTESTED: \"{c.get('claim', '')[:100]}\" — {c.get('notes', '')[:80]}\n"
                for c in speculative:
                    if c not in disputed:
                        verification_ctx += f"- SPECULATIVE: \"{c.get('claim', '')[:100]}\" — low confidence\n"
                verification_ctx += "Tag scenes containing these claims with the appropriate claim_confidence.\n"

    prompt = f"""Break this documentary script into exactly {target_scenes} scenes.
Topic: {topic}

Script:
{full_script}
{verification_ctx}
Return a JSON array of exactly {target_scenes} scene objects."""

    result = call_agent(
        "07_scene_breakdown",
        system_prompt=system,
        user_prompt=prompt,
        max_tokens=12000,
        stage_num=7,
        topic=topic,
    )

    # Handle both array and object responses
    if isinstance(result, list):
        scenes = result
    else:
        scenes = result.get("scenes", result.get("scene_breakdown", []))

    total = len(scenes)
    if total != target_scenes:
        print(f"[Scene Breakdown] WARNING: Requested {target_scenes} scenes, got {total} — adjusting")
        # If too many, trim from the middle (preserve hook, ending, and reveal scenes)
        if total > target_scenes + 5:
            # Always keep reveal scenes
            reveal_indices = {i for i, s in enumerate(scenes) if s.get("is_reveal_moment")}
            keep_set = {0, total - 1} | reveal_indices
            # Fill remaining slots with evenly spaced indices
            remaining = target_scenes - len(keep_set)
            if remaining > 0:
                step = max(1, (total - 2) // (remaining + 1))
                for idx in range(1, total - 1, step):
                    if idx not in keep_set:
                        keep_set.add(idx)
                    if len(keep_set) >= target_scenes:
                        break
            # Ensure reveal scenes survive the trim by sorting them to appear first in priority
            keep_sorted = sorted(keep_set)
            # If we still have too many, drop non-reveal non-boundary scenes from the end
            if len(keep_sorted) > target_scenes:
                protected = {0, total - 1} | reveal_indices
                keep_sorted = [i for i in keep_sorted if i in protected] + \
                              [i for i in keep_sorted if i not in protected]
                keep_sorted = sorted(keep_sorted[:target_scenes])
            keep = keep_sorted
            scenes = [scenes[i] for i in keep]
            total = len(scenes)
    # Post-process: inject narrative_position, override act2 mood, ensure all fields present
    for i, scene in enumerate(scenes):
        position = get_narrative_position(i, total)
        scene["narrative_position"] = position

        position_mood = get_position_mood(position, i, total, scene.get("mood", ""))
        if position_mood is not None:
            scene["mood"] = position_mood

        scene.setdefault("year", "")
        scene.setdefault("location", "")
        scene.setdefault("characters_mentioned", [])
        scene.setdefault("is_reveal_moment", False)
        scene.setdefault("show_map", False)
        scene.setdefault("show_timeline", False)
        scene.setdefault("lower_third", None)
        scene.setdefault("key_text", None)
        scene.setdefault("key_text_type", None)
        scene.setdefault("retention_hook", None)
        scene.setdefault("visual_treatment", "standard")
        scene.setdefault("is_breathing_room", False)
        scene.setdefault("claim_confidence", None)

    # Post-process: flag scenes at danger zones that lack retention hooks
    if danger_zones and total > 0:
        for i, scene in enumerate(scenes):
            scene_pct = i / max(total - 1, 1)
            for zone in danger_zones:
                if abs(scene_pct - zone) < (1.0 / total):  # Within one scene of the danger zone
                    if not scene.get("retention_hook"):
                        scene["retention_hook"] = f"[Danger zone at {int(zone*100)}% — needs attention hook]"
                    break

    print(f"[Scene Breakdown] Created {total} scenes")
    return {"scenes": scenes, "total_scenes": total, "topic": topic}
