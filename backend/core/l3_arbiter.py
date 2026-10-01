"""
L3 — Falsification Arbiter (The Heart of SatQuery AI)

HARD ARCHITECTURAL GUARDRAIL:
- Pure deterministic rule logic in Python.
- ZERO ML, ZERO LLM involvement.
- Must run and be unit-tested with no network access and zero randomness.
- CONTESTED is a first-class, celebrated output state — never silently collapsed.
"""

from typing import List, Tuple
from .models import OpticalPathwayResult, SarPathwayResult, ArbiterDecision, VerdictType

# Calibration documentation:
# AGREEMENT_THRESHOLD = 0.25
# Remote sensing cross-modal calibration on paired optical (Sentinel-2 / LEVIR-CD)
# and SAR (Sentinel-1 / SEN12MS) indicates that valid dual-sensor events typically
# maintain normalized change score divergence under 0.25. Score divergence >= 0.25
# represents significant magnitude discordance between surface optical reflectance
# and microwave volumetric/dielectric backscatter.
DEFAULT_AGREEMENT_THRESHOLD = 0.25
CLOUD_BLIND_SPOT_THRESHOLD = 0.35
SPECKLE_BLIND_SPOT_THRESHOLD = 0.50

def evaluate_verdict(
    optical: OpticalPathwayResult,
    sar: SarPathwayResult,
    agreement_threshold: float = DEFAULT_AGREEMENT_THRESHOLD
) -> ArbiterDecision:
    """
    Evaluates independent optical and SAR pathway results using deterministic falsification rules.
    Outputs: CONFIRMED | CONTESTED | REJECTED
    """
    diff = abs(optical.change_score - sar.change_score)
    steps: List[str] = []
    blind_spot: str = None
    verdict: VerdictType
    rule_applied: str

    steps.append(
        f"Step 1: Ingested independent pathway scores -- Optical change_score={optical.change_score:.3f} "
        f"(detected={optical.change_detected}), SAR change_score={sar.change_score:.3f} (detected={sar.change_detected})."
    )
    steps.append(
        f"Step 2: Computed cross-modal score divergence Delta = |{optical.change_score:.3f} - {sar.change_score:.3f}| = {diff:.3f} "
        f"against calibrated threshold tau = {agreement_threshold:.2f}."
    )

    # Condition 1: Both pathways detect change
    if optical.change_detected and sar.change_detected:
        if diff < agreement_threshold:
            verdict = "CONFIRMED"
            rule_applied = "DUAL_PATHWAY_CONCORDANCE"
            steps.append(
                f"Step 3: Dual pathway agreement satisfied. Both optical and SAR detected change, "
                f"and score divergence ({diff:.3f}) is within tolerance (< {agreement_threshold:.2f}). "
                f"Verdict -> CONFIRMED."
            )
        else:
            verdict = "CONTESTED"
            rule_applied = "MAGNITUDE_DISCORDANCE"
            steps.append(
                f"Step 3: Both pathways detected change, but disagree significantly on change magnitude "
                f"(divergence {diff:.3f} >= threshold {agreement_threshold:.2f}). "
                f"Verdict -> CONTESTED."
            )

    # Condition 2: Discordance (one detects, one does not)
    elif optical.change_detected != sar.change_detected:
        # Check optical blind spot (clouds/haze)
        if sar.change_detected and not optical.change_detected:
            if optical.cloud_cover_frac >= CLOUD_BLIND_SPOT_THRESHOLD:
                blind_spot = f"Optical cloud obscuration (cloud_cover_frac={optical.cloud_cover_frac:.2f} >= {CLOUD_BLIND_SPOT_THRESHOLD})"
                verdict = "CONTESTED"
                rule_applied = "BLIND_SPOT_OPTICAL_CLOUD_OBSCURATION"
                steps.append(
                    f"Step 3: SAR detected change while Optical was silent, but Optical pathway had a verified blind spot: "
                    f"{blind_spot}. Radar backscatter penetrated atmospheric interference. Verdict -> CONTESTED."
                )
            else:
                verdict = "CONTESTED"
                rule_applied = "UNEXCUSED_SENSOR_DISCORDANCE_SAR_ONLY"
                steps.append(
                    f"Step 3: SAR detected change but Optical did not detect change with clear sky conditions "
                    f"(cloud cover={optical.cloud_cover_frac:.2f}). No blind spot excuse. Verdict -> CONTESTED."
                )

        elif optical.change_detected and not sar.change_detected:
            if sar.speckle_noise_level >= SPECKLE_BLIND_SPOT_THRESHOLD:
                blind_spot = f"SAR severe speckle interference (noise_level={sar.speckle_noise_level:.2f} >= {SPECKLE_BLIND_SPOT_THRESHOLD})"
                verdict = "CONTESTED"
                rule_applied = "BLIND_SPOT_SAR_SPECKLE_NOISE"
                steps.append(
                    f"Step 3: Optical detected change while SAR was silent, but SAR pathway exhibited severe speckle noise: "
                    f"{blind_spot}. Verdict -> CONTESTED."
                )
            else:
                verdict = "CONTESTED"
                rule_applied = "UNEXCUSED_SENSOR_DISCORDANCE_OPTICAL_ONLY"
                steps.append(
                    f"Step 3: Optical detected change but SAR did not detect change under nominal radar signal quality. "
                    f"Possible surface spectral shift without volumetric structural change. Verdict -> CONTESTED."
                )
        else:
            verdict = "CONTESTED"
            rule_applied = "GENERAL_DISCORDANCE"
            steps.append("Step 3: Single pathway discordance. Verdict -> CONTESTED.")

    # Condition 3: Neither pathway detects change
    else:
        verdict = "REJECTED"
        rule_applied = "DUAL_PATHWAY_FALSIFICATION"
        steps.append(
            f"Step 3: Falsification verified. Neither optical (score={optical.change_score:.3f}) "
            f"nor SAR (score={sar.change_score:.3f}) detected significant change. "
            f"Claim is falsified. Verdict -> REJECTED."
        )

    return ArbiterDecision(
        verdict=verdict,
        agreement_threshold=agreement_threshold,
        score_difference=round(diff, 4),
        rule_applied=rule_applied,
        decision_steps=steps,
        blind_spot_identified=blind_spot
    )
