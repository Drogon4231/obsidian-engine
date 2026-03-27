"""
Agent 05 — Fact Verification Agent
Verifies every flagged claim against 2+ sources. Catches hallucinations.
Includes Google Scholar cross-referencing, myth-busting, and upgraded verdicts.
Model: Sonnet 4.6 — accuracy is never compromised.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent_wrapper import call_agent
from intel.dna_loader import get_dna
import json

DNA = get_dna(["identity"])

SYSTEM_PROMPT = f"""You are the Fact Verification Agent for The Obsidian Archive YouTube channel.

{DNA}

Your job: Verify every claim flagged by the Script Writer. Check each claim against 2+ independent sources.
The Obsidian Archive's credibility depends on accuracy — especially for twist reveals.

CRITICAL: This agent NEVER approves unverifiable claims. It either verifies, flags, or rewrites.

VERDICT SYSTEM — use these exact verdicts:
- VERIFIED_SCHOLARLY: 2+ scholarly/academic sources confirm the claim
- VERIFIED_POPULAR: Popular/general sources confirm but no scholarly backing found
- UNVERIFIED: Cannot find confirmation from any reliable source
- DISPUTED: Sources actively disagree with each other on this claim
- HALLUCINATION: Claim is directly contradicted by reliable sources

Your output must be a JSON object with this structure:
{{
  "topic": "string",
  "verification_summary": "string — overall assessment",
  "verified_claims": [
    {{
      "claim": "string",
      "verdict": "VERIFIED_SCHOLARLY | VERIFIED_POPULAR | UNVERIFIED | DISPUTED | HALLUCINATION",
      "sources": ["source 1", "source 2"],
      "confidence": "HIGH | MEDIUM | LOW",
      "scholarly_confidence": "high | medium | low | none",
      "is_common_myth": false,
      "myth_notes": "string or null — if this claim matches a known myth, explain here",
      "notes": "string"
    }}
  ],
  "verification_sources": [
    {{
      "url": "string — actual URL or reference",
      "title": "string — source title",
      "type": "scholarly | news | encyclopedia | primary_source | other"
    }}
  ],
  "script_corrections": [
    {{
      "original_text": "string — exact text from script to change",
      "corrected_text": "string — what it should say",
      "reason": "string"
    }}
  ],
  "twist_reveal_verified": true,
  "twist_reveal_sources": ["sources backing the twist"],
  "overall_verdict": "APPROVED | APPROVED_WITH_CORRECTIONS | REQUIRES_REWRITE",
  "source_list_for_description": ["clean list of sources for the video description"]
}}

