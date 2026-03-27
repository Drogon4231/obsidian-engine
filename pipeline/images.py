import threading
import base64
import re
import json
import time
import shutil
import os
import sys
import subprocess
import random
from pathlib import Path
from datetime import datetime

from core.paths import ASSETS_DIR, OUTPUT_DIR
from core.log import get_logger
from core.shutdown import _shutdown_event

logger = get_logger(__name__)


def _fal_subscribe_with_retry(model: str, arguments: dict, label: str = "fal.ai",
                               max_attempts: int = 5, backoff_base: int = 2):
    """Call fal_client.subscribe with exponential-backoff retries.

    Retries on connection errors, timeouts, and rate limits (up to max_attempts).
    """
    import fal_client

    for attempt in range(1, max_attempts + 1):
        try:
            return fal_client.subscribe(model, arguments=arguments)
        except Exception as e:
            err_str = str(e).lower()
            is_retryable = any(kw in err_str for kw in [
                "timeout", "timed out", "connection", "rate limit", "429",
                "502", "503", "504", "overloaded", "temporarily",
            ])
            if attempt == max_attempts or not is_retryable:
                logger.error(f"  [{label}] Failed after {attempt} attempt(s): {e}")
                raise
            _rng = random.Random()
            wait = (backoff_base ** attempt) + _rng.uniform(0, backoff_base ** attempt * 0.5)
            logger.warning(f"  [{label}] Attempt {attempt}/{max_attempts} failed ({type(e).__name__}: {e}), retrying in {wait:.1f}s...")
            time.sleep(wait)


def _score_image(image_path) -> int:
    """Score image quality 1-10 using Claude Haiku vision. Returns 0 on failure."""
    try:
        from clients.claude_client import client as _vc, track_usage
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        resp = _vc.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=50,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text": "Rate 1-10 for quality as documentary illustration. Reply ONLY the number."}
            ]}],
        )
        try:
            track_usage("claude-haiku-4-5-20251001", resp.usage)
        except Exception:
            pass
        match = re.search(r'\d+', resp.content[0].text)
        return int(match.group()) if match else 0
    except Exception:
        return 0


