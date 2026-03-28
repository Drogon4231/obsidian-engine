"""Multi-part series detection and queuing — extracted from run_pipeline.py."""
from __future__ import annotations
import json
import re

from core.log import get_logger

logger = get_logger(__name__)


def detect_series_potential(research: dict, blueprint: dict) -> dict | None:
    """
    Detect if a topic is too complex for a single video and should be split
    into a multi-part series. Returns series plan or None.

    Signals of series-worthy content:
    - Research has 8+ key figures
    - Timeline spans 50+ years with 10+ major events
    - Blueprint estimated_length > 15 minutes despite hard cap
    - Research has 15+ core facts AND 5+ contradictions
    """
    if not research or not blueprint:
        return None

    key_figures = len(research.get("key_figures", []))
    core_facts = len(research.get("core_facts", []))
    contradictions = len(research.get("contradictions", []))
    timeline_events = len(research.get("timeline", []))
    suppressed = len(research.get("suppressed_details", []))
    primary_sources = len(research.get("primary_sources", []))

    # Calculate complexity score (0-14 scale)
    complexity = 0
    reasons = []

    if key_figures >= 8:
        complexity += 2
        reasons.append(f"{key_figures} key figures")
    elif key_figures >= 5:
        complexity += 1

    if core_facts >= 15:
        complexity += 2
        reasons.append(f"{core_facts} core facts")
    elif core_facts >= 10:
        complexity += 1

    if contradictions >= 5:
        complexity += 1
        reasons.append(f"{contradictions} contradictions")

    if timeline_events >= 10:
        complexity += 2
        reasons.append(f"{timeline_events} timeline events")
    elif timeline_events >= 6:
        complexity += 1

    if suppressed >= 5:
        complexity += 1
        reasons.append(f"{suppressed} suppressed details")

    # Timeline span: extract years from timeline and measure range
    timeline = research.get("timeline", [])
    if timeline:
        years = []
        for event in timeline:
            if not isinstance(event, dict):
                continue
            date_str = str(event.get("date", ""))
            year_match = re.search(r'(\d{3,4})', date_str)
            if year_match:
                y = int(year_match.group(1))
                if "BC" in date_str.upper() or "BCE" in date_str.upper():
                    y = -y
                years.append(y)
        if len(years) >= 2:
            span = max(years) - min(years)
            if span >= 100:
                complexity += 2
                reasons.append(f"{span}-year span")
            elif span >= 50:
                complexity += 1
                reasons.append(f"{span}-year span")

    # Geographic spread: count unique locations in timeline/key_figures
    locations = set()
    for event in timeline:
        if isinstance(event, dict):
            loc = event.get("location", "")
            if loc:
                locations.add(loc.lower().strip())
    for fig in research.get("key_figures", []):
        if isinstance(fig, dict):
            loc = fig.get("location", "")
            if loc:
                locations.add(loc.lower().strip())
    if len(locations) >= 5:
        complexity += 1
        reasons.append(f"{len(locations)} distinct locations")

    # Archival depth: many primary sources = deep enough material for series
    if primary_sources >= 6:
        complexity += 1
        reasons.append(f"{primary_sources} primary sources")

    # Blueprint length signal: if estimated > DEEP_DIVE cap, content is dense
    try:
        est_len = float(blueprint.get("estimated_length_minutes", 0))
        tier = blueprint.get("length_tier", "STANDARD").upper()
        if tier == "EPIC" or est_len >= 20:
            complexity += 1
            reasons.append(f"epic-tier length ({est_len:.0f}min)")
    except (TypeError, ValueError):
        pass

    # Threshold: complexity >= 5 suggests series
    if complexity < 5:
        return None

    # Determine part count: 3-part for truly epic topics, 2-part otherwise
    num_parts = 3 if complexity >= 8 else 2

    topic = research.get("topic", "Unknown")
    logger.info(f"[Series] Topic complexity score: {complexity}/14 — {', '.join(reasons)}")
    logger.info(f"[Series] Recommending {num_parts}-part series for: {topic}")

    # Use Claude to design the series split
    try:
        from clients.claude_client import call_claude, SONNET

        if num_parts == 3:
            schema_desc = (
                "Return JSON:\n"
                "{\n"
                '  "num_parts": 3,\n'
                '  "part_1_title_suffix": "(Part 1: The [something])",\n'
                '  "part_1_focus": "what Part 1 covers — the origin, setup",\n'
                '  "part_1_cliffhanger": "the exact cliffhanger moment to end Part 1 on",\n'
                '  "part_2_title_suffix": "(Part 2: The [something])",\n'
                '  "part_2_focus": "what Part 2 covers — the escalation, mystery deepens",\n'
                '  "part_2_cliffhanger": "the exact cliffhanger moment to end Part 2 on",\n'
                '  "part_3_title_suffix": "(Part 3: The [something])",\n'
                '  "part_3_focus": "what Part 3 covers — the reveal, consequences, legacy",\n'
                '  "split_point_1": "where Part 1→2 split happens",\n'
                '  "split_point_2": "where Part 2→3 split happens"\n'
                "}"
            )
            split_instruction = "Design a 3-part split. Each part ends mid-mystery for maximum 'I need the next part' urgency."
        else:
            schema_desc = (
                "Return JSON:\n"
                "{\n"
                '  "num_parts": 2,\n'
                '  "part_1_title_suffix": "(Part 1: The [something])",\n'
                '  "part_1_focus": "what Part 1 covers — the setup, mystery, buildup",\n'
                '  "part_1_cliffhanger": "the exact cliffhanger moment to end Part 1 on",\n'
                '  "part_2_title_suffix": "(Part 2: The [something])",\n'
                '  "part_2_focus": "what Part 2 covers — the reveal, consequences, aftermath",\n'
                '  "split_point": "the narrative moment where the split happens"\n'
                "}"
            )
            split_instruction = "Design a 2-part split. Part 1 ends mid-mystery for maximum 'I need Part 2' urgency."

        split_plan = call_claude(
            system_prompt=(
                "You are a documentary series planner. Given research data for a complex historical topic, "
                f"split it into a {num_parts}-part series. Each part must end on a cliffhanger that makes the next part essential viewing.\n\n"
                f"{schema_desc}"
            ),
            user_prompt=(
                f"Topic: {topic}\n"
                f"Key figures: {json.dumps(research.get('key_figures', [])[:6], indent=2)}\n"
                f"Core facts: {json.dumps(research.get('core_facts', [])[:8])}\n"
                f"Contradictions: {json.dumps(research.get('contradictions', []))}\n"
                f"Suppressed details: {json.dumps(research.get('suppressed_details', []))}\n"
                f"Blueprint hook: {json.dumps(blueprint.get('hook', {}))}\n"
                f"Blueprint act structure: {blueprint.get('structure_type', 'CLASSIC')}\n\n"
                f"{split_instruction}"
            ),
            model=SONNET,
            max_tokens=1500,
            expect_json=True,
        )
        split_plan["complexity_score"] = complexity
        split_plan["reasons"] = reasons
        split_plan["num_parts"] = num_parts
        logger.info(f"[Series] Split: Part 1 ends at: {split_plan.get('split_point', split_plan.get('split_point_1', 'N/A'))[:80]}")
        return split_plan
    except Exception as e:
        logger.warning(f"[Series] Series planning failed (continuing as single video): {e}")
        return None


