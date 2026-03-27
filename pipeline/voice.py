"""Voice settings and audio helpers — extracted from run_pipeline.py."""
import re
import subprocess


# Original hardcoded mood settings — preserved for zero-change regression test.
# Production code uses _build_mood_settings() which reads from param_overrides.
_ORIGINAL_MOOD_VOICE_SETTINGS = {
    "dark":      {"stability": 0.32, "similarity_boost": 0.82, "style": 0.55, "use_speaker_boost": True, "speed": 0.76},
    "tense":     {"stability": 0.28, "similarity_boost": 0.82, "style": 0.65, "use_speaker_boost": True, "speed": 0.84},
    "dramatic":  {"stability": 0.25, "similarity_boost": 0.85, "style": 0.80, "use_speaker_boost": True, "speed": 0.74},
    "cold":      {"stability": 0.55, "similarity_boost": 0.82, "style": 0.25, "use_speaker_boost": True, "speed": 0.80},
    "reverent":  {"stability": 0.48, "similarity_boost": 0.82, "style": 0.35, "use_speaker_boost": True, "speed": 0.72},
    "wonder":    {"stability": 0.35, "similarity_boost": 0.82, "style": 0.55, "use_speaker_boost": True, "speed": 0.78},
    "warmth":    {"stability": 0.42, "similarity_boost": 0.82, "style": 0.50, "use_speaker_boost": True, "speed": 0.76},
    "absurdity": {"stability": 0.28, "similarity_boost": 0.82, "style": 0.70, "use_speaker_boost": True, "speed": 0.82},
}

# Cache for mood settings (built once per pipeline run)
_cached_mood_settings = None


def _build_mood_settings():
    """Build mood voice settings from param_overrides (falls back to hardcoded defaults)."""
    global _cached_mood_settings
    if _cached_mood_settings is not None:
        return _cached_mood_settings

    try:
        from core.param_overrides import get_override
    except Exception:
        _cached_mood_settings = _ORIGINAL_MOOD_VOICE_SETTINGS
        return _cached_mood_settings

    settings = {}
    for mood, defaults in _ORIGINAL_MOOD_VOICE_SETTINGS.items():
        settings[mood] = {
            "stability": get_override(f"voice.mood.{mood}.stability", defaults["stability"]),
            "similarity_boost": get_override(f"voice.mood.{mood}.similarity_boost", defaults["similarity_boost"]),
            "style": get_override(f"voice.mood.{mood}.style", defaults["style"]),
            "use_speaker_boost": defaults["use_speaker_boost"],  # Not tunable
            "speed": get_override(f"voice.mood.{mood}.speed", defaults["speed"]),
        }
    _cached_mood_settings = settings
    return _cached_mood_settings


def reset_mood_settings_cache():
    """Reset cached mood settings (call when overrides change or at pipeline start)."""
    global _cached_mood_settings
    _cached_mood_settings = None


# Public alias for backward compatibility
MOOD_VOICE_SETTINGS = _ORIGINAL_MOOD_VOICE_SETTINGS