def _generate_single_image(idx, scene, total_scenes, assets_dir, image_model,
                           mood_light, style_recraft, style_flux,
                           character_portraits=None):
    """Generate + quality-score one scene image. Thread-safe: unique file path per scene.

    Returns (idx, updated_scene, success).
    """
    import copy
    from pipeline.helpers import download_file
    _thread = threading.current_thread().name
    scene = copy.deepcopy(scene)
    img_path = assets_dir / f"scene_{idx:03d}_ai.jpg"

    # Adaptive quality thresholds based on scene importance
    position = scene.get("narrative_position", "")
    is_reveal = scene.get("is_reveal_moment", False)
    is_breathing = scene.get("is_breathing_room", False)

    if position == "hook" or is_reveal:
        IMAGE_QUALITY_THRESHOLD, IMAGE_MAX_RETRIES = 8, 5
    elif position in ("act3", "ending"):
        IMAGE_QUALITY_THRESHOLD, IMAGE_MAX_RETRIES = 8, 4
    elif is_breathing:
        IMAGE_QUALITY_THRESHOLD, IMAGE_MAX_RETRIES = 6, 2
    else:
        IMAGE_QUALITY_THRESHOLD, IMAGE_MAX_RETRIES = 7, 3

    try:
        narration = scene.get("narration", "")
        visual_desc = scene.get("visual_description", "")
        first = narration.split(".")[0].strip()[:200]
        mood = scene.get("mood", "dark")
        year = scene.get("year", "")
        location = scene.get("location", "")
        subject = visual_desc if visual_desc else first

        era_context = ""
        if year:
            era_context += f"set in {year}, "
        if location:
            era_context += f"in {location}, "

        characters = scene.get("characters_mentioned", [])
        char_desc = ""
        if characters and not visual_desc:
            char_desc = f"depicting {', '.join(characters[:2])}, period-accurate clothing and appearance, "

        position = scene.get("narrative_position", "")
        composition_hint = ""
        if position == "hook":
            composition_hint = "extreme close-up on a face frozen in a pivotal moment, "
        elif position == "act3" or scene.get("is_reveal_moment"):
            composition_hint = "wide dramatic reveal shot, figures dwarfed by grand architecture or landscape, "
        elif position == "ending":
            composition_hint = "solitary figure silhouetted against vast empty space, melancholic distance, "

        cur_style = style_recraft if image_model == "recraft" else style_flux
        prompt = (f"{subject}, {era_context}{char_desc}{composition_hint}"
                  f"{mood_light.get(mood, 'deep shadows')}, {cur_style}")

        logger.info(f"  [{_thread}] Scene {idx+1}/{total_scenes} ({mood})...")

        best_score = 0
        best_path = None
        for attempt in range(IMAGE_MAX_RETRIES):
            if _shutdown_event.is_set():
                scene["ai_image"] = None
                return (idx, scene, False)

            attempt_path = assets_dir / f"scene_{idx:03d}_ai_attempt{attempt}.jpg" if attempt > 0 else img_path

            # Check for character portrait → Kontext Pro routing
            _used_kontext = False
            characters = scene.get("characters_mentioned", [])
            if character_portraits and characters:
                for c in characters:
                    if c in character_portraits:
                        portrait_path = character_portraits[c]
                        if Path(portrait_path).exists():
                            try:
                                with open(portrait_path, "rb") as _pf:
                                    ref_b64 = base64.b64encode(_pf.read()).decode()
                                kontext_prompt = (
                                    f"Transform this into: {subject}, {era_context}{composition_hint}"
                                    f"{mood_light.get(mood, 'deep shadows')}. "
                                    f"Keep the character's face, build, and clothing identical. {cur_style}"
                                )
                                result = _fal_subscribe_with_retry("fal-ai/flux-pro/kontext", {
                                    "image": f"data:image/jpeg;base64,{ref_b64}",
                                    "prompt": kontext_prompt,
                                    "aspect_ratio": "16:9",
                                    "num_images": 1,
                                    "safety_tolerance": "2",
                                }, label=f"{_thread} scene {idx+1} kontext")
                                _used_kontext = True
                            except Exception as kontext_err:
                                logger.warning(f"  [{_thread}] Kontext Pro failed, falling back: {kontext_err}")
                                _used_kontext = False
                        break

            if not _used_kontext:
                if image_model == "recraft":
                    result = _fal_subscribe_with_retry("fal-ai/recraft/v3/text-to-image", {
                        "prompt": prompt,
                        "image_size": {"width": 2560, "height": 1440},
                        "num_images": 1,
                        "style": "digital_illustration",
                    }, label=f"{_thread} scene {idx+1}")
                else:
                    result = _fal_subscribe_with_retry("fal-ai/flux-pro/v1.1-ultra", {
                        "prompt": prompt,
                        "image_size": {"width": 2560, "height": 1440},
                        "num_images": 1,
                        "safety_tolerance": "2",
                    }, label=f"{_thread} scene {idx+1}")

            images = result.get("images", [])
            if not images:
                raise ValueError("fal.ai returned empty images list")
            url = images[0]["url"]
            download_file(url, attempt_path)
            logger.info(f"  [{_thread}] {attempt_path.name} ({attempt_path.stat().st_size//1024}KB)")

            # Log fal.ai cost (per image generated, including retries)
            try:
                from core.cost_tracker import get_active_run_id, log_cost
                _rid = get_active_run_id()
                if _rid:
                    log_cost(_rid, "images", "fal_ai", 1, "images")
            except Exception:
                pass

            # Quality gate via Claude Haiku vision
            _score = _score_image(attempt_path)

            logger.info(f"  [{_thread}] Quality: {_score}/10 {'OK' if _score >= IMAGE_QUALITY_THRESHOLD else 'below threshold'}")

            if _score > best_score:
                best_score = _score
                best_path = attempt_path

            if _score >= IMAGE_QUALITY_THRESHOLD:
                break

            if attempt < IMAGE_MAX_RETRIES - 1:
                logger.info(f"  [{_thread}] Regenerating (attempt {attempt+2}/{IMAGE_MAX_RETRIES})...")
                time.sleep(1)

        # Use the best image we got (even if below threshold)
        if best_path and best_path != img_path:
            shutil.copy2(best_path, img_path)
            best_path.unlink(missing_ok=True)
        for att in assets_dir.glob(f"scene_{idx:03d}_ai_attempt*.jpg"):
            att.unlink(missing_ok=True)

        if best_score < IMAGE_QUALITY_THRESHOLD:
            logger.warning(f"  [{_thread}] Best quality {best_score}/10 — below {IMAGE_QUALITY_THRESHOLD} threshold but using anyway")
        scene["ai_image"] = str(img_path)
        return (idx, scene, True)

    except Exception as e:
        logger.error(f"  [{_thread}] fal.ai failed for scene {idx+1}: {e}")
        # Wikimedia fallback
        visual = scene.get("visual", {})
        wiki_url = visual.get("url", "") if isinstance(visual, dict) else ""
        if wiki_url:
            try:
                fallback_path = assets_dir / f"scene_{idx:03d}_fallback.jpg"
                from pipeline.helpers import download_file as _dl
                _dl(wiki_url, fallback_path)
                scene["ai_image"] = str(fallback_path)
                logger.info(f"  [{_thread}] Using Wikimedia fallback: {fallback_path.name}")
                return (idx, scene, True)
            except Exception as fb_err:
                logger.error(f"  [{_thread}] Wikimedia fallback also failed: {fb_err}")
        scene["ai_image"] = None
        return (idx, scene, False)


