"""
TTS Format Agent
Micro-agent that reformats a script for spoken ElevenLabs delivery.
Sits between the script writer (Agent 04) and the audio stage (Agent 08).
Model: Haiku 4.5 — mechanical reformatting, not creative work.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent_wrapper import call_agent

# Load DNA voice section if available, otherwise use inline default
try:
    from intel.dna_loader import get_dna
    _DNA_VOICE = get_dna(["voice"])
except ImportError:
    _DNA_VOICE = """
=== VOICE & TONE (default) ===
Primary tone: Cinematic and dramatic — like a Netflix documentary narrator.
Present tense narration. Gravitas, intimacy, dread, precision.
""".strip()

SYSTEM_PROMPT = f"""You are a TTS formatting specialist. Your ONLY job is to reformat a documentary narration script
so it sounds natural and clear when spoken aloud by an AI voice (ElevenLabs).

{_DNA_VOICE}

Apply ALL of the following transformations — no exceptions:

1. REPLACE ALL EM-DASHES (—) with natural pauses:
   - Mid-sentence em-dashes → ", " (a brief comma pause)
   - End-of-clause em-dashes before a new thought → "..." (a longer pause)
   - Example: "He knew — and had always known —" → "He knew, and had always known,"

2. EXPAND ALL ABBREVIATIONS:
   - "Dr." → "Doctor"
   - "Mr." → "Mister"
   - "Mrs." → "Missus"
   - "St." → "Saint" (when referring to a person or place)
   - "ca." or "c." (meaning circa) → "circa"
   - "vs." → "versus"
   - "etc." → "and so on"
   - "e.g." → "for example"
   - "i.e." → "that is"
   - "AD" and "BC" remain unchanged (they are spoken as letters)

3. REMOVE ALL PARENTHETICAL ASIDES:
   - Delete everything inside parentheses, including the parentheses themselves
   - Example: "The decree (issued in secret) was dated 1347." → "The decree was dated 1347."

4. REPLACE NUMBERS UNDER 10,000 WITH WORDS:
   - Cardinal numbers: "12" → "twelve", "37" → "thirty-seven", "1,200" → "twelve hundred"
   - Ordinal numbers: "3rd" → "third", "21st" → "twenty-first"
   - Years are NEVER converted — "37 AD" stays "37 AD", "1453" stays "1453"
   - Numbers 10,000 and above remain as digits
   - Decimals remain as digits (e.g. "3.5" stays "3.5")

5. ADD BREATHING ROOM:
   - After every 3-4 sentences, insert a line containing only "..."
   - This signals a beat/pause to the TTS voice
   - Do not add a pause mid-sentence or mid-thought

6. REPLACE SEMICOLONS with ". " for cleaner speech boundaries:
   - "He fled; the city fell." → "He fled. The city fell."

7. REMOVE ALL META-TEXT:
   - Delete any stage directions like [pause], [beat], [whisper], (dramatic pause)
   - Delete any section headers or labels (e.g. "HOOK:", "ACT 1 —")
   - Delete any formatting markers

8. MAINTAIN PRESENT TENSE and the cinematic dread tone throughout.
   - Do not change verb tenses.
   - Do not soften or add drama — only reformat.

9. DO NOT ADD NEW CONTENT:
   - Do not invent sentences, facts, or transitions.
   - Only reformat what exists.

10. OUTPUT FORMAT:
    - Output the full reformatted script as plain text.
    - No JSON wrapper, no headers, no labels.
    - Preserve paragraph breaks (blank lines between paragraphs).
    - The "..." breathing pause markers go on their own line.

Your output is the reformatted script and NOTHING ELSE."""


def run(script_data: dict) -> dict:
    """
    Reformat a script for spoken TTS delivery.

    Args:
        script_data: dict containing at minimum a 'full_script' key with the raw narration text.

    Returns:
        dict with keys:
          - full_script: reformatted script text
          - original_word_count: int
          - formatted_word_count: int
          - changes_made: list of str describing transformations applied
    """
    full_script = script_data.get("full_script", "")
    if not full_script.strip():
        return {
            "full_script": "",
            "original_word_count": 0,
            "formatted_word_count": 0,
            "changes_made": ["No script provided — nothing to format."],
        }

    original_word_count = len(full_script.split())
    print(f"[TTS Format Agent] Reformatting script: {original_word_count} words")

    user_prompt = f"""Reformat the following documentary narration script for spoken TTS delivery.
Apply all 10 formatting rules from your instructions. Output the plain reformatted script only.

