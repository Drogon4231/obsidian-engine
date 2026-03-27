"""
Music Track Analyzer — Pre-analyzes all tracks in the music library.

Extracts audio features using librosa:
- Energy curve (RMS per 10-second window, normalized 0-1)
- Tempo (BPM)
- Key and mode (major/minor)
- Sections (intro/build/climax/resolution with timestamps)
- Peak moments (timestamps of energy spikes)

Run manually: python analyze_music.py
Re-run when new tracks are added: python analyze_music.py --force
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MUSIC_DIR = BASE_DIR / "remotion" / "public" / "music"
OUTPUT_FILE = BASE_DIR / "outputs" / "music_analysis.json"

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Major and minor chroma templates for mode detection
MAJOR_TEMPLATE = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]  # W-W-H-W-W-W-H
MINOR_TEMPLATE = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0]  # W-H-W-W-H-W-W


def _detect_key_mode(y, sr):
    """Detect musical key and mode (major/minor) from audio signal."""
    import librosa
    import numpy as np

    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_sum = np.mean(chroma, axis=1)  # 12-element vector

    best_key = 0
    best_mode = "minor"
    best_corr = -1

    for shift in range(12):
        maj = np.roll(MAJOR_TEMPLATE, shift)
        minor = np.roll(MINOR_TEMPLATE, shift)
        corr_maj = float(np.corrcoef(chroma_sum, maj)[0, 1])
        corr_min = float(np.corrcoef(chroma_sum, minor)[0, 1])

        if corr_maj > best_corr:
            best_corr = corr_maj
            best_key = shift
            best_mode = "major"
        if corr_min > best_corr:
            best_corr = corr_min
            best_key = shift
            best_mode = "minor"

    return NOTE_NAMES[best_key], best_mode


def _compute_energy_curve(y, sr, window_sec: float = 10.0) -> list[float]:
    """Compute RMS energy in fixed-size windows, normalized to 0-1."""
    import librosa
    import numpy as np

    rms = librosa.feature.rms(y=y)[0]
    hop_length = 512  # librosa default
    samples_per_window = int(window_sec * sr / hop_length)

    if samples_per_window < 1:
        samples_per_window = 1

    curve = []
    for start in range(0, len(rms), samples_per_window):
        chunk = rms[start : start + samples_per_window]
        if len(chunk) > 0:
            curve.append(float(np.mean(chunk)))

    # Normalize to 0-1
    if curve:
        max_val = max(curve)
        if max_val > 0:
            curve = [v / max_val for v in curve]

    return curve


def _detect_sections(energy_curve: list[float], duration: float, window_sec: float = 10.0) -> list[dict]:
    """Heuristic section detection based on energy curve."""
    if not energy_curve or len(energy_curve) < 4:
        return [{"label": "full", "start": 0.0, "end": duration}]

    n = len(energy_curve)

    # Find the peak window
    peak_idx = energy_curve.index(max(energy_curve))

    # Divide into sections based on energy patterns
    sections = []

    # Intro: from start until energy first rises above 30% of max
    intro_end = 0
    for i, e in enumerate(energy_curve):
        if e > 0.3:
            intro_end = i
            break
    else:
        intro_end = n // 4

    if intro_end > 0:
        sections.append({
            "label": "intro",
            "start": 0.0,
            "end": round(min(intro_end * window_sec, duration), 1),
        })

    # Build: from intro end to peak
    build_start = intro_end
    build_end = max(peak_idx, build_start + 1)
    if build_start < build_end:
        sections.append({
            "label": "build",
            "start": round(build_start * window_sec, 1),
            "end": round(min(build_end * window_sec, duration), 1),
        })

    # Climax: around the peak (peak ± some windows where energy stays high)
    climax_start = build_end
    climax_end = climax_start
    threshold = max(energy_curve) * 0.7
    for i in range(peak_idx, n):
        if energy_curve[i] >= threshold:
            climax_end = i + 1
        else:
            break
    climax_end = max(climax_end, climax_start + 1)

    sections.append({
        "label": "climax",
        "start": round(climax_start * window_sec, 1),
        "end": round(min(climax_end * window_sec, duration), 1),
    })

    # Resolution: from climax end to track end
    if climax_end * window_sec < duration - window_sec:
        sections.append({
            "label": "resolution",
            "start": round(climax_end * window_sec, 1),
            "end": round(duration, 1),
        })

    return sections


def _find_peak_moments(energy_curve: list[float], window_sec: float = 10.0) -> list[float]:
    """Find timestamps where energy exceeds mean + 1.5*std."""
    import numpy as np

    if not energy_curve or len(energy_curve) < 3:
        return []

    arr = np.array(energy_curve)
    threshold = float(np.mean(arr) + 1.5 * np.std(arr))

    peaks = []
    for i, e in enumerate(energy_curve):
        if e >= threshold:
            ts = (i + 0.5) * window_sec  # center of window
            # Cluster nearby peaks (within 15s of last)
            if not peaks or ts - peaks[-1] > 15:
                peaks.append(round(ts, 1))

    return peaks


def analyze_track(filepath: Path) -> dict | None:
    """Analyze a single MP3 track. Returns feature dict or None on error."""
    import librosa

    try:
        y, sr = librosa.load(str(filepath), sr=22050, mono=True)
    except Exception as e:
        print(f"  [SKIP] Could not load {filepath.name}: {e}")
        return None

    duration = float(len(y) / sr)
    if duration < 10:
        print(f"  [SKIP] {filepath.name} too short ({duration:.1f}s)")
        return None

    # Tempo
    try:
        tempo = float(librosa.feature.rhythm.tempo(y=y, sr=sr)[0])
    except Exception:
        tempo = 0.0

    # Key and mode
    try:
        key, mode = _detect_key_mode(y, sr)
    except Exception:
        key, mode = "C", "minor"

    # Energy curve
    energy_curve = _compute_energy_curve(y, sr, window_sec=10.0)

    # Sections
    sections = _detect_sections(energy_curve, duration)

    # Peak moments
    peak_moments = _find_peak_moments(energy_curve)

    return {
        "duration_seconds": round(duration, 1),
        "tempo_bpm": round(tempo, 1),
        "key": key,
        "mode": mode,
        "energy_curve": [round(e, 4) for e in energy_curve],
        "sections": sections,
        "peak_moments": peak_moments,
    }


def run(force: bool = False, single_track: str | None = None):
    """Analyze all tracks (or a single one) and save to JSON."""
    # Load existing analysis
    existing = {}
    if OUTPUT_FILE.exists() and not force:
        try:
            data = json.loads(OUTPUT_FILE.read_text())
            existing = data.get("tracks", {})
        except Exception:
            pass

    # Collect tracks to analyze
    if single_track:
        tracks = [MUSIC_DIR / single_track]
        if not tracks[0].exists():
            print(f"[Analyze] Track not found: {single_track}")
            return
    else:
        tracks = sorted(MUSIC_DIR.glob("*.mp3"))

    if not tracks:
        print("[Analyze] No MP3 files found in", MUSIC_DIR)
        return

    print(f"[Analyze] Found {len(tracks)} tracks in library")

    analyzed = 0
    skipped = 0
    errors = 0

    for i, track in enumerate(tracks, 1):
        filename = track.name

        # Skip if already analyzed (unless forced)
        if filename in existing and not force:
            # Check if file size changed (new version)
            current_size = track.stat().st_size
            if existing[filename].get("_file_size") == current_size:
                skipped += 1
                continue

        print(f"[Analyze] {i}/{len(tracks)}: {filename}...", end=" ", flush=True)
        t0 = time.time()

        result = analyze_track(track)
        if result:
            result["_file_size"] = track.stat().st_size
            existing[filename] = result
            elapsed = time.time() - t0
            print(f"OK ({result['duration_seconds']:.0f}s, {result['tempo_bpm']:.0f} BPM, "
                  f"{result['key']} {result['mode']}, {elapsed:.1f}s)")
            analyzed += 1
        else:
            errors += 1

    # Save
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "track_count": len(existing),
        "tracks": existing,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))

    # Persist to Supabase so Railway can use it
    try:
        from core.utils import persist_json_to_supabase
        persist_json_to_supabase(OUTPUT_FILE, output)
        print("[Analyze] Persisted to Supabase")
    except Exception as e:
        print(f"[Analyze] Supabase persist warning: {e}")

    print(f"\n[Analyze] Done: {analyzed} analyzed, {skipped} cached, {errors} errors")
    print(f"[Analyze] Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze music tracks for smart selection")
    parser.add_argument("--force", action="store_true", help="Re-analyze all tracks (ignore cache)")
    parser.add_argument("--track", metavar="FILENAME", help="Analyze a single track by filename")
    args = parser.parse_args()

    try:
        import librosa  # noqa: F401
    except ImportError:
        print("[Analyze] Installing librosa...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "librosa", "soundfile", "numpy"], check=True)

    run(force=args.force, single_track=args.track)
