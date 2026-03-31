"""
JSON Schema definitions for structured output on Wave 1 agents.

Each schema is a raw JSON Schema dict passed to:
    output_config={"format": {"type": "json_schema", "schema": <SCHEMA>}}

Strictness is enforced via `additionalProperties: false` in each schema.
No `name` or `strict` wrapper — the Anthropic SDK handles this natively.
"""

# ── Agent 06: SEO Agent ──────────────────────────────────────────

SEO_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "title_variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "character_count": {"type": "number"},
                    "strategy": {"type": "string"},
                },
                "required": ["title", "character_count", "strategy"],
                "additionalProperties": False,
            },
        },
        "recommended_title": {"type": "string"},
        "description": {
            "type": "object",
            "properties": {
                "hook_lines": {"type": "string"},
                "full_description": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["hook_lines", "full_description", "hashtags"],
            "additionalProperties": False,
        },
        "tags": {"type": "array", "items": {"type": "string"}},
        "chapter_markers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["timestamp", "label"],
                "additionalProperties": False,
            },
        },
        "thumbnail_text": {"type": "string"},
        "thumbnail_concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "text_overlay": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["concept", "text_overlay", "rationale"],
                "additionalProperties": False,
            },
        },
        "end_screen_cta": {"type": "string"},
    },
    "required": [
        "topic", "title_variants", "recommended_title", "description",
        "tags", "chapter_markers", "thumbnail_text", "thumbnail_concepts",
        "end_screen_cta",
    ],
    "additionalProperties": False,
}

# ── Agent 03: Narrative Architect ────────────────────────────────

NARRATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "chosen_angle": {"type": "string"},
        "structure_type": {"type": "string"},
        "length_tier": {"type": "string"},
        "estimated_length_minutes": {"type": "number"},
        "cold_open": {"type": "string"},
        "hook_register": {"type": "string"},
        "hook": {
            "type": "object",
            "properties": {
                "opening_scene": {"type": "string"},
                "stakes": {"type": "string"},
                "opening_question": {"type": "string"},
            },
            "required": ["opening_scene", "stakes", "opening_question"],
            "additionalProperties": False,
        },
        "act1": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "key_beats": {"type": "array", "items": {"type": "string"}},
                "cliffhanger": {"type": "string"},
            },
            "required": ["title", "summary", "key_beats", "cliffhanger"],
            "additionalProperties": False,
        },
        "act2": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "evidence_sequence": {"type": "array", "items": {"type": "string"}},
                "tension_peak": {"type": "string"},
            },
            "required": ["title", "summary", "evidence_sequence", "tension_peak"],
            "additionalProperties": False,
        },
        "act3": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "reveal_sequence": {"type": "array", "items": {"type": "string"}},
                "sources_for_reveal": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "summary", "reveal_sequence", "sources_for_reveal"],
            "additionalProperties": False,
        },
        "ending": {
            "type": "object",
            "properties": {
                "reframe": {"type": "string"},
                "final_line": {"type": "string"},
                "cta": {"type": "string"},
            },
            "required": ["reframe", "final_line", "cta"],
            "additionalProperties": False,
        },
        "pov_shift": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "from_perspective": {"type": "string"},
                "to_perspective": {"type": "string"},
                "line": {"type": "string"},
            },
            "required": ["location", "from_perspective", "to_perspective", "line"],
            "additionalProperties": False,
        },
        "reflection_beat": {
            "type": "object",
            "properties": {
                "placement": {"type": "string"},
                "visual": {"type": "string"},
                "duration_seconds": {"type": "number"},
            },
            "required": ["placement", "visual", "duration_seconds"],
            "additionalProperties": False,
        },
        "archival_moment": {"type": "string"},
        "emotional_arc": {"type": "string"},
        "pacing_notes": {"type": "string"},
    },
    "required": [
        "topic", "chosen_angle", "structure_type", "length_tier",
        "estimated_length_minutes", "cold_open", "hook_register",
        "hook", "act1", "act2", "act3", "ending",
        "pov_shift", "reflection_beat",
        "archival_moment", "emotional_arc", "pacing_notes",
    ],
    "additionalProperties": False,
}

# ── Agent 04b: Script Doctor ─────────────────────────────────────

SCRIPT_DOCTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "hook_strength": {"type": "integer"},
        "emotional_pacing": {"type": "integer"},
        "personality": {"type": "integer"},
        "pov_shifts": {"type": "integer"},
        "voice_consistency": {"type": "integer"},
        "factual_grounding": {"type": "integer"},
        "emotional_arc": {"type": "integer"},
        "breathability": {"type": "integer"},
        "revelation_craft": {"type": "integer"},
        "reflection_beat_present": {"type": "boolean"},
        "exposition_front_loaded": {"type": "boolean"},
        "open_loop": {"type": "boolean"},
        "specific_fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "issue": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["section", "issue", "fix"],
                "additionalProperties": False,
            },
        },
        "feedback": {"type": "string"},
    },
    "required": [
        "hook_strength", "emotional_pacing", "personality",
        "pov_shifts", "voice_consistency", "factual_grounding",
        "emotional_arc", "breathability", "revelation_craft",
        "reflection_beat_present", "exposition_front_loaded",
        "open_loop", "specific_fixes", "feedback",
    ],
    "additionalProperties": False,
}

