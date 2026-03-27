"""
compliance_checker.py — Pre-flight monetization compliance scanner.

Scans scripts for YouTube demonetization triggers BEFORE production begins.
Uses Claude Haiku for intelligent content analysis against YouTube's
advertiser-friendly content guidelines.

Usage:
    from compliance_checker import run
    report = run(script_data, topic="MKUltra")
"""

import os
import sys
import json
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = Path(__file__).resolve().parent.parent

from core.agent_wrapper import call_agent

PREFIX = "[ComplianceChecker]"


# ══════════════════════════════════════════════════════════════════════════════
# Compliance scanning
# ══════════════════════════════════════════════════════════════════════════════

def check_compliance(script_text: str, topic: str) -> dict:
    """
    Scan a script for YouTube monetization risk factors.

    Sends the full script to Claude Haiku with a detailed prompt covering
    YouTube's advertiser-friendly content guidelines.

    Args:
        script_text: The full narration script text.
        topic: The video topic (provides context for appropriate content).

    Returns:
        {risk_level: 'green'|'yellow'|'red',
         flags: [{category, text_excerpt, suggestion, severity}],
         overall_recommendation: str}
    """
    if not script_text or not script_text.strip():
        return {
            "risk_level": "green",
            "flags": [],
            "overall_recommendation": "No script content to check.",
        }

    system_prompt = (
        "You are a YouTube monetization compliance expert. Your job is to scan "
        "documentary scripts for content that could trigger demonetization or "
        "limited ad serving under YouTube's Advertiser-Friendly Content Guidelines.\n\n"
        "## Categories to flag:\n"
        "1. **Graphic violence descriptions** — Detailed depictions of injury, torture, "
        "gore, or death. Educational context helps but graphic detail still triggers.\n"
        "2. **Hate speech or slurs** — Even historical quotes containing slurs. "
        "YouTube's automated systems don't distinguish context.\n"
        "3. **Suicide/self-harm descriptions** — Detailed methods, glorification, or "
        "instructions. Brief historical mentions are usually safe.\n"
        "4. **Child endangerment references** — Any content involving minors in danger, "
        "abuse, or exploitation. Extremely sensitive category.\n"
        "5. **Controversial claims without sourcing** — Conspiracy theories, unverified "
        "allegations, or claims that could be flagged as misinformation.\n"
        "6. **Copyrighted content** — Song lyrics, movie quotes, or book passages "
        "quoted at length (more than a brief fair-use excerpt).\n"
        "7. **Drug use descriptions** — Detailed descriptions of drug manufacturing, "
        "use, or promotion.\n"
        "8. **Sexual content** — Explicit descriptions, even in historical context.\n\n"
        "## Risk levels:\n"
        "- **green**: No issues found. Safe to produce.\n"
        "- **yellow**: Minor issues — add disclaimers or soften language. "
        "Still likely to be monetized with adjustments.\n"
        "- **red**: Major issues — rewrite sections before production. "
        "High risk of demonetization or limited ads.\n\n"
        "## Output format (JSON):\n"
        "{\n"
        '  "risk_level": "green"|"yellow"|"red",\n'
        '  "flags": [\n'
        "    {\n"
        '      "category": "graphic_violence"|"hate_speech"|"suicide_self_harm"|'
        '"child_endangerment"|"controversial_claims"|"copyrighted_content"|'
        '"drug_content"|"sexual_content",\n'
        '      "text_excerpt": "the problematic text from the script",\n'
        '      "suggestion": "how to fix it",\n'
        '      "severity": "low"|"medium"|"high"\n'
        "    }\n"
        "  ],\n"
        '  "overall_recommendation": "summary of what to do"\n'
        "}\n\n"
        "Be thorough but not overly cautious. Documentary channels covering dark history "
        "can discuss difficult topics — the key is HOW they're described. "
        "Educational framing with measured language is usually safe."
    )

    user_prompt = (
        f"Topic: {topic}\n\n"
        f"Please scan this documentary script for monetization risks:\n\n"
        f"---\n{script_text}\n---"
    )

    try:
        print(f"{PREFIX} Scanning script for compliance ({len(script_text)} chars)...")
        result = call_agent("compliance_checker", system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=4000)

        if isinstance(result, dict):
            # Validate expected fields
            result.setdefault("risk_level", "yellow")
            result.setdefault("flags", [])
            result.setdefault("overall_recommendation", "Review flagged items.")
            print(f"{PREFIX} Risk level: {result['risk_level']} ({len(result['flags'])} flags)")
            return result

        print(f"{PREFIX} Unexpected response format — defaulting to yellow.")
        return {
            "risk_level": "yellow",
            "flags": [],
            "overall_recommendation": "Could not parse compliance check — manual review recommended.",
        }

    except Exception as e:
        print(f"{PREFIX} Error during compliance check: {e}")
        return {
            "risk_level": "yellow",
            "flags": [],
            "overall_recommendation": f"Compliance check failed ({e}) — manual review required.",
        }


