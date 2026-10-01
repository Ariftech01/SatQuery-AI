"""
Unit tests for SatQuery AI:
- Layer 1 Query Compiler
- Layer 3 Deterministic Falsification Arbiter
- Layer 4 Confidence Engine
- Layer 5 Verdict-to-Language
"""

import pytest
from core.models import OpticalPathwayResult, SarPathwayResult, StructuredVerdictObject, QueryInput
from core.l1_compiler import compile_query
from core.l3_arbiter import evaluate_verdict
from core.l4_confidence import compute_survival_score
from core.l5_verdict_to_language import translate_verdict_to_language

def test_arbiter_confirmed():
    """Both pathways detect change within agreement threshold -> CONFIRMED"""
    opt = OpticalPathwayResult(
        pathway="optical",
        change_detected=True,
        change_score=0.72,
        cloud_cover_frac=0.05,
        optical_confidence=0.95
    )
    sar = SarPathwayResult(
        pathway="sar",
        change_detected=True,
        change_score=0.68,
        speckle_noise_level=0.12,
        sar_confidence=0.90
    )
    decision = evaluate_verdict(opt, sar, agreement_threshold=0.25)
    assert decision.verdict == "CONFIRMED"
    assert decision.rule_applied == "DUAL_PATHWAY_CONCORDANCE"
    assert decision.score_difference == pytest.approx(0.04, abs=1e-3)

def test_arbiter_contested_magnitude():
    """Both pathways detect change, but disagree significantly on magnitude -> CONTESTED"""
    opt = OpticalPathwayResult(
        pathway="optical",
        change_detected=True,
        change_score=0.85,
        cloud_cover_frac=0.05,
        optical_confidence=0.95
    )
    sar = SarPathwayResult(
        pathway="sar",
        change_detected=True,
        change_score=0.35, # Divergence 0.50 >= 0.25
        speckle_noise_level=0.15,
        sar_confidence=0.88
    )
    decision = evaluate_verdict(opt, sar, agreement_threshold=0.25)
    assert decision.verdict == "CONTESTED"
    assert decision.rule_applied == "MAGNITUDE_DISCORDANCE"

def test_arbiter_contested_optical_cloud_blindspot():
    """SAR detects change, Optical does not due to high cloud cover -> CONTESTED with blind spot"""
    opt = OpticalPathwayResult(
        pathway="optical",
        change_detected=False,
        change_score=0.08,
        cloud_cover_frac=0.75, # High cloud cover
        optical_confidence=0.25
    )
    sar = SarPathwayResult(
        pathway="sar",
        change_detected=True,
        change_score=0.74,
        speckle_noise_level=0.14,
        sar_confidence=0.88
    )
    decision = evaluate_verdict(opt, sar)
    assert decision.verdict == "CONTESTED"
    assert decision.rule_applied == "BLIND_SPOT_OPTICAL_CLOUD_OBSCURATION"
    assert decision.blind_spot_identified is not None
    assert "Optical cloud obscuration" in decision.blind_spot_identified

def test_arbiter_contested_unexcused_discordance():
    """One sensor detects change, the other does not under clear conditions -> CONTESTED"""
    opt = OpticalPathwayResult(
        pathway="optical",
        change_detected=True,
        change_score=0.65,
        cloud_cover_frac=0.04, # Clear sky
        optical_confidence=0.96
    )
    sar = SarPathwayResult(
        pathway="sar",
        change_detected=False,
        change_score=0.05,
        speckle_noise_level=0.10,
        sar_confidence=0.92
    )
    decision = evaluate_verdict(opt, sar)
    assert decision.verdict == "CONTESTED"
    assert decision.rule_applied == "UNEXCUSED_SENSOR_DISCORDANCE_OPTICAL_ONLY"

def test_arbiter_rejected():
    """Neither pathway detects change -> REJECTED"""
    opt = OpticalPathwayResult(
        pathway="optical",
        change_detected=False,
        change_score=0.04,
        cloud_cover_frac=0.02,
        optical_confidence=0.98
    )
    sar = SarPathwayResult(
        pathway="sar",
        change_detected=False,
        change_score=0.06,
        speckle_noise_level=0.08,
        sar_confidence=0.94
    )
    decision = evaluate_verdict(opt, sar)
    assert decision.verdict == "REJECTED"
    assert decision.rule_applied == "DUAL_PATHWAY_FALSIFICATION"

def test_survival_score_metrics():
    """Verifies that survival score correctly reflects confidence"""
    opt = OpticalPathwayResult(pathway="optical", change_detected=True, change_score=0.75, cloud_cover_frac=0.05, optical_confidence=0.95)
    sar = SarPathwayResult(pathway="sar", change_detected=True, change_score=0.70, speckle_noise_level=0.10, sar_confidence=0.90)
    decision = evaluate_verdict(opt, sar)
    agreement_str, survival = compute_survival_score(opt, sar, decision)
    assert survival >= 0.70 # High survival for confirmed

    # Rejected case
    opt_rej = OpticalPathwayResult(pathway="optical", change_detected=False, change_score=0.02, cloud_cover_frac=0.0, optical_confidence=1.0)
    sar_rej = SarPathwayResult(pathway="sar", change_detected=False, change_score=0.03, speckle_noise_level=0.1, sar_confidence=0.9)
    decision_rej = evaluate_verdict(opt_rej, sar_rej)
    _, survival_rej = compute_survival_score(opt_rej, sar_rej, decision_rej)
    assert survival_rej <= 0.20 # Minimal survival for rejected claim

def test_query_compiler_negation():
    """Verifies that L1 compiler generates claim and exact negation without guessing"""
    q_in = QueryInput(
        query="Did deforestation occur in the sanctuary between 2024-01-01 and 2024-06-01?",
        t1="2024-01-01",
        t2="2024-06-01"
    )
    compiled = compile_query(q_in)
    assert "Vegetation loss" in compiled.claim or "occurred" in compiled.claim
    assert "No significant vegetation loss" in compiled.negated_claim or "remained" in compiled.negated_claim
    assert compiled.query_type in ["change_detection", "presence_detection"]
    assert compiled.target_class == "vegetation"

def test_verdict_to_language_constraints():
    """Verifies L5 translation states verdict and cites reasons strictly"""
    verdict_obj = StructuredVerdictObject(
        verdict="CONTESTED",
        claim="Flood inundation occurred along the river",
        negated_claim="No flood inundation occurred along the river",
        query_type="change_detection",
        target_class="water",
        optical={"change_score": 0.08, "cloud_cover_frac": 0.78, "optical_confidence": 0.22},
        sar={"change_score": 0.72, "speckle_noise_level": 0.12, "sar_confidence": 0.90},
        survival_score=0.38,
        diversity_weight=0.82,
        rule_applied="BLIND_SPOT_OPTICAL_CLOUD_OBSCURATION",
        blind_spot_identified="Optical cloud obscuration (cloud_cover_frac=0.78 >= 0.35)"
    )
    text = translate_verdict_to_language(verdict_obj)
    assert "CONTESTED" in text
    assert "cloud" in text.lower()
    assert "0.38" in text or "survival" in text.lower()
