"""Shared path constants for the project."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
MEDIA_DIR = OUTPUT_DIR / "media"
ASSETS_DIR = MEDIA_DIR / "assets"
CHUNKS_DIR = MEDIA_DIR / "chunks"
REMOTION_SRC = BASE_DIR / "remotion" / "src"
REMOTION_PUBLIC = BASE_DIR / "remotion" / "public"

def ensure_dirs():
    for d in [OUTPUT_DIR, MEDIA_DIR, ASSETS_DIR, CHUNKS_DIR, REMOTION_SRC, REMOTION_PUBLIC]:
        d.mkdir(parents=True, exist_ok=True)
