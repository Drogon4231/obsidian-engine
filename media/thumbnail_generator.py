#!/usr/bin/env python3
"""Cinematic thumbnail generator for The Obsidian Archive."""
import sys
import json
import glob
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent

def generate(title, ai_image_path, output_path):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
        from PIL import Image, ImageDraw, ImageFont

    W, H = 1280, 720
    img = Image.open(ai_image_path).convert("RGB").resize((W, H), Image.LANCZOS)

    # Dark gradient overlay
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    od = ImageDraw.Draw(overlay)
    for i in range(200):
        od.rectangle([0, i, W, i+1], fill=(0,0,0,int(160*(1-i/200))))
    for i in range(340):
        od.rectangle([0, H-340+i, W, H-340+i+1], fill=(0,0,0,int(230*(i/340))))

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)

    # Load fonts — use Pillow's built-in scalable font
    try:
        font_title = ImageFont.load_default(size=56)
        font_channel = ImageFont.load_default(size=24)
    except TypeError:
        # Pillow < 10.1 doesn't support size param
        font_title = ImageFont.load_default()
        font_channel = ImageFont.load_default()

    # Gold line
    gold = (180, 140, 80)
    draw.rectangle([80, H-250, W-80, H-247], fill=gold)
    draw.rectangle([80, H-244, W-80, H-243], fill=(120, 90, 40))

    # Channel name top
    draw.text((82, 52), "THE OBSIDIAN ARCHIVE", fill=(0,0,0,180), font=font_channel)
    draw.text((80, 50), "THE OBSIDIAN ARCHIVE", fill=gold, font=font_channel)

    # Split title into lines
    words = title.upper().split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if len(test) > 26 and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    # Draw title bottom-up
    y = H - 90
    for line in reversed(lines):
        draw.text((83, y+3), line, fill=(0,0,0,200), font=font_title)
        draw.text((80, y), line, fill=(255, 248, 225), font=font_title)
        y -= 62

    # Decorative dots
    for i, x in enumerate([80, 93, 106]):
        draw.ellipse([x-4, H-228, x+4, H-220], fill=gold)

    img.convert("RGB").save(output_path, "JPEG", quality=95)
    print(f"[Thumbnail] ✓ {Path(output_path).name}")
    return output_path

def run(seo_data, manifest):
    title  = seo_data.get("recommended_title", "The Obsidian Archive")
    scenes = manifest.get("scenes", [])
    ai_image = None
    for scene in scenes:
        src = scene.get("ai_image")
        if src:
            for candidate in [
                Path(src),
                _BASE / "outputs" / "media" / "assets" / Path(src).name,
            ]:
                if candidate.exists():
                    ai_image = str(candidate)
                    break
        if ai_image:
            break

    if not ai_image:
        print("[Thumbnail] No AI image found, skipping")
        return None

    output = _BASE / "outputs" / "media" / "thumbnail.jpg"
    return generate(title, ai_image, str(output))

if __name__ == "__main__":
    state_files = sorted(glob.glob("outputs/*_state.json"))
    manifest_path = Path("outputs/media/media_manifest.json")
    if not state_files or not manifest_path.exists():
        print("Run pipeline first")
        sys.exit(1)
    with open(state_files[-1]) as f:
        state = json.load(f)
    with open(manifest_path) as f:
        manifest = json.load(f)
    run(state.get("stage_6", {}), manifest)
