"""
schema_validator.py — Reusable schema definitions and validation for pipeline data.

Validates data flowing between agents using lightweight schema definitions.
Used by run_pipeline.py stage validation, quality_gates.py, and smoke tests.
"""

from typing import Any


# ── Schema definitions ─────────────────────────────────────────────────────

# Each schema is a dict of:  field_name → {"type": type, "required": bool, "min_items": int}
# "type" can be: str, int, float, list, dict, bool, or a tuple of types

RESEARCH_SCHEMA = {
    "topic":              {"type": str, "required": True},
    "era":                {"type": str, "required": False},
    "core_facts":         {"type": list, "required": True, "min_items": 3},
    "key_figures":        {"type": list, "required": True, "min_items": 1},
    "suppressed_details": {"type": list, "required": False},
    "contradictions":     {"type": list, "required": False},
    "archival_gems":      {"type": list, "required": False},
    "timeline":           {"type": list, "required": False},
    "primary_sources":    {"type": list, "required": False},
}

ANGLE_SCHEMA = {
    "chosen_angle":    {"type": str, "required": True},
    "central_figure":  {"type": str, "required": False},
    "hook_moment":     {"type": str, "required": False},
    "twist_potential":  {"type": str, "required": False},
}

BLUEPRINT_SCHEMA = {
    "hook":            {"type": dict, "required": True},
    "act1":            {"type": dict, "required": True},
    "act2":            {"type": dict, "required": True},
    "act3":            {"type": dict, "required": True},
    "ending":          {"type": dict, "required": False},
    "structure_type":  {"type": str, "required": False},
    "cold_open":       {"type": str, "required": False},
    "hook_register":   {"type": str, "required": False},
    "length_tier":     {"type": str, "required": False},
}

SCRIPT_SCHEMA = {
    "full_script":   {"type": str, "required": True},
    "word_count":    {"type": (int, float), "required": False},
    "topic":         {"type": str, "required": False},
    "script":        {"type": dict, "required": False},
}

VERIFICATION_SCHEMA = {
    "overall_verdict": {"type": str, "required": True},
}

SEO_SCHEMA = {
    "recommended_title":  {"type": str, "required": True},
    "tags":               {"type": list, "required": False},
}

SCENE_SCHEMA = {
    "narration":           {"type": str, "required": True},
    "mood":                {"type": str, "required": True},
    "image_prompt":        {"type": str, "required": False},
    "narrative_position":  {"type": str, "required": False},
    "narrative_function":  {"type": str, "required": False},
}

SCENES_SCHEMA = {
    "scenes": {"type": list, "required": True, "min_items": 2},
}

AUDIO_SCHEMA = {
    "audio_path":              {"type": str, "required": True},
    "total_duration_seconds":  {"type": (int, float), "required": True},
}

UPLOAD_SCHEMA = {
    "video_id": {"type": str, "required": True},
}

# Stage → schema mapping
STAGE_SCHEMAS = {
    1: ("Research", RESEARCH_SCHEMA),
    2: ("Angle", ANGLE_SCHEMA),
    3: ("Blueprint", BLUEPRINT_SCHEMA),
    4: ("Script", SCRIPT_SCHEMA),
    5: ("Verification", VERIFICATION_SCHEMA),
    6: ("SEO", SEO_SCHEMA),
    7: ("Scenes", SCENES_SCHEMA),
    8: ("Audio", AUDIO_SCHEMA),
    9: ("Footage", SCENES_SCHEMA),
    10: ("Images", SCENES_SCHEMA),
    13: ("Upload", UPLOAD_SCHEMA),
}

# Valid enum values
VALID_MOODS = {"dark", "tense", "dramatic", "cold", "reverent", "wonder", "warmth", "absurdity"}
VALID_NARRATIVE_FUNCTIONS = {
    "hook", "setup", "exposition", "rising_action", "complication",
    "climax", "twist", "reveal", "falling_action", "resolution",
    "reflection", "coda", "cold_open",
}
VALID_STRUCTURE_TYPES = {"CLASSIC", "MYSTERY", "DUAL_TIMELINE", "COUNTDOWN", "TRIAL", "REFRAME"}
VALID_HOOK_REGISTERS = {"TENSION", "DREAD_THROUGH_BEAUTY", "MYSTERY", "INTIMACY"}
VALID_LENGTH_TIERS = {"STANDARD", "DEEP_DIVE", "EPIC"}


# ── Validation functions ───────────────────────────────────────────────────

def validate(data: Any, schema: dict, name: str = "data") -> list[str]:
    """Validate data against a schema. Returns list of errors (empty = valid)."""
    errors = []

    if not isinstance(data, dict):
        return [f"{name}: expected dict, got {type(data).__name__}"]

    for field, rules in schema.items():
        value = data.get(field)
        required = rules.get("required", False)
        expected_type = rules.get("type")
        min_items = rules.get("min_items", 0)

        if value is None or value == "" or value == []:
            if required:
                errors.append(f"{name}.{field}: required but missing/empty")
            continue

        if expected_type and not isinstance(value, expected_type):
            errors.append(
                f"{name}.{field}: expected {expected_type}, got {type(value).__name__}"
            )
            continue

        if isinstance(value, list) and min_items > 0 and len(value) < min_items:
            errors.append(
                f"{name}.{field}: needs {min_items}+ items, has {len(value)}"
            )

    return errors


def validate_stage(stage_num: int, data: Any) -> list[str]:
    """Validate a pipeline stage output. Returns list of errors."""
    # Stages 11-12 return strings (paths)
    if stage_num in (11, 12):
        if isinstance(data, str) and data:
            return []
        return [f"Stage {stage_num}: expected non-empty string path"]

    schema_info = STAGE_SCHEMAS.get(stage_num)
    if not schema_info:
        return []  # no schema defined for this stage

    stage_name, schema = schema_info
    return validate(data, schema, name=f"Stage {stage_num} ({stage_name})")


def validate_scene(scene: dict) -> list[str]:
    """Validate a single scene dict."""
    errors = validate(scene, SCENE_SCHEMA, name="scene")

    mood = scene.get("mood", "")
    if mood and mood not in VALID_MOODS:
        errors.append(f"scene.mood: '{mood}' not in valid moods: {VALID_MOODS}")

    nf = scene.get("narrative_function", "")
    if nf and nf not in VALID_NARRATIVE_FUNCTIONS:
        errors.append(f"scene.narrative_function: '{nf}' not in valid functions")

    return errors


def validate_blueprint_enums(blueprint: dict) -> list[str]:
    """Validate enum fields in a blueprint."""
    errors = []

    st = blueprint.get("structure_type", "")
    if st and st not in VALID_STRUCTURE_TYPES:
        errors.append(f"blueprint.structure_type: '{st}' not in {VALID_STRUCTURE_TYPES}")

    hr = blueprint.get("hook_register", "")
    if hr and hr not in VALID_HOOK_REGISTERS:
        errors.append(f"blueprint.hook_register: '{hr}' not in {VALID_HOOK_REGISTERS}")

    lt = blueprint.get("length_tier", "")
    if lt and lt not in VALID_LENGTH_TIERS:
        errors.append(f"blueprint.length_tier: '{lt}' not in {VALID_LENGTH_TIERS}")

    return errors