def _generate_character_portraits(visual_bible, scenes, assets_dir):
    """Generate reference portraits for top characters using FLUX Pro Ultra. Returns {name: path}."""
    from pipeline.helpers import download_file
    char_descs = visual_bible.get("character_descriptions", {})
    art_style = visual_bible.get("art_style", "")
    if not char_descs:
        return {}

    # Count character appearances to prioritize
    char_counts = {}
    for scene in scenes:
        for c in scene.get("characters_mentioned", []):
            char_counts[c] = char_counts.get(c, 0) + 1

    top_chars = sorted(char_descs.keys(), key=lambda c: char_counts.get(c, 0), reverse=True)[:5]
    portraits = {}

    for char_name in top_chars:
        desc = char_descs[char_name]
        slug = re.sub(r'[^a-z0-9]+', '_', char_name.lower()).strip('_')
        portrait_path = assets_dir / f"character_ref_{slug}.jpg"

        try:
            portrait_prompt = (
                f"Portrait of {desc}, neutral studio background, "
                f"front-facing 3/4 view, {art_style}, no text, no watermarks"
            )
            result = _fal_subscribe_with_retry("fal-ai/flux-pro/v1.1-ultra", {
                "prompt": portrait_prompt,
                "image_size": {"width": 1024, "height": 1024},
                "num_images": 1,
            }, label=f"portrait_{slug}")

            images = result.get("images", [])
            if images:
                download_file(images[0]["url"], portrait_path)
                try:
                    from core.cost_tracker import get_active_run_id, log_cost
                    _rid = get_active_run_id()
                    if _rid:
                        log_cost(_rid, "images", "fal_ai", 1, "images")
                except Exception:
                    pass
                score = _score_image(portrait_path)
                if score >= 7:
                    portraits[char_name] = str(portrait_path)
                    logger.info(f"[Portraits] {char_name}: {score}/10")
                else:
                    logger.warning(f"[Portraits] {char_name} scored {score}/10 — skipping")
                    portrait_path.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"[Portraits] Failed for {char_name}: {e}")

    return portraits


