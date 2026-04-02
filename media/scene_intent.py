"""
Scene Intent Resolution System.

Unifies mood + narrative_function + act_position into concrete temporal
parameters for the Remotion renderer. All rendering decisions are resolved
in Python — no intent strings cross the Python→JSON→Remotion boundary.

Output per scene:
  - transition_type:   "normal" | "act" | "reveal"
  - motion_style:      KenBurns seed hint (0-15)
  - music_volume_base: 0.0-1.0
  - pace_modifier:     multiplier on base WPM (0.8 = slower, 1.2 = faster)
  - caption_style:     "standard" | "emphasis" | "whisper"
  - scene_energy:      0.0-1.0 (drives composite intensity)
"""

from __future__ import annotations


# ── Emotional Blueprint ──────────────────────────────────────────────────────
# Defines the target emotional experience by video percentage.
# Each phase maps to concrete parameter targets that guide tuning of
# _FUNCTION_MODIFIERS and _POSITION_VOLUME.
# Format: phase_name → (start_pct, end_pct)
EMOTIONAL_BLUEPRINT = {
    "intrigue":     (0.00, 0.05),   # Hook: curiosity gap, urgent
    "context":      (0.05, 0.25),   # Measured setup, building world
    "rising":       (0.25, 0.45),   # Tension building, stakes rising
    "first_reveal": (0.45, 0.55),   # Slow down, let it land
    "escalation":   (0.55, 0.70),   # Intensify, faster cuts
    "climax":       (0.70, 0.82),   # Peak intensity → devastation
    "silence":      (0.82, 0.88),   # Near-zero music, hushed voice
    "resolution":   (0.88, 1.00),   # Music swell, reflective close
}

# Blueprint phase → target parameters (reference table for tuning)
BLUEPRINT_TARGETS = {
    "intrigue":     {"wpm": (145, 155), "music_mult": 0.40, "energy": 0.8, "transition": "normal"},
    "context":      {"wpm": (120, 130), "music_mult": 0.50, "energy": 0.4, "transition": "normal"},
    "rising":       {"wpm": (130, 140), "music_mult": 0.65, "energy": 0.6, "transition": "normal"},
    "first_reveal": {"wpm": (95, 110),  "music_mult": 0.30, "energy": 0.7, "transition": "act"},
    "escalation":   {"wpm": (135, 145), "music_mult": 0.80, "energy": 0.9, "transition": "normal"},
    "climax":       {"wpm": (100, 115), "music_mult": 0.90, "energy": 1.0, "transition": "reveal"},
    "silence":      {"wpm": (80, 95),   "music_mult": 0.05, "energy": 0.3, "transition": "silence"},
    "resolution":   {"wpm": (105, 120), "music_mult": 1.15, "energy": 0.5, "transition": "normal"},
}


# ── Mood → Base Energy ────────────────────────────────────────────────────────
# How much visual/audio intensity this mood carries (0-1 scale)
_MOOD_ENERGY = {
    "dark":      0.6,
    "tense":     0.75,
    "dramatic":  0.9,
    "cold":      0.4,
    "reverent":  0.3,
    "wonder":    0.5,
    "warmth":    0.35,
    "absurdity": 0.55,
}