def _get_scene_voice_settings(scene, scene_idx, total_scenes):
    """Determine voice settings based on scene metadata.
    Returns (voice_settings_dict, voice_id, speed)."""
    from core.pipeline_config import NARRATOR_VOICE_ID, QUOTE_VOICE_ID
    VOICE_ID = NARRATOR_VOICE_ID

    mood = (scene.get("mood", "") or "dark").lower()
    is_reveal = scene.get("is_reveal_moment", False)
    is_breathing = scene.get("is_breathing_room", False)
    narrative_pos = scene.get("narrative_position", "")
    narration = scene.get("narration", "")

    # Base settings from mood (reads overrides if set, falls back to hardcoded)
    mood_settings = _build_mood_settings()
    base = mood_settings.get(mood, mood_settings["dark"])
    vs = {
        "stability": base["stability"],
        "similarity_boost": base["similarity_boost"],
        "style": base["style"],
        "use_speaker_boost": base["use_speaker_boost"],
    }
    spd = base["speed"]
    vid = VOICE_ID

    # --- Narrative arc voice modulation ---
    # Uses narrative_position (hook/act1/act2/act3/ending) from scene breakdown
    # agent for story-structure-aware delivery, with scene_idx fallback.
    # Deltas read from overrides (voice.arc.{pos}.{delta}).
    try:
        from core.param_overrides import get_override as _arc_override
    except Exception:
        def _arc_override(key, default):
            return default

    if narrative_pos == "hook" or (not narrative_pos and scene_idx == 0):
        # Hook: more dramatic, faster to grab attention
        vs["stability"] = max(0.20, vs["stability"] + _arc_override("voice.arc.hook.stability_delta", -0.08))
        vs["style"] = min(1.0, vs["style"] + _arc_override("voice.arc.hook.style_delta", 0.15))
        spd = min(0.92, spd + _arc_override("voice.arc.hook.speed_delta", 0.08))
    elif narrative_pos == "act1":
        # Act 1 (setup): measured, building context
        vs["stability"] = min(0.55, vs["stability"] + _arc_override("voice.arc.act1.stability_delta", 0.04))
        spd = max(0.70, spd + _arc_override("voice.arc.act1.speed_delta", -0.02))
    elif narrative_pos == "act2":
        # Act 2 (tension rising): increasing intensity
        vs["stability"] = max(0.25, vs["stability"] + _arc_override("voice.arc.act2.stability_delta", -0.04))
        vs["style"] = min(1.0, vs["style"] + _arc_override("voice.arc.act2.style_delta", 0.08))
        spd = min(0.88, spd + _arc_override("voice.arc.act2.speed_delta", 0.02))
    elif narrative_pos == "act3":
        # Act 3 (climax): peak dramatic delivery, weight
        vs["stability"] = max(0.20, vs["stability"] + _arc_override("voice.arc.act3.stability_delta", -0.06))
        vs["style"] = min(1.0, vs["style"] + _arc_override("voice.arc.act3.style_delta", 0.12))
        vs["similarity_boost"] = min(1.0, vs["similarity_boost"] + 0.05)
        spd = max(0.68, spd + _arc_override("voice.arc.act3.speed_delta", -0.06))
    elif narrative_pos == "ending" or (not narrative_pos and scene_idx == total_scenes - 1):
        # Ending: calmer, slower, hushed reflective
        vs["stability"] = min(0.65, vs["stability"] + _arc_override("voice.arc.ending.stability_delta", 0.12))
        vs["style"] = min(1.0, vs["style"] + _arc_override("voice.arc.ending.style_delta", 0.05))
        spd = max(0.66, spd + _arc_override("voice.arc.ending.speed_delta", -0.08))

    # Reveal moments: maximum expression, devastating slow delivery
    if is_reveal:
        vs["stability"] = max(0.20, vs["stability"] + _arc_override("voice.modifier.reveal.stability_delta", -0.05))
        vs["style"] = min(1.0, vs["style"] + _arc_override("voice.modifier.reveal.style_delta", 0.15))
        spd = max(0.66, spd + _arc_override("voice.modifier.reveal.speed_delta", -0.08))

    # Breathing room: very measured, contemplative
    if is_breathing:
        vs["stability"] = min(0.65, vs["stability"] + _arc_override("voice.modifier.breathing.stability_delta", 0.15))
        vs["style"] = max(0.15, vs["style"] + _arc_override("voice.modifier.breathing.style_delta", -0.20))
        spd = max(0.65, spd + _arc_override("voice.modifier.breathing.speed_delta", -0.12))

    # Quoted speech detection: switch to secondary voice
    # Only override voice ID and speed base — preserve mood-based stability/style
    quotes = re.findall(r'["\u201c]([^"\u201d]{10,200})["\u201d]', narration)
    speech_verbs = ['said', 'wrote', 'declared', 'proclaimed', 'whispered', 'shouted',
                    'announced', 'commanded', 'stated', 'replied', 'exclaimed']
    if quotes and any(w in narration.lower() for w in speech_verbs):
        vid = QUOTE_VOICE_ID
        from core.param_overrides import get_override
        spd = get_override("voice_speed.quote", 0.74)  # position/pace modifiers applied by caller

    # Clamp all values to ElevenLabs ranges
    vs["stability"] = round(max(0.0, min(1.0, vs["stability"])), 2)
    vs["style"] = round(max(0.0, min(1.0, vs["style"])), 2)
    spd = round(max(0.65, min(1.0, spd)), 2)

    return vs, vid, spd


def _get_inter_scene_pause(scene, next_scene, scene_idx, total_scenes):
    """Determine how long to pause between this scene and the next.
    Returns pause duration in seconds (0 = no pause)."""
    from core.param_overrides import get_override

    if scene_idx >= total_scenes - 1:
        return 0  # No pause after last scene

    # Check specific conditions in priority order
    if scene.get("is_reveal_moment"):
        return get_override("pause.reveal", 1.8)

    if scene.get("is_breathing_room"):
        return get_override("pause.breathing", 1.2)

    # Act transition pause
    curr_pos = scene.get("narrative_position", "")
    next_pos = (next_scene or {}).get("narrative_position", "")
    if curr_pos and next_pos and curr_pos != next_pos:
        return get_override("pause.act_transition", 0.9)

    return get_override("pause.default", 0.4)


def _generate_silence_file(duration_sec, output_path):
    """Generate a silent MP3 file of the given duration.
    Tries ffmpeg first, falls back to raw MPEG audio frame construction."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", str(duration_sec), "-c:a", "libmp3lame", "-b:a", "128k",
             str(output_path)],
            check=True, capture_output=True
        )
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Fallback: construct a minimal silent MP3 from raw MPEG frames
    # MPEG1 Layer 3, 128kbps, 44100Hz, mono — each frame is 417 bytes covering 26.12ms
    # Frame header: FF FB 90 00 (sync, MPEG1, Layer3, 128kbps, 44100Hz, mono)
    frame_header = bytes([0xFF, 0xFB, 0x90, 0x00])
    frame_size = 417  # bytes per frame at 128kbps/44100Hz
    frame_duration_ms = 26.12
    n_frames = max(1, int(duration_sec * 1000 / frame_duration_ms))

    # Each frame: header + zero-padded audio data
    silent_frame = frame_header + b'\x00' * (frame_size - len(frame_header))
    with open(output_path, "wb") as f:
        for _ in range(n_frames):
            f.write(silent_frame)