SCRIPT:
{full_script}"""

    reformatted = call_agent(
        "tts_format_agent",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=16000,
        expect_json=False,
        topic=script_data.get("topic", ""),
    )

    formatted_word_count = len(reformatted.split())

    # Safety check: if the reformatted script is less than 50% of the original length,
    # something went badly wrong — return the original unchanged.
    if formatted_word_count < original_word_count * 0.50:
        print(
            f"[TTS Format Agent] WARNING: Reformatted script ({formatted_word_count} words) "
            f"is < 50% of original ({original_word_count} words). Returning original unchanged."
        )
        return {
            "full_script": full_script,
            "original_word_count": original_word_count,
            "formatted_word_count": original_word_count,
            "changes_made": [
                "Formatting aborted — reformatted output was less than 50% of original length. "
                "Original script returned unchanged."
            ],
        }

    # Build a summary of changes that were likely applied
    changes_made = _detect_changes(full_script, reformatted)

    print(
        f"[TTS Format Agent] Done: {original_word_count} → {formatted_word_count} words "
        f"| {len(changes_made)} change type(s) applied"
    )

    # Apply pronunciation guide for historical terms
    reformatted, pron_count = _apply_pronunciation_guide(reformatted)
    if pron_count > 0:
        changes_made.append(f"Pronunciation guide: {pron_count} term(s) respelled for TTS accuracy")

    return {
        "full_script": reformatted,
        "original_word_count": original_word_count,
        "formatted_word_count": formatted_word_count,
        "changes_made": changes_made,
    }


# ── Pronunciation Guide ─────────────────────────────────────────────────────
# Respells historical terms for accurate TTS pronunciation.
# ElevenLabs doesn't support SSML phonemes, but responds to phonetic respelling.
# Only applies on first occurrence (so the viewer reads the correct spelling
# in captions, but hears correct pronunciation).

import re as _re

PRONUNCIATION_MAP = {
    # Sanskrit / Indian
    "Arthashastra":   "Artha-shaas-tra",
    "Chanakya":       "Chaa-nuh-kya",
    "Chandragupta":   "Chun-druh-gup-ta",
    "Kautilya":       "Kow-til-ya",
    "Ashoka":         "Uh-sho-ka",
    "Pataliputra":    "Paa-ta-lee-poo-tra",
    "Maurya":         "Mowr-ya",
    "Magadha":        "Muh-guh-dha",
    "Bindusara":      "Bin-doo-saa-ra",
    "Dhamma":         "Dhum-ma",
    "Vishnugupta":    "Vish-noo-gup-ta",
    # Greek / Roman
    "Megasthenes":    "Meh-gas-theh-neez",
    "Seleucus":       "Seh-loo-kus",
    # Egyptian
    "Tutankhamun":    "Too-tan-kah-moon",
    "Akhenaten":      "Ah-keh-nah-ten",
    "Nefertiti":      "Nef-er-tee-tee",
    # General historical
    "Machiavelli":    "Mah-kee-uh-vel-ee",
    "Thucydides":     "Thoo-sid-ih-deez",
}


def _apply_pronunciation_guide(text: str) -> tuple[str, int]:
    """Replace first occurrence of historical terms with phonetic respelling.

    Returns (modified_text, count_of_replacements).
    """
    count = 0
    for term, respelling in PRONUNCIATION_MAP.items():
        # Only replace first occurrence, case-insensitive
        pattern = _re.compile(_re.escape(term), _re.IGNORECASE)
        if pattern.search(text):
            text = pattern.sub(respelling, text, count=1)
            count += 1
    return text, count


def _detect_changes(original: str, reformatted: str) -> list:
    """
    Inspect original and reformatted text to build a human-readable list of
    transformation categories that were applied. Used for pipeline logging only.
    """
    changes = []

    if "\u2014" in original and "\u2014" not in reformatted:
        changes.append("Em-dashes replaced with '...' or ', ' pauses")

    abbrev_markers = ["Dr.", "Mr.", "Mrs.", "St.", "ca.", "vs.", "etc.", "e.g.", "i.e."]
    if any(a in original for a in abbrev_markers):
        changes.append("Abbreviations expanded to full spoken form")

    import re
    if re.search(r"\([^)]+\)", original) and not re.search(r"\([^)]+\)", reformatted):
        changes.append("Parenthetical asides removed")

    if ";" in original and ";" not in reformatted:
        changes.append("Semicolons replaced with '. ' boundaries")

    if "..." in reformatted and reformatted.count("...") > original.count("..."):
        changes.append("Breathing-room pause markers ('...') added between sentence groups")

    # Check for number-to-word conversion (heuristic: look for standalone short digit strings)
    if re.search(r"\b(?<![\d])[1-9][0-9]?\b(?!\s*(AD|BC|[0-9]))", original):
        changes.append("Numbers under 10,000 converted to words (excluding years)")

    meta_patterns = [r"\[.*?\]", r"\(dramatic pause\)", r"\(pause\)", r"\(beat\)",
                     r"^HOOK:", r"^ACT\s+\d", r"^ENDING:"]
    if any(re.search(p, original, re.MULTILINE | re.IGNORECASE) for p in meta_patterns):
        changes.append("Meta-text and stage directions removed")

    if not changes:
        changes.append("Minor whitespace and formatting normalisation applied")

    return changes


if __name__ == "__main__":
    print("TTS Format Agent — run via orchestrator or pass script_data directly.")
    # Quick smoke test
    sample = {
        "full_script": (
            "It is the year 1453 AD. The city — ancient and proud — falls in 3 days. "
            "Dr. Constantine (the last emperor) stands at the gate; he knows the end is near. "
            "37 soldiers remain. He walks forward."
        )
    }
    result = run(sample)
    print("\nReformatted script:")
    print(result["full_script"])
    print(f"\nChanges: {result['changes_made']}")