# ── Narrative Function → Modifiers ────────────────────────────────────────────
# Each function adjusts the base energy and sets rendering hints
_FUNCTION_MODIFIERS = {
    "cold_open": {
        "energy_offset":    +0.10,
        "pace_modifier":    0.95,     # measured, establishing dread
        "transition_type":  "normal",
        "caption_style":    "whisper",
        "motion_hint":      "slow_pan",
        "speech_intensity":  0.6,     # restrained, ominous
        "silence_eligible":  False,
    },
    "hook": {
        "energy_offset":    +0.15,
        "pace_modifier":    1.05,     # slightly faster, punchy
        "transition_type":  "normal",
        "caption_style":    "emphasis",
        "motion_hint":      "zoom_in",
        "speech_intensity":  0.8,     # urgent, commanding
        "silence_eligible":  False,
    },
    "setup": {
        "energy_offset":    -0.05,
        "pace_modifier":    0.95,     # steady, building world
        "transition_type":  "normal",
        "caption_style":    "standard",
        "motion_hint":      "slow_pan",
        "speech_intensity":  0.5,     # calm, authoritative
        "silence_eligible":  False,
    },
    "exposition": {
        "energy_offset":    -0.10,
        "pace_modifier":    0.95,     # measured, informational
        "transition_type":  "normal",
        "caption_style":    "standard",
        "motion_hint":      "slow_pan",
        "speech_intensity":  0.5,
        "silence_eligible":  False,
    },
    "rising_action": {
        "energy_offset":    +0.10,
        "pace_modifier":    1.02,     # building momentum
        "transition_type":  "normal",
        "caption_style":    "standard",
        "motion_hint":      "zoom_in",
        "speech_intensity":  0.65,
        "silence_eligible":  False,
    },
    "complication": {
        "energy_offset":    +0.12,
        "pace_modifier":    1.00,     # controlled tension
        "transition_type":  "normal",
        "caption_style":    "standard",
        "motion_hint":      "slow_pan",
        "speech_intensity":  0.7,
        "silence_eligible":  False,
    },
    "question": {
        "energy_offset":    +0.05,
        "pace_modifier":    0.90,     # slower, let question land
        "transition_type":  "normal",
        "caption_style":    "emphasis",
        "motion_hint":      "zoom_in",
        "speech_intensity":  0.6,
        "silence_eligible":  False,
    },
    "answer": {
        "energy_offset":    +0.00,
        "pace_modifier":    1.00,
        "transition_type":  "normal",
        "caption_style":    "standard",
        "motion_hint":      "slow_pan",
        "speech_intensity":  0.55,
        "silence_eligible":  False,
    },
    "escalation": {
        "energy_offset":    +0.15,
        "pace_modifier":    1.05,
        "transition_type":  "normal",
        "caption_style":    "standard",
        "motion_hint":      "zoom_in",
        "speech_intensity":  0.75,
        "silence_eligible":  False,
    },
    "climax": {
        "energy_offset":    +0.25,
        "pace_modifier":    0.88,     # slow, devastating delivery
        "transition_type":  "reveal",
        "caption_style":    "emphasis",
        "motion_hint":      "zoom_in",
        "speech_intensity":  0.95,    # maximum intensity
        "silence_eligible":  False,   # climax must never be silent
    },
    "twist": {
        "energy_offset":    +0.20,
        "pace_modifier":    0.85,     # slow for the turn
        "transition_type":  "reveal",
        "caption_style":    "emphasis",
        "motion_hint":      "zoom_in",
        "speech_intensity":  0.85,
        "silence_eligible":  False,   # twist must never be silent
    },
    "reveal": {
        "energy_offset":    +0.20,
        "pace_modifier":    0.90,     # slow for impact
        "transition_type":  "reveal",
        "caption_style":    "emphasis",
        "motion_hint":      "zoom_in",
        "speech_intensity":  0.9,
        "silence_eligible":  False,   # reveal must never be silent
    },
    "falling_action": {
        "energy_offset":    -0.10,
        "pace_modifier":    0.92,     # decelerating
        "transition_type":  "normal",
        "caption_style":    "standard",
        "motion_hint":      "zoom_out",
        "speech_intensity":  0.5,
        "silence_eligible":  False,
    },
    "breathing_room": {
        "energy_offset":    -0.25,
        "pace_modifier":    0.85,     # slow, contemplative
        "transition_type":  "act",
        "caption_style":    "whisper",
        "motion_hint":      "breathe",
        "speech_intensity":  0.3,     # near-whisper
        "silence_eligible":  True,
    },
    "reflection": {
        "energy_offset":    -0.15,
        "pace_modifier":    0.88,     # thoughtful, weighted
        "transition_type":  "act",
        "caption_style":    "whisper",
        "motion_hint":      "breathe",
        "speech_intensity":  0.4,
        "silence_eligible":  True,
    },
    "resolution": {
        "energy_offset":    -0.05,
        "pace_modifier":    0.92,
        "transition_type":  "normal",
        "caption_style":    "standard",
        "motion_hint":      "zoom_out",
        "speech_intensity":  0.5,
        "silence_eligible":  False,
    },
    "conclusion": {
        "energy_offset":    -0.05,
        "pace_modifier":    0.92,     # measured, reflective
        "transition_type":  "act",
        "caption_style":    "standard",
        "motion_hint":      "zoom_out",
        "speech_intensity":  0.5,
        "silence_eligible":  False,
    },
    "coda": {
        "energy_offset":    -0.20,
        "pace_modifier":    0.85,     # final thought, lingering
        "transition_type":  "act",
        "caption_style":    "whisper",
        "motion_hint":      "breathe",
        "speech_intensity":  0.35,
        "silence_eligible":  True,
    },
    "callback": {
        "energy_offset":    +0.10,
        "pace_modifier":    1.00,
        "transition_type":  "normal",
        "caption_style":    "emphasis",
        "motion_hint":      "slow_pan",
        "speech_intensity":  0.65,
        "silence_eligible":  False,
    },
    "silence": {
        "energy_offset":    -0.35,
        "pace_modifier":    0.80,
        "transition_type":  "silence",
        "caption_style":    "whisper",
        "motion_hint":      "breathe",
        "speech_intensity":  0.2,     # barely audible
        "silence_eligible":  True,
    },
}

