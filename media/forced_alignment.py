"""
Forced alignment — word-level timestamp extraction from audio + text.

Used as fallback when TTS providers don't supply character-level timestamps
(e.g., Epidemic Sound voiceover). Uses Whisper 'tiny' model for speed.

Falls back to even distribution if Whisper is not installed.
"""

from __future__ import annotations

from pathlib import Path

from core.log import get_logger

logger = get_logger(__name__)


def align_audio_to_text(audio_path: Path, text: str) -> list[dict]:
    """Extract word-level timestamps from audio using Whisper.

    Returns list of {"word": str, "start": float, "end": float}.
    Requires: openai-whisper (pip install openai-whisper).
    """
    try:
        import whisper
    except ImportError:
        logger.warning("[Alignment] Whisper not installed — using even distribution")
        return _even_distribution_from_file(audio_path, text)

    try:
        model = whisper.load_model("tiny")
        result = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",
        )

        timestamps = []
        for segment in result.get("segments", []):
            for word_info in segment.get("words", []):
                timestamps.append({
                    "word": word_info.get("word", "").strip(),
                    "start": round(word_info.get("start", 0.0), 3),
                    "end": round(word_info.get("end", 0.0), 3),
                })

        if timestamps:
            logger.info(f"[Alignment] Extracted {len(timestamps)} word timestamps via Whisper")
            return timestamps

        logger.warning("[Alignment] Whisper returned no word timestamps — using even distribution")
        return _even_distribution_from_file(audio_path, text)

    except Exception as e:
        logger.warning(f"[Alignment] Whisper failed: {e} — using even distribution")
        return _even_distribution_from_file(audio_path, text)


def _even_distribution_from_file(audio_path: Path, text: str) -> list[dict]:
    """Fallback: distribute words evenly across audio duration."""
    duration = 10.0
    try:
        import mutagen
        audio = mutagen.File(str(audio_path))
        if audio and audio.info:
            duration = audio.info.length
    except Exception:
        pass

    words = text.split()
    if not words:
        return []

    per_word = duration / len(words)
    return [
        {
            "word": w,
            "start": round(i * per_word, 3),
            "end": round((i + 1) * per_word, 3),
        }
        for i, w in enumerate(words)
    ]
