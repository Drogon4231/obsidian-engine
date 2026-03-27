"""
Smoke test — lightweight end-to-end pipeline test with mocked Claude calls.

Validates that data flows correctly between stages 1→7 without hitting real APIs.
Uses fixture mock responses for each agent.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


sys.path.insert(0, str(Path(__file__).parent.parent))

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mock_responses"


def _load_fixture(name: str):
    """Load a mock response fixture."""
    path = FIXTURES_DIR / f"{name}.json"
    data = json.loads(path.read_text())
    return data


# ── Mock call_agent that returns fixtures based on agent_name ─────────────────

def _mock_call_agent(agent_name, **kwargs):
    """Route mock calls to fixture files based on agent name."""
    fixture_map = {
        "01_research_agent": "research_agent",
        "02_originality_agent": "originality_agent",
        "03_narrative_architect": "narrative_architect",
        "04_script_writer": "script_writer",
        "04b_script_doctor": None,  # returns inline
        "05_fact_verification": "fact_verification_agent",
        "06_seo_agent": "seo_agent",
        "07_scene_breakdown": "scene_breakdown_agent",
    }

    fixture_name = fixture_map.get(agent_name)

    if agent_name == "04_script_writer":
        # Script writer returns raw text, not JSON
        return _load_fixture("script_writer")

    if agent_name == "04b_script_doctor":
        # Script evaluator returns inline evaluation
        return {
            "hook_strength": 8, "emotional_pacing": 7, "personality": 8,
            "pov_shifts": 7, "voice_consistency": 8, "factual_grounding": 8,
            "emotional_arc": 7,
            "reflection_beat_present": True, "exposition_front_loaded": False,
            "specific_fixes": [],
            "feedback": "Strong script with good pacing and personality.",
        }

    if fixture_name:
        return _load_fixture(fixture_name)

    # Default: return empty dict
    return {}


# ── Smoke Tests ───────────────────────────────────────────────────────────────

class TestSmokeStageContracts:
    """Verify data contracts between pipeline stages."""

    def test_research_output_feeds_angle(self):
        """Stage 1 (research) output has fields needed by Stage 2 (angle)."""
        research = _load_fixture("research_agent")
        assert "topic" in research
        assert "core_facts" in research
        assert len(research["core_facts"]) >= 3
        assert "key_figures" in research
        assert len(research["key_figures"]) >= 1

    def test_angle_output_feeds_blueprint(self):
        """Stage 2 (angle) output has fields needed by Stage 3 (blueprint)."""
        angle = _load_fixture("originality_agent")
        assert "chosen_angle" in angle
        assert "central_figure" in angle
        assert "hook_moment" in angle
        assert "twist_potential" in angle

    def test_blueprint_output_feeds_script(self):
        """Stage 3 (blueprint) output has fields needed by Stage 4 (script)."""
        blueprint = _load_fixture("narrative_architect")
        assert "hook" in blueprint
        assert "act1" in blueprint
        assert "act2" in blueprint
        assert "act3" in blueprint
        assert "ending" in blueprint
        assert "cold_open" in blueprint
        assert "hook_register" in blueprint

    def test_script_output_feeds_evaluator(self):
        """Stage 4 (script) output can be evaluated."""
        script_text = _load_fixture("script_writer")
        assert isinstance(script_text, str)
        words = script_text.split()
        assert len(words) >= 100  # minimum script length

    def test_verification_output_gates_pipeline(self):
        """Stage 5 (verification) output has verdict field."""
        verification = _load_fixture("fact_verification_agent")
        assert "overall_verdict" in verification
        assert verification["overall_verdict"] in ("APPROVED", "APPROVED_WITH_CORRECTIONS", "REJECTED")

    def test_seo_output_has_title_and_tags(self):
        """Stage 6 (SEO) output has required fields."""
        seo = _load_fixture("seo_agent")
        assert "recommended_title" in seo
        assert "tags" in seo
        assert len(seo["tags"]) >= 5

    def test_scenes_output_has_valid_scenes(self):
        """Stage 7 (scenes) output has scene list with required fields."""
        scenes = _load_fixture("scene_breakdown_agent")
        assert "scenes" in scenes
        assert len(scenes["scenes"]) >= 1
        for scene in scenes["scenes"]:
            assert "narration" in scene
            assert "mood" in scene


class TestSmokeSchemaValidation:
    """Verify schema_validator against real fixture data."""

    def test_research_schema(self):
        from core.schema_validator import validate_stage
        errors = validate_stage(1, _load_fixture("research_agent"))
        assert errors == [], f"Research validation errors: {errors}"

    def test_angle_schema(self):
        from core.schema_validator import validate_stage
        errors = validate_stage(2, _load_fixture("originality_agent"))
        assert errors == [], f"Angle validation errors: {errors}"

    def test_blueprint_schema(self):
        from core.schema_validator import validate_stage
        errors = validate_stage(3, _load_fixture("narrative_architect"))
        assert errors == [], f"Blueprint validation errors: {errors}"

    def test_script_schema(self):
        from core.schema_validator import validate_stage
        # Script stage expects a dict with full_script
        script_text = _load_fixture("script_writer")
        script_data = {"full_script": script_text, "word_count": len(script_text.split())}
        errors = validate_stage(4, script_data)
        assert errors == [], f"Script validation errors: {errors}"

    def test_verification_schema(self):
        from core.schema_validator import validate_stage
        errors = validate_stage(5, _load_fixture("fact_verification_agent"))
        assert errors == [], f"Verification validation errors: {errors}"

    def test_seo_schema(self):
        from core.schema_validator import validate_stage
        errors = validate_stage(6, _load_fixture("seo_agent"))
        assert errors == [], f"SEO validation errors: {errors}"

    def test_scenes_schema(self):
        from core.schema_validator import validate_stage
        errors = validate_stage(7, _load_fixture("scene_breakdown_agent"))
        assert errors == [], f"Scenes validation errors: {errors}"

    def test_blueprint_enums(self):
        from core.schema_validator import validate_blueprint_enums
        blueprint = _load_fixture("narrative_architect")
        errors = validate_blueprint_enums(blueprint)
        assert errors == [], f"Blueprint enum errors: {errors}"

    def test_scene_validation(self):
        from core.schema_validator import validate_scene
        scenes = _load_fixture("scene_breakdown_agent")
        for scene in scenes["scenes"]:
            errors = validate_scene(scene)
            assert errors == [], f"Scene validation errors for scene {scene.get('scene_id')}: {errors}"


class TestSmokeConfigValidation:
    """Verify config validation catches issues."""

    def test_default_config_valid(self):
        from core.pipeline_config import validate_config
        errors = validate_config()
        assert errors == [], f"Default config has errors: {errors}"

    def test_scoring_tiers_consistent(self):
        from core.pipeline_config import (
            SCORING_ADJUSTMENTS_EARLY, SCORING_ADJUSTMENTS_GROWING, SCORING_ADJUSTMENTS_MATURE,
        )
        assert set(SCORING_ADJUSTMENTS_EARLY.keys()) == set(SCORING_ADJUSTMENTS_GROWING.keys())
        assert set(SCORING_ADJUSTMENTS_EARLY.keys()) == set(SCORING_ADJUSTMENTS_MATURE.keys())


class TestSmokeEndToEnd:
    """Smoke test: chain stages 1→7 with mocked Claude calls."""

    @patch("core.agent_wrapper.call_claude")
    @patch("core.agent_wrapper.call_claude_with_search")
    def test_stages_1_through_5(self, mock_search, mock_claude):
        """Run research → angle → blueprint → verification with mocks."""
        call_log = []

        def side_effect(**kwargs):
            call_log.append(kwargs.get("expect_json", True))
            idx = len(call_log) - 1
            fixtures = [
                _load_fixture("research_agent"),
                _load_fixture("originality_agent"),
                _load_fixture("narrative_architect"),
                _load_fixture("fact_verification_agent"),
            ]
            return fixtures[min(idx, len(fixtures) - 1)]

        mock_claude.side_effect = side_effect

        from core.agent_wrapper import call_agent

        # Stage 1: Research
        research = call_agent(
            "01_research_agent",
            system_prompt="test", user_prompt="test",
            stage_num=1, topic="Flight 19",
            enable_recovery=False,
        )
        assert "core_facts" in research

        # Stage 2: Angle
        angle = call_agent(
            "02_originality_agent",
            system_prompt="test", user_prompt="test",
            stage_num=2, topic="Flight 19",
            enable_recovery=False,
        )
        assert "chosen_angle" in angle

        # Stage 3: Blueprint
        blueprint = call_agent(
            "03_narrative_architect",
            system_prompt="test", user_prompt="test",
            stage_num=3, topic="Flight 19",
            enable_recovery=False,
        )
        assert "hook" in blueprint

        # Stage 5: Verification
        verification = call_agent(
            "05_fact_verification",
            system_prompt="test", user_prompt="test",
            stage_num=5, topic="Flight 19",
            enable_recovery=False,
        )
        assert verification["overall_verdict"] == "APPROVED"

    @patch("core.agent_wrapper.call_claude")
    def test_script_evaluator_flow(self, mock_claude):
        """Script evaluator processes script data and returns scored result."""
        mock_claude.return_value = {
            "hook_strength": 8, "emotional_pacing": 7, "personality": 8,
            "pov_shifts": 7, "voice_consistency": 8, "factual_grounding": 8,
            "emotional_arc": 7,
            "reflection_beat_present": True, "exposition_front_loaded": False,
            "specific_fixes": [],
            "feedback": "Strong script.",
        }

        import importlib
        # Patch channel_insights for the evaluator
        with patch.dict("sys.modules", {"intel.channel_insights": MagicMock()}):
            import_path = str(Path(__file__).parent.parent / "agents" / "04b_script_doctor.py")
            spec = importlib.util.spec_from_file_location("script_doctor", import_path)
            script_doctor = importlib.util.module_from_spec(spec)

            # Patch call_agent inside the module
            with patch("core.agent_wrapper.call_agent", side_effect=_mock_call_agent):
                spec.loader.exec_module(script_doctor)

                script_data = {
                    "topic": "Flight 19",
                    "full_script": _load_fixture("script_writer"),
                    "script": {"cold_open": "", "hook": "", "act1": "", "act2": "", "act3": "", "ending": ""},
                    "word_count": 400,
                    "length_tier": "STANDARD",
                }
                blueprint = _load_fixture("narrative_architect")

                result = script_doctor.run(script_data, blueprint)
                assert "approved" in result
                assert "scores" in result
                assert "average_score" in result
                assert isinstance(result["scores"], dict)
                assert len(result["scores"]) == len(script_doctor.SCORED_DIMENSIONS)


class TestSmokePromptVersioning:
    """Verify prompt drift detection works."""

    def test_hash_is_deterministic(self):
        from core.agent_wrapper import _hash_prompt
        h1 = _hash_prompt("test prompt")
        h2 = _hash_prompt("test prompt")
        assert h1 == h2

    def test_different_prompts_different_hashes(self):
        from core.agent_wrapper import _hash_prompt
        h1 = _hash_prompt("prompt A")
        h2 = _hash_prompt("prompt B")
        assert h1 != h2

    def test_drift_detection(self, tmp_path):
        from core.agent_wrapper import _check_prompt_drift
        manifest_path = tmp_path / "prompt_manifest.json"
        with patch("core.agent_wrapper.PROMPT_MANIFEST", manifest_path):
            # First call: registers, no drift
            result1 = _check_prompt_drift("test_agent", "original prompt")
            assert result1 is None

            # Same prompt: no drift
            result2 = _check_prompt_drift("test_agent", "original prompt")
            assert result2 is None

            # Changed prompt: drift detected
            result3 = _check_prompt_drift("test_agent", "changed prompt")
            assert result3 is not None
            assert "PROMPT DRIFT" in result3