def run_images(manifest):
    try:
        import fal_client  # noqa: F401
    except ImportError:
        logger.info("[Images] Installing fal-client...")
        subprocess.run([sys.executable, "-m", "pip", "install", "fal-client"], check=True)

    FAL_KEY = os.getenv("FAL_API_KEY")
    if not FAL_KEY:
        logger.warning("[Images] WARNING: FAL_API_KEY not set — skipping image generation")
        return manifest

    os.environ["FAL_KEY"] = FAL_KEY
    scenes = manifest.get("scenes", [])

    # Generate character reference portraits if visual bible is available
    visual_bible = manifest.get("visual_bible", {})
    character_portraits = _generate_character_portraits(visual_bible, scenes, ASSETS_DIR) if visual_bible else {}
    if character_portraits:
        logger.info(f"[Images] Character portraits generated: {len(character_portraits)}")

    IMAGE_MODEL = os.getenv("IMAGE_MODEL", "recraft").lower()

    STYLE_FLUX = ("masterwork oil painting, museum-quality historical illustration, "
                  "dramatic cinematic composition inspired by Caravaggio and Rembrandt, "
                  "rich chiaroscuro with deep shadows and luminous highlights, "
                  "ultra-detailed faces and period-accurate costumes, "
                  "16:9 widescreen composition, textured canvas feel, "
                  "no text, no watermarks, no modern elements, no UI")
    STYLE_RECRAFT = ("historical documentary illustration, dramatic cinematic lighting, "
                     "rich chiaroscuro inspired by Caravaggio and Rembrandt, "
                     "ultra-detailed period-accurate costumes and architecture, "
                     "no text, no watermarks, no modern elements")
    MOOD_LIGHT = {
        "tense":    "sinister torchlight casting long shadows on stone walls, blood-red undertones, faces half-hidden in darkness",
        "dramatic": "golden candlelight flooding the scene, high contrast chiaroscuro like Caravaggio, dramatic spotlight on central figure",
        "dark":     "single guttering flame in vast darkness, deep impenetrable shadows, silhouettes against dim firelight",
        "cold":     "cold blue moonlight through stone arches, frost-pale skin tones, desolate winter atmosphere",
        "reverent": "warm amber cathedral light streaming through stained glass, sacred golden glow, solemn processional atmosphere",
        "wonder":   "vast open sky with golden hour light, awe-inspiring scale, luminous atmospheric perspective, warm sunlight on massive architecture",
        "warmth":   "soft warm firelight, intimate candlelit interior, gentle amber tones on human faces, tender domestic atmosphere",
        "absurdity":"bright incongruous lighting, slightly surreal color palette, vivid saturated tones that feel dreamlike and impossible",
    }

    logger.info(f"[Images] Using model: {IMAGE_MODEL} ({'Recraft v3' if IMAGE_MODEL == 'recraft' else 'Flux Pro Ultra'})")
    generated = 0

    # Pre-filter cached scenes (synchronous)
    to_generate = []
    for idx, scene in enumerate(scenes):
        img_path = ASSETS_DIR / f"scene_{idx:03d}_ai.jpg"
        if img_path.exists():
            logger.info(f"[Images] Scene {idx+1}/{len(scenes)}: cached")
            scene["ai_image"] = str(img_path)
            generated += 1
        else:
            to_generate.append((idx, scene))

    # Parallel generation for uncached scenes (3 workers)
    if to_generate:
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
        logger.info(f"[Images] Generating {len(to_generate)} scenes with 3 parallel workers...")
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="img_gen") as pool:
            futures = {}
            for idx, scene in to_generate:
                fut = pool.submit(
                    _generate_single_image, idx, scene, len(scenes),
                    ASSETS_DIR, IMAGE_MODEL, MOOD_LIGHT, STYLE_RECRAFT, STYLE_FLUX,
                    character_portraits,
                )
                futures[fut] = idx

            for future in as_completed(futures):
                try:
                    result_idx, updated_scene, success = future.result(timeout=300)
                    scenes[result_idx] = updated_scene
                    if success:
                        generated += 1
                except TimeoutError:
                    tidx = futures[future]
                    logger.error(f"  [Images] Scene {tidx+1} timed out (300s)")
                    scenes[tidx]["ai_image"] = None
                except Exception as e:
                    tidx = futures[future]
                    logger.error(f"  [Images] Scene {tidx+1} unexpected error: {e}")
                    scenes[tidx]["ai_image"] = None

    manifest["scenes"] = scenes
    logger.info(f"[Images] ✓ Generated {generated}/{len(scenes)} images")

    # Abort if more than 50% of scenes have no AI image
    total_scenes = len(scenes)
    scenes_with_images = sum(1 for s in scenes if s.get("ai_image"))
    if total_scenes > 0 and scenes_with_images / total_scenes < 0.5:
        raise Exception(
            f"[Images] ABORT: Only {scenes_with_images}/{total_scenes} scenes have images "
            f"({scenes_with_images/total_scenes*100:.0f}%). Pipeline would produce unwatchable video. "
            f"Check fal.ai API key and quota, then retry with --from-stage 10"
        )

    # Write image attribution audit log
    audit_log = []
    for i, scene in enumerate(scenes):
        entry = {
            "scene_index": i,
            "has_image": bool(scene.get("ai_image")),
            "source": "none",
            "license": "none",
            "source_url": "",
        }
        ai_img = scene.get("ai_image")
        wiki_img = scene.get("wikimedia_url", "") or scene.get("footage_url", "")

        if ai_img and "ai.jpg" in str(ai_img):
            entry["source"] = "fal.ai (AI generated)"
            entry["license"] = "AI-generated, no copyright"
        elif wiki_img and "wikimedia" in str(wiki_img).lower():
            entry["source"] = "Wikimedia Commons"
            entry["license"] = "Public Domain / CC"
            entry["source_url"] = str(wiki_img)
        elif ai_img:
            entry["source"] = "unknown"
            entry["license"] = "verify manually"

        audit_log.append(entry)

    audit_path = OUTPUT_DIR / "image_audit_log.json"
    audit_data = {
        "generated_at": datetime.now().isoformat(),
        "total_scenes": len(scenes),
        "scenes_with_images": sum(1 for s in scenes if s.get("ai_image")),
        "sources": audit_log,
    }
    with open(audit_path, "w") as f:
        json.dump(audit_data, f, indent=2)
    logger.info(f"[Images] Audit log: {audit_path.name}")
    try:
        from core.utils import persist_json_to_supabase
        persist_json_to_supabase(audit_path, audit_data)
    except Exception:
        pass

    return manifest
