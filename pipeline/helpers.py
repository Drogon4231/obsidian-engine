"""Pipeline helper functions — extracted from run_pipeline.py."""
import re
import shutil
from pathlib import Path

from core.paths import MEDIA_DIR
from core.log import get_logger

logger = get_logger(__name__)


def download_file(url: str, dest: str, timeout: int = 60) -> str:
    """Download a URL to a local file with timeout. Returns dest path."""
    import requests
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest


# ── Hook intrigue scoring ─────────────────────────────────────────────────────
def score_hook(script_text):
    """Evaluate the hook (first 2-3 sentences) for curiosity gap and stakes."""
    try:
        from clients.claude_client import call_claude, HAIKU
        sentences = [s.strip() for s in re.split(r'[.!?]+', script_text) if s.strip()]
        hook_text = '. '.join(sentences[:3]) + '.'
        result = call_claude(
            system_prompt="Rate this documentary video hook on 3 criteria. Reply ONLY as JSON: {\"curiosity_gap\": N, \"stakes\": N, \"keep_watching\": N} where N is 1-10.",
            user_prompt=f"Hook text:\n\"{hook_text}\"",
            model=HAIKU,
            expect_json=True,
            max_tokens=100,
        )
        scores = {
            "curiosity_gap": result.get("curiosity_gap", 5),
            "stakes": result.get("stakes", 5),
            "keep_watching": result.get("keep_watching", 5),
        }
        avg = sum(scores.values()) / 3
        if avg < 6:
            logger.warning(f"[Quality] \u26a0\ufe0f Hook scored {avg:.1f}/10 — consider strengthening")
            logger.warning(f"  Curiosity gap: {scores['curiosity_gap']}/10, Stakes: {scores['stakes']}/10, Keep watching: {scores['keep_watching']}/10")
        else:
            logger.info(f"[Quality] Hook scored {avg:.1f}/10 \u2713")
        return scores
    except Exception as e:
        logger.warning(f"[Quality] Hook scoring failed (non-fatal): {e}")
        return {}


# ── Script cleaner ────────────────────────────────────────────────────────────
def clean_script(text):
    """Remove any meta/pipeline text that leaked into the script."""
    text = re.sub(r'(?i)^(verification|approved|corrections|fact.check|review|status|agent\s+\d|pipeline)[^\n]*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?i)(APPROVED_WITH_CORRECTIONS|APPROVED|REJECTED)[^\n]*\n?', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Topic sanitizer ──────────────────────────────────────────────────────────
def _sanitize_topic(topic: str) -> str:
    """Sanitize topic string to prevent prompt injection and invalid characters."""
    # Strip control characters
    topic = re.sub(r'[\x00-\x1f\x7f]', '', topic)
    # Collapse any injected prompt markers
    topic = re.sub(r'(?i)(system|assistant|user)\s*:', '', topic)
    # Strip XML-like tags that could confuse Claude
    topic = re.sub(r'<[^>]+>', '', topic)
    # Limit length
    topic = topic.strip()[:200]
    return topic


# ── Post-upload cleanup ──────────────────────────────────────────────────────
def _cleanup_after_upload(state: dict, state_path: Path):
    """
    Remove intermediate media files after a successful YouTube upload.
    Keeps: state JSON (feeds optimizer trends), thumbnail, narration.mp3.
    Removes: frames/, chunks/, raw_video.mp4, image assets, concat files.
    """
    media_dir = MEDIA_DIR
    freed = 0

    if media_dir.exists():
        # Disposable subdirs: frames, chunks, visuals (intermediate render artifacts)
        for subdir in ("frames", "chunks", "visuals"):
            target = media_dir / subdir
            if target.is_dir():
                size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
                shutil.rmtree(target, ignore_errors=True)
                target.mkdir(exist_ok=True)  # recreate empty dir for next run
                freed += size

        # Disposable files in media root
        disposable_patterns = ["raw_video.mp4", "concat_list.txt", "captions.ass",
                               "captions.srt", "background_music.mp3"]
        for pattern in disposable_patterns:
            for f in media_dir.glob(pattern):
                freed += f.stat().st_size
                f.unlink(missing_ok=True)

        # Large asset images (already baked into rendered video)
        assets_dir = media_dir / "assets"
        if assets_dir.is_dir():
            size = sum(f.stat().st_size for f in assets_dir.rglob("*") if f.is_file())
            shutil.rmtree(assets_dir, ignore_errors=True)
            assets_dir.mkdir(exist_ok=True)
            freed += size

    # NOTE: State files are NOT deleted — they feed the optimizer's cross-run
    # trend analysis. Each is only ~50-100 KB so storage impact is negligible.

    if freed > 0:
        freed_mb = freed / (1024 * 1024)
        logger.info(f"[Cleanup] Freed {freed_mb:.0f} MB of intermediate media files")
    else:
        logger.info("[Cleanup] No intermediate files to clean up")
