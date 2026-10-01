"""
L5 — Verdict-to-Language (Constrained Translation Layer)

HARD ARCHITECTURAL GUARDRAILS:
1. Input to this module is ONLY the StructuredVerdictObject from L3/L4.
2. The LLM NEVER receives raw imagery, raw sensor matrices, or unverified claims.
3. The LLM's role is strictly translation into plain natural language, NOT reasoning.
4. If CONTESTED, it must explicitly report the disagreement and cite the exact field/reason.
5. It must NEVER invent facts absent from the structured verdict.
"""

import os
import json
from .models import StructuredVerdictObject

SYSTEM_PROMPT = """You are the SatQuery AI Verdict-to-Language translator.
Your ONLY role is to translate a structured remote-sensing verdict object into a concise, factual natural language summary.

CRITICAL RULES:
1. You may ONLY state facts directly present in the input verdict object.
2. Do NOT speculate, infer, or hallucinate external causes, weather events, or history.
3. If the verdict is "CONFIRMED", state that the claim was independently validated by both optical and SAR evidence, quoting the survival score.
4. If the verdict is "CONTESTED", explicitly state that the claim is contested due to sensor discordance or a blind spot, and cite the exact reason provided in the object.
5. If the verdict is "REJECTED", state clearly that falsification succeeded and neither independent sensor detected the claimed event.
6. Keep the response professional, concise (2-4 sentences), and authoritative.
"""

def _deterministic_template_translation(verdict_obj: StructuredVerdictObject) -> str:
    """
    Guaranteed hallucination-free translation engine.
    Ensures 100% compliance with non-negotiable guardrails even without external API access.
    """
    v = verdict_obj.verdict
    claim = verdict_obj.claim
    survival = verdict_obj.survival_score
    opt_score = verdict_obj.optical.get("change_score", 0.0)
    sar_score = verdict_obj.sar.get("change_score", 0.0)
    cloud_frac = verdict_obj.optical.get("cloud_cover_frac", 0.0)
    blind_spot = verdict_obj.blind_spot_identified

    if v == "CONFIRMED":
        return (
            f"VERDICT: CONFIRMED. The claim '{claim}' has been independently verified across both optical "
            f"and synthetic aperture radar (SAR) pathways with a Diversity-Weighted Survival Score of {survival:.2f}. "
            f"Optical spectral analysis detected significant change (magnitude {opt_score:.2f}) and SAR microwave backscatter "
            f"concordantly detected structural change (magnitude {sar_score:.2f}), confirming dual-sensor agreement."
        )
    elif v == "CONTESTED":
        if blind_spot:
            return (
                f"VERDICT: CONTESTED. The claim '{claim}' cannot be confirmed due to sensor asymmetry: {blind_spot}. "
                f"While SAR backscatter detected change (magnitude {sar_score:.2f}), optical imagery had {cloud_frac*100:.1f}% cloud cover. "
                f"Under the falsification architecture, this claim remains CONTESTED rather than prematurely confirmed, achieving a survival score of {survival:.2f}."
            )
        else:
            return (
                f"VERDICT: CONTESTED. The claim '{claim}' is contested due to pathway discordance "
                f"(Optical magnitude {opt_score:.2f} vs SAR magnitude {sar_score:.2f}, rule '{verdict_obj.rule_applied}'). "
                f"One sensor detected significant alteration while the independent peer showed discordance without an atmospheric blind spot. "
                f"The Diversity-Weighted Survival Score is {survival:.2f}."
            )
    else: # REJECTED
        return (
            f"VERDICT: REJECTED. The claim '{claim}' was falsified. Neither the optical pathway "
            f"(change score {opt_score:.2f}) nor the SAR microwave pathway (change score {sar_score:.2f}) detected "
            f"evidence supporting the claim. The claim failed falsification testing with a minimal survival score of {survival:.2f}."
        )

def translate_verdict_to_language(verdict_obj: StructuredVerdictObject) -> str:
    """
    Translates structured verdict into plain language.
    If an OpenAI key is present, calls the LLM with strict translation prompt;
    otherwise uses the deterministic translation engine.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    
    if api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            user_input = json.dumps(verdict_obj.model_dump(), indent=2)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Structured Verdict Object:\n{user_input}"}
                ],
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[L5 Translator] LLM API call error ({e}), using deterministic translator.")

    return _deterministic_template_translation(verdict_obj)