# ── Motion Hint → KenBurns Seed Range ────────────────────────────────────────
# Maps abstract motion hints to seed ranges that correspond to KenBurns patterns
_MOTION_SEED_RANGES = {
    "zoom_in":   (0, 3),     # patterns 0-3: zoom-in variants
    "zoom_out":  (4, 7),     # patterns 4-7: zoom-out variants
    "slow_pan":  (8, 13),    # patterns 8-13: diagonal drift + horizontal pan
    "breathe":   (14, 15),   # patterns 14-15: breathe/intimate
}

# ── Act Position → Volume Multiplier ─────────────────────────────────────────
_POSITION_VOLUME = {
    "hook":   0.45,   # music slightly lower — voice must dominate
    "act1":   0.50,
    "act2":   0.50,
    "act3":   0.45,   # act3 often has revelations — lower music
    "ending": 0.55,   # music swells for emotional close
}


def resolve_scene_intent(
    scene: dict,
    scene_index: int,
    total_scenes: int,
) -> dict:
    """
    Resolve a scene's mood + narrative_function + position into concrete
    rendering parameters.

    Args:
        scene: Scene dict with at least 'mood' and 'narrative_function'
        scene_index: 0-based index
        total_scenes: Total number of scenes in the video

    Returns:
        Dict of resolved intent parameters to merge into the scene.
    """
    mood = scene.get("mood", "dark")
    narrative_function = scene.get("narrative_function", "exposition")
    # 1. Compute energy
    base_energy = _MOOD_ENERGY.get(mood, 0.5)
    modifiers = _FUNCTION_MODIFIERS.get(narrative_function, _FUNCTION_MODIFIERS["exposition"])
    energy = max(0.0, min(1.0, base_energy + modifiers["energy_offset"]))

    # 2. Resolve transition type
    # Reveal moments always get reveal transition regardless of function
    if scene.get("is_reveal_moment"):
        transition_type = "reveal"
    elif scene.get("is_breathing_room"):
        transition_type = "act"
    else:
        transition_type = modifiers["transition_type"]

    # Act boundaries also get act transitions (first scene of each act)
    if scene_index > 0 and _is_act_boundary(scene_index, total_scenes):
        transition_type = "act"

    # Blueprint silence window override (82-88% of video)
    if total_scenes > 1:
        pct = scene_index / max(total_scenes - 1, 1)
        if 0.82 <= pct <= 0.88:
            transition_type = "silence"

    # 3. Resolve motion seed
    motion_hint = modifiers["motion_hint"]
    seed_lo, seed_hi = _MOTION_SEED_RANGES.get(motion_hint, (0, 15))
    # Use scene_index to pick a specific seed within the range
    motion_seed = seed_lo + (scene_index % (seed_hi - seed_lo + 1))

    # 4. Resolve music volume — blueprint-driven for dynamic range
    pct_pos = scene_index / max(total_scenes - 1, 1) if total_scenes > 1 else 0.0
    base_volume = _blueprint_volume(pct_pos)
    # Breathing room scenes get quieter music
    if narrative_function == "breathing_room":
        base_volume *= 0.7
    # Reveal scenes get brief volume dip for impact
    elif narrative_function == "reveal":
        base_volume *= 0.8

    # 5. Pace modifier
    pace_modifier = modifiers["pace_modifier"]

    # 6. Caption style
    caption_style = modifiers["caption_style"]

    # 7. Speech intensity — how intensely the narrator delivers this scene
    speech_intensity = modifiers.get("speech_intensity", 0.5)

    # 8. Silence beat — coordinated audio+visual silence moment
    # Fires when: function is silence-eligible AND transition is silence/act
    # OR the blueprint silence window is active (82-88%)
    silence_eligible = modifiers.get("silence_eligible", False)
    silence_beat = (
        (silence_eligible and transition_type in ("silence", "act"))
        or transition_type == "silence"
    )

    return {
        "intent_transition_type":   transition_type,
        "intent_motion_seed":       motion_seed,
        "intent_music_volume_base": round(base_volume, 3),
        "intent_pace_modifier":     pace_modifier,
        "intent_caption_style":     caption_style,
        "intent_scene_energy":      round(energy, 3),
        "intent_speech_intensity":  round(speech_intensity, 3),
        "intent_silence_beat":      silence_beat,
    }