# ── Agent 07: Scene Breakdown ────────────────────────────────────
# NOTE: narrative_position is injected AFTER Claude's response by
# post-processing code — it is NOT in this schema.

SCENE_BREAKDOWN_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_id": {"type": "integer"},
                    "narration": {"type": "string"},
                    "duration_seconds": {"type": "number"},
                    "visual_type": {
                        "type": "string",
                        "enum": [
                            "historical_art", "broll_atmospheric", "broll_nature",
                            "map", "text_overlay",
                        ],
                    },
                    "visual_description": {"type": "string"},
                    "pexels_query": {"type": "string"},
                    "wikimedia_query": {"type": "string"},
                    "mood": {
                        "type": "string",
                        "enum": [
                            "dark", "tense", "reverent", "cold",
                            "dramatic", "wonder", "warmth", "absurdity",
                        ],
                    },
                    "year": {"type": "string"},
                    "location": {"type": "string"},
                    "characters_mentioned": {"type": "array", "items": {"type": "string"}},
                    "is_reveal_moment": {"type": "boolean"},
                    "show_map": {"type": "boolean"},
                    "show_timeline": {"type": "boolean"},
                    "lower_third": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "key_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "key_text_type": {
                        "anyOf": [
                            {"type": "string", "enum": ["date", "claim", "name"]},
                            {"type": "null"},
                        ],
                    },
                    "retention_hook": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "visual_treatment": {
                        "type": "string",
                        "enum": [
                            "standard", "close_portrait", "wide_establishing",
                            "artifact_detail", "map_overhead", "text_overlay_dark",
                        ],
                    },
                    "is_breathing_room": {"type": "boolean"},
                    "narrative_function": {
                        "type": "string",
                        "enum": [
                            "cold_open", "hook", "setup", "exposition",
                            "rising_action", "complication", "question",
                            "answer", "escalation", "climax",
                            "twist", "reveal", "falling_action",
                            "breathing_room", "reflection", "resolution",
                            "conclusion", "coda", "callback", "silence",
                        ],
                    },
                    "claim_confidence": {
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": ["established", "contested", "speculative"],
                            },
                            {"type": "null"},
                        ],
                    },
                },
                "required": [
                    "scene_id", "narration", "duration_seconds",
                    "visual_type", "visual_description", "pexels_query",
                    "wikimedia_query", "mood", "year", "location",
                    "characters_mentioned", "is_reveal_moment",
                    "show_map", "show_timeline", "lower_third",
                    "key_text", "key_text_type", "retention_hook",
                    "visual_treatment", "is_breathing_room",
                    "narrative_function",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scenes"],
    "additionalProperties": False,
}

# ── Agent 07b: Visual Continuity ─────────────────────────────────
# character_descriptions uses an array of {name, description} objects
# because Anthropic structured output requires additionalProperties: false
# (dynamic keys are not allowed). Post-processing converts to dict.

VISUAL_CONTINUITY_SCHEMA = {
    "type": "object",
    "properties": {
        "visual_bible": {
            "type": "object",
            "properties": {
                "art_style": {"type": "string"},
                "color_palette": {"type": "array", "items": {"type": "string"}},
                "character_descriptions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["name", "description"],
                        "additionalProperties": False,
                    },
                },
                "recurring_motifs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["art_style", "color_palette", "character_descriptions", "recurring_motifs"],
            "additionalProperties": False,
        },
        "enhanced_scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_id": {"type": "integer"},
                    "core_composition": {"type": "string"},
                    "style_suffix": {"type": "string"},
                    "visual_treatment": {
                        "type": "string",
                        "enum": [
                            "standard", "close_portrait", "wide_establishing",
                            "artifact_detail", "map_overhead", "text_overlay_dark",
                        ],
                    },
                    "is_breathing_room": {"type": "boolean"},
                },
                "required": ["scene_id", "core_composition", "style_suffix", "visual_treatment", "is_breathing_room"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["visual_bible", "enhanced_scenes"],
    "additionalProperties": False,
}

# ── Registry for auto-lookup ──────────────────────────────────────
# Agent 13 (Content Auditor) is NOT in the registry — it uses free-form
# JSON with complex per-call prompts that vary between narrative and master evaluations.

SCHEMA_REGISTRY = {
    "06_seo_agent": SEO_SCHEMA,
    "03_narrative_architect": NARRATIVE_SCHEMA,
    "04b_script_doctor": SCRIPT_DOCTOR_SCHEMA,
    "07_scene_breakdown": SCENE_BREAKDOWN_SCHEMA,
    "07b_visual_continuity": VISUAL_CONTINUITY_SCHEMA,
}