def queue_series_parts(topic: str, series_plan: dict, research: dict,
                       state_path: str = ""):
    """Queue remaining parts of a series in Supabase with full context metadata."""
    queued = []
    try:
        from clients import supabase_client
        num_parts = series_plan.get("num_parts", 2)
        for part_num in range(2, num_parts + 1):
            suffix_key = f"part_{part_num}_title_suffix"
            suffix = series_plan.get(suffix_key, f"(Part {part_num})")
            part_topic = f"{topic} {suffix}"
            # Score decreases slightly for later parts to preserve queue priority
            score = round(0.92 - (part_num - 2) * 0.02, 2)
            metadata = {
                "series_part": part_num,
                "series_num_parts": num_parts,
                "parent_topic": topic,
                "series_plan": series_plan,
                "parent_state_path": state_path,
                "part_focus": series_plan.get(f"part_{part_num}_focus", ""),
            }
            supabase_client.add_topic(
                part_topic, source="series_auto", score=score, metadata=metadata,
            )
            logger.info(f"[Series] Queued Part {part_num}: {part_topic} (with context metadata)")
            queued.append(part_topic)
    except Exception as e:
        logger.warning(f"[Series] Failed to queue series parts (non-critical): {e}")
    return queued


# Backward compat alias
def queue_series_part2(topic: str, series_plan: dict, research: dict,
                       state_path: str = ""):
    """Queue Part 2 of a series in Supabase for later production."""
    result = queue_series_parts(topic, series_plan, research, state_path=state_path)
    return result[0] if result else None


def get_retention_optimal_length() -> float | None:
    """Read optimal video length from channel_insights.json retention data."""
    try:
        from intel.channel_insights import load_insights
        insights = load_insights()
        if not insights:
            return None
        ret = insights.get("retention_analysis", {})
        optimal = ret.get("optimal_length_minutes")
        if optimal and isinstance(optimal, (int, float)) and 5 <= optimal <= 20:
            logger.info(f"[Retention] Data-backed optimal length: {optimal:.0f} minutes")
            return float(optimal)
        # Fallback: find best-performing length band
        bands = ret.get("retention_by_length_band", {})
        if bands:
            best_band = max(
                ((k, v) for k, v in bands.items() if v.get("sample_count", 0) >= 2),
                key=lambda x: (x[1].get("avg_retention", 0) * x[1].get("avg_views", 0)),
                default=None,
            )
            if best_band:
                band_map = {"under_8min": 7, "8_to_12min": 10, "12_to_16min": 14, "over_16min": 18}
                length = band_map.get(best_band[0])
                if length:
                    logger.info(f"[Retention] Best band: {best_band[0]} — targeting {length} min")
                    return float(length)
    except Exception as e:
        logger.warning(f"[Retention] Could not load retention data (using default): {e}")
    return None