def resolve_all_scenes(scenes: list[dict]) -> list[dict]:
    """
    Resolve intent for every scene in the video. Returns a NEW list
    of scene dicts with intent fields merged in. Does NOT mutate input.
    """
    total = len(scenes)
    resolved = []
    for i, scene in enumerate(scenes):
        intent = resolve_scene_intent(scene, i, total)
        merged = {**scene, **intent}
        resolved.append(merged)

    # ── KenBurns alternation: no 3+ consecutive scenes in same seed range ──
    for i in range(2, len(resolved)):
        s0 = resolved[i - 2]["intent_motion_seed"]
        s1 = resolved[i - 1]["intent_motion_seed"]
        s2 = resolved[i]["intent_motion_seed"]
        # Check if all three fall in the same seed range
        def _seed_range(seed):
            for rng_name, (lo, hi) in _MOTION_SEED_RANGES.items():
                if lo <= seed <= hi:
                    return rng_name
            return "unknown"
        if _seed_range(s0) == _seed_range(s1) == _seed_range(s2):
            # Force scene i to a different range
            current_range = _seed_range(s2)
            for rng_name, (lo, hi) in _MOTION_SEED_RANGES.items():
                if rng_name != current_range:
                    resolved[i]["intent_motion_seed"] = lo + (i % (hi - lo + 1))
                    break

    # Log energy arc for manual review
    energies = [s["intent_scene_energy"] for s in resolved]
    print(f"  [Intent] Energy arc: {[round(e, 2) for e in energies]}")

    return resolved


# ── Internal Helpers ─────────────────────────────────────────────────────────

def _blueprint_volume(pct: float) -> float:
    """Map a scene's percentage position to music volume using BLUEPRINT_TARGETS.

    Walks EMOTIONAL_BLUEPRINT phases to find which phase this scene falls in,
    then returns the corresponding music_mult from BLUEPRINT_TARGETS.
    Falls back to 0.50 if no phase matches (should not happen).
    """
    for phase_name, (start_pct, end_pct) in EMOTIONAL_BLUEPRINT.items():
        if start_pct <= pct < end_pct:
            return BLUEPRINT_TARGETS[phase_name]["music_mult"]
    # pct == 1.0 falls off the last phase boundary; use resolution
    return BLUEPRINT_TARGETS["resolution"]["music_mult"]


def _infer_position(scene_index: int, total_scenes: int) -> str:
    """Infer narrative position from scene index when not explicitly set."""
    if total_scenes <= 1:
        return "hook"
    pct = scene_index / max(total_scenes - 1, 1)
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


def _is_act_boundary(scene_index: int, total_scenes: int) -> bool:
    """Check if this scene is the first scene of a new act."""
    if total_scenes < 4:
        return False
    # Act boundary positions (same ratios as _infer_position)
    boundaries = [
        int(total_scenes * 0.07),   # start of act1
        int(total_scenes * 0.28),   # start of act2
        int(total_scenes * 0.67),   # start of act3
        int(total_scenes * 0.90),   # start of ending
    ]
    return scene_index in boundaries