Return ONLY valid JSON. No preamble, no markdown fences.
"""


def run(script: dict, research: dict) -> dict:
    topic = script.get("topic", "Unknown")
    claims = script.get("claims_requiring_verification", [])
    print(f"[Fact Verification] Verifying {len(claims)} claims for: {topic}")

    # ── Batched verification: Haiku searches + Sonnet synthesis ──────────────
    # Instead of 3 Sonnet web-search calls per claim (24 total for 8 claims),
    # we batch all claims into 3 Haiku web-search calls, then let Sonnet
    # synthesize the condensed evidence. Cuts cost ~85-90%.

    # Build numbered claims list for batch prompts
    claims_text = "\n".join(
        f"{i+1}. [{claim_obj.get('source_hint', 'Historical fact')}] {claim_obj.get('claim', '')}"
        for i, claim_obj in enumerate(claims)
    )

    # --- Batch 1: General fact verification (Haiku + web search) ---
    general_evidence = ""
    general_ok = False
    try:
        print(f"[Fact Verification]   Batch search: general verification ({len(claims)} claims)...")
        general_evidence = call_agent(
            "05_fact_verification",
            system_prompt="You are a fact-checker. For EACH numbered claim below, search for evidence that confirms or refutes it. For each claim, provide: the claim number, whether sources confirm or contradict it, and the key source names/URLs. Be concise but thorough — cover every claim.",
            user_prompt=f"Topic: {topic}\n\nVerify each of these claims with independent sources:\n{claims_text}",
            max_tokens=2000,
            use_search=True,
            expect_json=False,
            effort_offset=-1,  # Haiku for batch search
            stage_num=5,
            topic=topic,
        )
        general_ok = True
    except Exception as e:
        print(f"[Fact Verification]   Warning: General batch search failed: {e}")
        general_evidence = f"GENERAL SEARCH FAILED: {e}"

    # --- Batch 2: Scholarly cross-reference (Haiku + web search) ---
    scholarly_evidence = ""
    scholarly_ok = False
    try:
        print(f"[Fact Verification]   Batch search: scholarly sources ({len(claims)} claims)...")
        scholarly_evidence = call_agent(
            "05_fact_verification",
            system_prompt="You are an academic researcher. For EACH numbered claim below, search for scholarly/academic sources — peer-reviewed papers, academic books, university sources. For each claim, report: claim number, any scholarly sources found (author, title, publication), and whether they support the claim. If no scholarly source exists for a claim, say so.",
            user_prompt=f"Topic: {topic}\n\nFind academic/scholarly sources for each claim:\n{claims_text}",
            max_tokens=2000,
            use_search=True,
            expect_json=False,
            effort_offset=-1,  # Haiku for batch search
            stage_num=5,
            topic=topic,
        )
        scholarly_ok = True
    except Exception as e:
        print(f"[Fact Verification]   Warning: Scholarly batch search failed: {e}")
        scholarly_evidence = f"SCHOLARLY SEARCH FAILED: {e}"

    # --- Batch 3: Myth-busting check (Haiku + web search) ---
    myth_evidence = ""
    myth_ok = False
    try:
        print(f"[Fact Verification]   Batch search: myth-busting ({len(claims)} claims)...")
        myth_evidence = call_agent(
            "05_fact_verification",
            system_prompt="You are a myth-buster specializing in historical misconceptions. For EACH numbered claim below, check if it is a known myth, misconception, or commonly repeated but inaccurate 'fact'. For each claim, report: claim number, whether it's a known myth, and any debunking sources found.",
            user_prompt=f"Topic: {topic}\n\nCheck each claim for myths/misconceptions:\n{claims_text}\n\nAlso search for: {topic} myths debunked, {topic} misconceptions",
            max_tokens=1500,
            use_search=True,
            expect_json=False,
            effort_offset=-1,  # Haiku for batch search
            stage_num=5,
            topic=topic,
        )
        myth_ok = True
    except Exception as e:
        print(f"[Fact Verification]   Warning: Myth batch search failed: {e}")
        myth_evidence = f"MYTH CHECK FAILED: {e}"

    # Build verification_notes from batch results (compatible with synthesis prompt)
    verification_notes = []
    for i, claim_obj in enumerate(claims):
        verification_notes.append({
            "claim": claim_obj.get("claim", ""),
            "location": claim_obj.get("location", ""),
            "search_succeeded": general_ok,
            "scholarly_succeeded": scholarly_ok,
            "myth_check_succeeded": myth_ok,
        })

    # Produce final verification report (Sonnet synthesis from Haiku evidence)
    result = call_agent(
        "05_fact_verification",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"""Topic: {topic}

Script to verify:
{script.get('full_script', '')[:3000]}

Claims requiring verification:
{json.dumps(verification_notes, indent=2)}

=== GENERAL VERIFICATION EVIDENCE ===
{general_evidence[:3000]}

=== SCHOLARLY / ACADEMIC EVIDENCE ===
{scholarly_evidence[:2500]}

=== MYTH-BUSTING EVIDENCE ===
{myth_evidence[:2000]}

Original research sources:
{json.dumps(research.get('primary_sources', []), indent=2)}

Twist reveal claim: {script.get('script', {}).get('act3', '')[:500]}

Produce the full verification report. Be strict — the channel's credibility depends on accuracy.

IMPORTANT:
- Use the upgraded verdict system (VERIFIED_SCHOLARLY, VERIFIED_POPULAR, UNVERIFIED, DISPUTED, HALLUCINATION).
- For each claim, set scholarly_confidence based on whether scholarly sources were found (high/medium/low/none).
- If a claim matches a known myth, set is_common_myth to true and explain in myth_notes.
- Include a verification_sources list with actual URLs/references that can be cited in the video description and pinned comment.
- If the twist reveal cannot be verified by 2+ sources, mark overall_verdict as REQUIRES_REWRITE.""",
        max_tokens=8000,
        stage_num=5,
        topic=topic,
    )

    if isinstance(result, list):
        result = {"verified_claims": result, "overall_verdict": "UNKNOWN"}
    verdict = result.get("overall_verdict", "UNKNOWN")
    corrections = len(result.get("script_corrections", []))
    scholarly_claims = sum(
        1 for c in result.get("verified_claims", [])
        if c.get("verdict") == "VERIFIED_SCHOLARLY"
    )
    myth_flags = sum(
        1 for c in result.get("verified_claims", [])
        if c.get("is_common_myth")
    )
    sources_count = len(result.get("verification_sources", []))
    print(f"[Fact Verification] Verdict: {verdict} | Corrections: {corrections}")
    print(f"[Fact Verification] Scholarly verified: {scholarly_claims} | Myth flags: {myth_flags} | Citable sources: {sources_count}")
    return result


if __name__ == "__main__":
    print("Fact Verification requires full pipeline input. Run via orchestrator.")
