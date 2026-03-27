import os
import sys
import json
import re
import time
import base64
import shutil
import subprocess
from pathlib import Path

from core.paths import MEDIA_DIR, CHUNKS_DIR
from core.log import get_logger
from pipeline.helpers import clean_script
from pipeline.voice import _get_scene_voice_settings, _get_inter_scene_pause, _generate_silence_file

logger = get_logger(__name__)


def run_audio(script_data, scene_data=None):
    import requests
    try:
        from mutagen.mp3 import MP3
    except ImportError:
        logger.info("[Audio] Installing mutagen...")
        subprocess.run([sys.executable, "-m", "pip", "install", "mutagen"], check=True)
        from mutagen.mp3 import MP3

    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set — cannot generate audio")
    VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
    MAX_CHARS = 500  # smaller chunks = more natural prosody per segment

    # Legacy voice presets (used when no scene data available)
    VOICE_BODY = {"stability": 0.38, "similarity_boost": 0.82,
                  "style": 0.60, "use_speaker_boost": True}
    VOICE_HOOK = {"stability": 0.28, "similarity_boost": 0.85,
                  "style": 0.75, "use_speaker_boost": True}
    VOICE_SPEED = 0.88  # Documentary pace — slower than default 1.0

    # Secondary voice for quoted speech (e.g. historical figures)
    QUOTE_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # "Adam" — authoritative male
    VOICE_QUOTE = {"stability": 0.50, "similarity_boost": 0.75,
                   "style": 0.40, "use_speaker_boost": True}

    # Split text into chunks at sentence boundaries
    def split_chunks(text):
        sentences = text.replace('\n', ' ').split('. ')
        chunks, current = [], ""
        for s in sentences:
            part = s + ". "
            if len(current) + len(part) > MAX_CHARS and current:
                chunks.append(current.strip())
                current = part
            else:
                current += part
        if current.strip() and len(current.strip()) > 2:
            chunks.append(current.strip())
        return chunks

    def detect_quoted_speech(text):
        """Detect if a chunk contains quoted speech (historical figure dialogue)."""
        quotes = re.findall(r'["\u201c]([^"\u201d]{10,200})["\u201d]', text)
        return len(quotes) > 0 and any(
            word in text.lower() for word in
            ['said', 'wrote', 'declared', 'proclaimed', 'whispered', 'shouted',
             'announced', 'commanded', 'stated', 'replied', 'exclaimed']
        )

    def generate_chunk(text, voice_settings=None, voice_id=None, speed=None):
        if voice_settings is None:
            voice_settings = VOICE_BODY
        if voice_id is None:
            voice_id = VOICE_ID
        if speed is None:
            speed = VOICE_SPEED
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
        headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
        payload = {
            "text": text, "model_id": "eleven_v3",
            "voice_settings": voice_settings,
            "speed": speed,
        }
        last_err = None
        for attempt in range(5):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=120)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as ce:
                wait = 30 * (attempt + 1)
                logger.warning(f"  Connection/timeout error, waiting {wait}s...")
                time.sleep(wait)
                last_err = ce
                continue
            if r.status_code == 200:
                return json.loads(r.text, strict=False)
            elif r.status_code == 429:
                wait = 60 * (attempt + 1)
                logger.warning(f"  Rate limited, waiting {wait}s (attempt {attempt+1}/5)...")
                time.sleep(wait)
                last_err = Exception("ElevenLabs rate limit (429)")
            elif r.status_code in (500, 502, 503):
                wait = 30 * (attempt + 1)
                logger.warning(f"  Server error ({r.status_code}), waiting {wait}s (attempt {attempt+1}/5)...")
                time.sleep(wait)
                last_err = Exception(f"ElevenLabs server error ({r.status_code})")
            else:
                raise Exception(f"ElevenLabs {r.status_code}: {r.text[:200]}")
        raise last_err or Exception("Failed after 5 attempts")

    def extract_word_timestamps(data):
        """Extract word-level timestamps from ElevenLabs character alignment."""
        alignment = data.get("alignment") or {}
        if not isinstance(alignment, dict):
            alignment = {}
        chars  = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends   = alignment.get("character_end_times_seconds", [])

        chunk_words = []
        word, word_start, last_end = "", None, 0.0
        for j, ch in enumerate(chars):
            if ch in (" ", "\n"):
                if word and word_start is not None:
                    end_idx = j - 1
                    word_end = ends[end_idx] if 0 <= end_idx < len(ends) else word_start + max(0.15, len(word) * 0.08)
                    chunk_words.append({"word": word, "start": round(word_start, 3),
                        "end": round(word_end, 3)})
                    word, word_start = "", None
            else:
                if word_start is None and j < len(starts):
                    word_start = starts[j]
                word += ch
                if j < len(ends):
                    last_end = ends[j]
        if word and word_start is not None:
            chunk_words.append({"word": word, "start": round(word_start, 3), "end": round(last_end, 3)})
        return chunk_words

    # ── Determine chunking strategy ───────────────────────────────────────────
    # Scene-aware: chunk by scene narration with mood-specific voice settings
    # Legacy: chunk by text splitting with keyword-based prosody detection

    scenes = []
    if scene_data and isinstance(scene_data, dict):
        scenes = scene_data.get("scenes", [])
        # Filter out scenes with empty narration
        scenes = [s for s in scenes if (s.get("narration", "") or "").strip()]

    use_scene_aware = len(scenes) >= 3  # Need meaningful scene data

    if use_scene_aware:
        # ── Resolve scene intent early (before audio) for intent_pace_modifier ──
        try:
            from media.scene_intent import resolve_all_scenes
            scenes = resolve_all_scenes(scenes)
        except Exception as _intent_err:
            logger.warning(f"[Audio] WARNING: Scene intent resolution failed: {_intent_err}")

        # ── SCENE-AWARE PATH ──────────────────────────────────────────────
        # Build chunk list from scene narrations with mood-specific voice settings
        # Each entry: (text, voice_settings, voice_id, speed, scene_idx)
        # Plus optional silence entries: (None, None, None, None, scene_idx, pause_duration)

        total_scenes = len(scenes)
        total_words_est = sum(len((s.get("narration", "") or "").split()) for s in scenes)
        logger.info(f"[Audio] Scene-aware mode: {total_scenes} scenes, ~{total_words_est} words")

        chunk_plan = []  # list of dicts describing each chunk
        for si, scene in enumerate(scenes):
            narration = clean_script(scene.get("narration", "").strip())
            if not narration:
                continue

            vs, vid, spd = _get_scene_voice_settings(scene, si, total_scenes)
            # Apply intent pace modifier from scene_intent resolution
            pace_mod = scene.get("intent_pace_modifier", 1.0)
            final_speed = round(max(0.65, min(1.0, spd * pace_mod)), 2)
            logger.info(f"  [Voice] Scene {si}: raw_spd={spd:.2f} × pace={pace_mod} = {final_speed}")
            vs["speed"] = final_speed
            spd = final_speed
            mood = (scene.get("mood", "") or "dark").lower()
            label = f"scene {si+1}/{total_scenes} [{mood}]"

            # Sub-chunk long narrations
            if len(narration) > MAX_CHARS:
                sub_chunks = split_chunks(narration)
                for sci, sc_text in enumerate(sub_chunks):
                    chunk_plan.append({
                        "type": "audio", "text": sc_text,
                        "vs": vs, "vid": vid, "spd": spd,
                        "scene_idx": si, "label": f"{label} part {sci+1}/{len(sub_chunks)}",
                    })
            else:
                chunk_plan.append({
                    "type": "audio", "text": narration,
                    "vs": vs, "vid": vid, "spd": spd,
                    "scene_idx": si, "label": label,
                })

            # Add inter-scene silence
            next_scene = scenes[si + 1] if si < total_scenes - 1 else None
            pause = _get_inter_scene_pause(scene, next_scene, si, total_scenes)
            if pause > 0:
                chunk_plan.append({
                    "type": "silence", "duration": pause,
                    "scene_idx": si, "label": f"pause {pause:.1f}s after scene {si+1}",
                })

        logger.info(f"[Audio] {len(chunk_plan)} chunks planned "
              f"({sum(1 for c in chunk_plan if c['type'] == 'audio')} audio + "
              f"{sum(1 for c in chunk_plan if c['type'] == 'silence')} pauses)")

    else:
        # ── LEGACY PATH ───────────────────────────────────────────────────
        full_script = clean_script(script_data.get("full_script", ""))
        logger.info(f"[Audio] Legacy mode: {len(full_script)} chars, {len(full_script.split())} words")
        text_chunks = split_chunks(full_script)

        chunk_plan = []
        for i, chunk in enumerate(text_chunks):
            chunk_lower = chunk.lower()
            if i == 0:
                vs, vid, spd = VOICE_HOOK, VOICE_ID, 0.92
            elif detect_quoted_speech(chunk):
                from core.param_overrides import get_override
                vs, vid, spd = VOICE_QUOTE, QUOTE_VOICE_ID, get_override("voice_speed.quote_legacy", 0.85)
            elif any(phrase in chunk_lower for phrase in [
                "the truth", "what really happened", "no one knew", "the real story",
                "but here's what", "what they found", "the evidence shows",
                "it was actually", "in reality",
            ]):
                vs = {"stability": 0.30, "similarity_boost": 0.85, "style": 0.95, "use_speaker_boost": True}
                vid, spd = VOICE_ID, 0.82
            elif any(phrase in chunk_lower for phrase in [
                "but then", "everything changed", "no one expected", "suddenly",
                "without warning", "in secret", "behind closed doors",
            ]):
                vs = {"stability": 0.35, "similarity_boost": 0.82, "style": 0.90, "use_speaker_boost": True}
                vid, spd = VOICE_ID, 0.86
            elif i == len(text_chunks) - 1:
                vs = {"stability": 0.50, "similarity_boost": 0.82, "style": 0.80, "use_speaker_boost": True}
                vid, spd = VOICE_ID, 0.85
            else:
                vs, vid, spd = VOICE_BODY, VOICE_ID, VOICE_SPEED
            chunk_plan.append({
                "type": "audio", "text": chunk,
                "vs": vs, "vid": vid, "spd": spd,
                "scene_idx": None, "label": f"chunk {i+1}/{len(text_chunks)}",
            })

        logger.info(f"[Audio] {len(chunk_plan)} chunks")

    # ── Clear stale chunks from previous runs ─────────────────────────────
    for stale in CHUNKS_DIR.glob("chunk_*.mp3"):
        stale.unlink(missing_ok=True)
    for stale in CHUNKS_DIR.glob("chunk_*_ts.json"):
        stale.unlink(missing_ok=True)
    for stale in CHUNKS_DIR.glob("silence_*.mp3"):
        stale.unlink(missing_ok=True)

    # ── Generate audio for each chunk ─────────────────────────────────────
    all_words = []
    time_offset = 0.0
    concat_files = []  # ordered list of MP3 files for ffmpeg concat
    scene_word_ranges = {}  # scene_idx → (first_word_idx, last_word_idx)

    for i, plan in enumerate(chunk_plan):

        if plan["type"] == "silence":
            # Generate silent audio file
            silence_path = CHUNKS_DIR / f"silence_{i:02d}.mp3"
            pause_dur = plan["duration"]
            try:
                _generate_silence_file(pause_dur, silence_path)
                concat_files.append(silence_path)
                time_offset += pause_dur
                logger.info(f"  [{plan['label']}]")
            except Exception as e:
                logger.warning(f"  [Silence] Failed to generate pause ({e}) — skipping")
            continue

        # Audio chunk
        chunk_path = CHUNKS_DIR / f"chunk_{i:02d}.mp3"
        chunk_ts   = CHUNKS_DIR / f"chunk_{i:02d}_ts.json"

        if chunk_path.exists() and chunk_ts.exists():
            logger.info(f"[Audio] {plan['label']}: cached")
            with open(chunk_ts) as f:
                chunk_words = json.load(f)
        else:
            logger.info(f"[Audio] {plan['label']}: generating ({len(plan['text'])} chars, "
                  f"stab={plan['vs'].get('stability', '?')}, "
                  f"style={plan['vs'].get('style', '?')}, "
                  f"spd={plan['spd']})...")
            data = generate_chunk(plan["text"], voice_settings=plan["vs"],
                                  voice_id=plan["vid"], speed=plan["spd"])
            audio_bytes = base64.b64decode(data.get("audio_base64", ""))
            chunk_path.write_bytes(audio_bytes)

            # Log ElevenLabs cost
            try:
                from core.cost_tracker import get_active_run_id, log_cost
                _rid = get_active_run_id()
                if _rid:
                    log_cost(_rid, "audio", "elevenlabs", len(plan["text"]), "characters")
            except Exception:
                pass

            chunk_words = extract_word_timestamps(data)

            with open(chunk_ts, "w") as f:
                json.dump(chunk_words, f)
            time.sleep(0.5)

        concat_files.append(chunk_path)

        # Use ACTUAL MP3 duration for correct offset
        actual_duration = MP3(chunk_path).info.length
        logger.info(f"  {len(chunk_words)} words, {actual_duration:.2f}s, offset={time_offset:.2f}s")

        # Track scene word boundaries for precise alignment
        si = plan.get("scene_idx")
        first_word_idx = len(all_words)

        for w in chunk_words:
            all_words.append({"word": w["word"],
                "start": round(w["start"] + time_offset, 3),
                "end":   round(w["end"]   + time_offset, 3)})

        last_word_idx = len(all_words) - 1
        if si is not None and chunk_words:
            if si in scene_word_ranges:
                # Extend range for multi-chunk scenes
                scene_word_ranges[si] = (scene_word_ranges[si][0], last_word_idx)
            else:
                scene_word_ranges[si] = (first_word_idx, last_word_idx)

        time_offset += actual_duration

    # ── Concat all audio files with ffmpeg ────────────────────────────────
    raw_audio_path = str(MEDIA_DIR / "narration_raw.mp3")
    audio_path = str(MEDIA_DIR / "narration.mp3")
    if not concat_files:
        raise ValueError("[Audio] No audio chunks generated — script may be empty or TTS failed for all chunks")
    elif len(concat_files) == 1:
        shutil.copy2(concat_files[0], raw_audio_path)
    else:
        concat_list = CHUNKS_DIR / "concat_list.txt"
        with open(concat_list, "w") as f:
            for cf in concat_files:
                f.write(f"file '{cf}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", str(raw_audio_path)],
            check=True, capture_output=True
        )
        concat_list.unlink(missing_ok=True)

    # Audio mastering: loudness normalization to YouTube standard (LUFS -14)
    try:
        logger.info("[Audio] Mastering: loudness normalization (LUFS -14)...")
        subprocess.run(
            ["ffmpeg", "-y", "-i", raw_audio_path,
             "-af", "loudnorm=I=-14:LRA=11:TP=-1.5",
             "-ar", "44100", "-b:a", "192k",
             str(audio_path)],
            check=True, capture_output=True
        )
        Path(raw_audio_path).unlink(missing_ok=True)
        logger.info("[Audio] ✓ Mastered to LUFS -14")
    except Exception as e:
        logger.warning(f"[Audio] Mastering failed ({e}), using raw audio")
        shutil.copy2(raw_audio_path, audio_path)

    # Build scene word ranges list (ordered by scene index)
    scene_boundaries = []
    if scene_word_ranges:
        for si in sorted(scene_word_ranges.keys()):
            scene_boundaries.append(list(scene_word_ranges[si]))

    ts_path = str(MEDIA_DIR / "timestamps.json")
    with open(ts_path, "w") as f:
        ts_data = {"words": all_words}
        if scene_boundaries:
            ts_data["scene_word_ranges"] = scene_boundaries
        json.dump(ts_data, f, indent=2)

    total_narration = sum(len(s.get("narration", "").split()) for s in scenes) if scenes else len(
        clean_script(script_data.get("full_script", "")).split())
    total_duration = (all_words[-1]["end"] if all_words else time_offset) + 1.5  # 1.5s tail buffer

    mode_str = f"scene-aware ({len(scenes)} scenes)" if use_scene_aware else "legacy"
    logger.info(f"[Audio] ✓ {len(all_words)} words, {total_duration:.1f}s ({total_duration/60:.1f}min) [{mode_str}]")
    if scene_boundaries:
        logger.info(f"[Audio] ✓ {len(scene_boundaries)} scene boundaries tracked for precise alignment")

    # WPM validation gate
    if total_duration > 0 and total_narration > 0:
        from core.quality_gates import gate_wpm_range
        from core import pipeline_config
        wpm_ok, wpm_msg = gate_wpm_range(total_narration, total_duration)
        if not wpm_ok:
            if pipeline_config.ENFORCE_WPM_GATE:
                raise RuntimeError(f"WPM gate failed: {wpm_msg}")
            else:
                logger.warning(f"[Audio] WARNING: {wpm_msg} (gate not enforced)")

    return {"audio_path": audio_path, "timestamps_path": ts_path,
            "total_duration_seconds": total_duration, "word_count": total_narration}