# ══════════════════════════════════════════════════════════════════════════════
# Alternative suggestions
# ══════════════════════════════════════════════════════════════════════════════

def suggest_alternatives(flags: list[dict]) -> list[dict]:
    """
    For each yellow/red flag, generate a monetization-safe alternative phrasing
    that preserves the story's impact.

    Args:
        flags: List of flag dicts from check_compliance().

    Returns:
        List of dicts: {original_text, alternative_text, category, reasoning}
    """
    actionable = [
        f for f in flags
        if f.get("severity") in ("medium", "high") and f.get("text_excerpt")
    ]

    if not actionable:
        print(f"{PREFIX} No actionable flags — no alternatives needed.")
        return []

    system_prompt = (
        "You are a script doctor for a YouTube documentary channel about dark history. "
        "Your job is to rewrite flagged passages to be monetization-safe while preserving "
        "the emotional and narrative impact.\n\n"
        "Rules:\n"
        "- Keep the same meaning and story beats\n"
        "- Use implication over explicit description\n"
        "- Prefer 'what happened' over 'how it happened' for graphic content\n"
        "- Replace slurs with '[slur]' or describe the language used without quoting it\n"
        "- Add educational framing where helpful\n"
        "- Maintain the documentary's serious tone\n\n"
        "Return a JSON array of objects:\n"
        "[\n"
        "  {\n"
        '    "original_text": "the flagged excerpt",\n'
        '    "alternative_text": "the safe rewrite",\n'
        '    "category": "the flag category",\n'
        '    "reasoning": "brief explanation of what changed and why"\n'
        "  }\n"
        "]"
    )

    # Build the user prompt with all flagged excerpts
    flag_descriptions = []
    for i, f in enumerate(actionable, 1):
        flag_descriptions.append(
            f"{i}. [{f.get('category', 'unknown')}] (severity: {f.get('severity', 'medium')})\n"
            f"   Text: \"{f['text_excerpt']}\"\n"
            f"   Issue: {f.get('suggestion', 'Needs rewrite')}"
        )

    user_prompt = (
        f"Please provide safe alternative phrasings for these {len(actionable)} flagged passages:\n\n"
        + "\n\n".join(flag_descriptions)
    )

    try:
        print(f"{PREFIX} Generating alternatives for {len(actionable)} flags...")
        result = call_agent("compliance_checker", system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=4000)

        if isinstance(result, list):
            print(f"{PREFIX} Generated {len(result)} alternative phrasings.")
            return result
        elif isinstance(result, dict) and "alternatives" in result:
            return result["alternatives"]

        print(f"{PREFIX} Unexpected response format for alternatives.")
        return []

    except Exception as e:
        print(f"{PREFIX} Error generating alternatives: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Auto-apply alternatives
# ══════════════════════════════════════════════════════════════════════════════

def apply_safe_alternatives(script_text: str, alternatives: list[dict]) -> str:
    """
    Auto-apply safe alternative phrasings to the script.

    Args:
        script_text: Original script text.
        alternatives: List of {original_text, alternative_text, ...} dicts.

    Returns:
        Modified script with alternatives applied.
    """
    if not alternatives:
        return script_text

    modified = script_text
    applied = 0

    for alt in alternatives:
        original = alt.get("original_text", "")
        replacement = alt.get("alternative_text", "")
        if not original or not replacement:
            continue

        if original in modified:
            modified = modified.replace(original, replacement, 1)
            applied += 1
        else:
            # Try fuzzy match — the excerpt might be slightly different
            # from the actual script text due to truncation
            original_words = original.split()[:8]
            if len(original_words) >= 4:
                snippet = " ".join(original_words)
                idx = modified.find(snippet)
                if idx >= 0:
                    # Find the end of the sentence or passage
                    end_search = modified[idx:idx + len(original) + 100]
                    period_idx = end_search.find(".")
                    if period_idx > 0:
                        old_passage = modified[idx:idx + period_idx + 1]
                        modified = modified.replace(old_passage, replacement, 1)
                        applied += 1

    print(f"{PREFIX} Applied {applied}/{len(alternatives)} alternatives to script.")
    return modified


# ══════════════════════════════════════════════════════════════════════════════
# Full pipeline
# ══════════════════════════════════════════════════════════════════════════════

def run(script_data: dict, topic: str) -> dict:
    """
    Full compliance pipeline: check → suggest → return report.

    Does NOT auto-apply alternatives — the caller decides whether to use them.

    Args:
        script_data: Dict with 'full_script' key (or string).
        topic: The video topic for context.

    Returns:
        {risk_level, flags, alternatives, safe_script}
    """
    if isinstance(script_data, str):
        script_text = script_data
    else:
        script_text = script_data.get("full_script", "")

    if not script_text:
        print(f"{PREFIX} No script text provided.")
        return {
            "risk_level": "green",
            "flags": [],
            "alternatives": [],
            "safe_script": "",
        }

    print(f"{PREFIX} Starting compliance check for topic: {topic}")

    # Step 1: Check compliance
    compliance = check_compliance(script_text, topic)
    flags = compliance.get("flags", [])
    risk_level = compliance.get("risk_level", "green")

    # Step 2: Suggest alternatives for flagged content
    alternatives = []
    safe_script = script_text
    if flags:
        alternatives = suggest_alternatives(flags)
        if alternatives:
            safe_script = apply_safe_alternatives(script_text, alternatives)

    report = {
        "risk_level": risk_level,
        "flags": flags,
        "alternatives": alternatives,
        "safe_script": safe_script,
        "overall_recommendation": compliance.get("overall_recommendation", ""),
        "topic": topic,
        "script_length": len(script_text),
    }

    print(f"{PREFIX} Compliance check complete — risk: {risk_level}, "
          f"{len(flags)} flags, {len(alternatives)} alternatives suggested.")
    return report


# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check script for YouTube monetization compliance.")
    parser.add_argument("--script-file", help="Path to script JSON file (must have 'full_script' key)")
    parser.add_argument("--topic", default="Unknown", help="Video topic for context")
    parser.add_argument("--text", help="Raw script text (alternative to --script-file)")
    args = parser.parse_args()

    if args.script_file:
        script_path = Path(args.script_file)
        if not script_path.exists():
            print(f"{PREFIX} File not found: {script_path}")
            sys.exit(1)
        script_data = json.loads(script_path.read_text())
    elif args.text:
        script_data = {"full_script": args.text}
    else:
        # Demo mode with sample text
        script_data = {
            "full_script": (
                "In the summer of 1942, the experiments began in earnest. "
                "Prisoners were subjected to freezing temperatures, their screams "
                "echoing through the concrete corridors of Block 5. "
                "Dr. Rascher meticulously documented each death, noting the exact "
                "moment the heart stopped beating."
            )
        }
        print(f"{PREFIX} No input provided — running demo mode.")

    result = run(script_data, args.topic)
    print(json.dumps(result, indent=2, ensure_ascii=False))
