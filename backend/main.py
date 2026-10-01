"""
FastAPI Application & 5-Layer Falsification Pipeline Orchestrator for SatQuery AI.
SIH26167 — ISRO Multimodal Remote Sensing Assistant.
"""

import sys
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
import numpy as np

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.models import (
    QueryInput,
    CompiledQuery,
    OpticalPathwayResult,
    SarPathwayResult,
    ArbiterDecision,
    ConfidenceResult,
    StructuredVerdictObject,
    AnalysisResponse
)
from core.l1_compiler import compile_query
from core.l2a_optical import analyze_optical_change, array_to_data_url
from core.l2b_sar import analyze_sar_change
from core.l3_arbiter import evaluate_verdict
from core.l4_confidence import build_confidence_result
from core.l5_verdict_to_language import translate_verdict_to_language
from data.demo_scenarios import DEMO_SCENARIOS, get_scenario_assets, _generate_realistic_optical_sar_pair

app = FastAPI(
    title="SatQuery AI API",
    description="Falsification-First Multimodal Remote Sensing Vision-Language Assistant",
    version="1.0.0"
)

# Enable CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "SatQuery AI Backend",
        "architecture": "5-Layer Falsification-First",
        "layers": {
            "L1": "Query Compiler (Claim/Negation)",
            "L2a": "Optical Pathway (Independent)",
            "L2b": "SAR Pathway (Independent)",
            "L3": "Falsification Arbiter (Deterministic Rule Engine)",
            "L4": "Confidence Engine (Diversity-Weighted Survival Score + Overlay)",
            "L5": "Verdict-to-Language (Constrained Translation)"
        },
        "version": "1.0.0"
    }

@app.get("/api/scenarios")
def list_scenarios():
    """Returns all pre-baked demonstration scenarios."""
    scenarios_list = []
    for sc_id, sc in DEMO_SCENARIOS.items():
        assets = get_scenario_assets(sc_id)
        scenarios_list.append({
            **sc,
            "previews": assets["previews"]
        })
    return scenarios_list

@app.post("/api/compile", response_model=CompiledQuery)
def endpoint_compile_query(query_input: QueryInput):
    """L1: Compiles query into claim & negated claim."""
    return compile_query(query_input)

@app.post("/api/analyze", response_model=AnalysisResponse)
async def endpoint_analyze(query_input: QueryInput):
    """
    Executes the complete 5-layer falsification pipeline:
    L1 -> L2a & L2b (parallel, strictly independent) -> L3 Arbiter -> L4 Confidence & Overlay -> L5 Language
    """
    start_time = time.time()
    evidence_trace: List[Dict[str, Any]] = []

    # -------------------------------------------------------------
    # Layer 1 — Query Compiler
    # -------------------------------------------------------------
    t0 = time.time()
    compiled: CompiledQuery = compile_query(query_input)
    t1_comp = time.time()
    evidence_trace.append({
        "layer": "L1 — Query Compiler",
        "duration_ms": round((t1_comp - t0) * 1000, 2),
        "claim": compiled.claim,
        "negated_claim": compiled.negated_claim,
        "query_type": compiled.query_type,
        "target_class": compiled.target_class,
        "region": compiled.region.coords,
        "temporal_range": f"{compiled.t1} to {compiled.t2}"
    })

    # -------------------------------------------------------------
    # Retrieve or generate paired sensor imagery
    # -------------------------------------------------------------
    scenario_id = query_input.scenario_id or "wayanad_confirmed"
    if scenario_id not in DEMO_SCENARIOS:
        scenario_id = "wayanad_confirmed"

    assets = get_scenario_assets(scenario_id)
    opt1, opt2 = assets["opt1"], assets["opt2"]
    sar1, sar2 = assets["sar1"], assets["sar2"]
    previews = assets["previews"]

    # -------------------------------------------------------------
    # Layers 2a & 2b — Parallel Independent Evidence Pathways
    # Hard Rule: Neither pathway receives the other's data!
    # -------------------------------------------------------------
    loop = asyncio.get_event_loop()

    # Execute L2a (Optical)
    opt_task = loop.run_in_executor(
        executor,
        analyze_optical_change,
        opt1,
        opt2,
        compiled.target_class
    )

    # Execute L2b (SAR)
    sar_task = loop.run_in_executor(
        executor,
        analyze_sar_change,
        sar1,
        sar2
    )

    optical_res, sar_res = await asyncio.gather(opt_task, sar_task)

    evidence_trace.append({
        "layer": "L2a — Optical Pathway",
        "change_detected": optical_res.change_detected,
        "change_score": optical_res.change_score,
        "cloud_cover_frac": optical_res.cloud_cover_frac,
        "optical_confidence": optical_res.optical_confidence,
        "indices": {
            "ndvi_t1": optical_res.ndvi_t1_mean,
            "ndvi_t2": optical_res.ndvi_t2_mean,
            "delta_ndvi": optical_res.delta_ndvi_mean
        },
        "details": optical_res.details
    })

    evidence_trace.append({
        "layer": "L2b — SAR Pathway",
        "change_detected": sar_res.change_detected,
        "change_score": sar_res.change_score,
        "speckle_noise_level": sar_res.speckle_noise_level,
        "sar_confidence": sar_res.sar_confidence,
        "telemetry": {
            "backscatter_t1_db": sar_res.backscatter_t1_mean_db,
            "backscatter_t2_db": sar_res.backscatter_t2_mean_db,
            "log_ratio_mean": sar_res.log_ratio_mean
        },
        "details": sar_res.details
    })

    # -------------------------------------------------------------
    # Layer 3 — Falsification Arbiter (Deterministic, Zero ML/LLM)
    # -------------------------------------------------------------
    arbiter_decision: ArbiterDecision = evaluate_verdict(optical_res, sar_res)
    evidence_trace.append({
        "layer": "L3 — Falsification Arbiter",
        "verdict": arbiter_decision.verdict,
        "rule_applied": arbiter_decision.rule_applied,
        "score_divergence": arbiter_decision.score_difference,
        "agreement_threshold": arbiter_decision.agreement_threshold,
        "blind_spot": arbiter_decision.blind_spot_identified,
        "decision_steps": arbiter_decision.decision_steps
    })

    # -------------------------------------------------------------
    # Layer 4 — Confidence Engine & Spatial Overlay
    # -------------------------------------------------------------
    # Use optical mask and SAR mask generated by pathways
    # Decode or reconstruct binary masks
    opt_mask = np.zeros(opt1.shape[:2], dtype=np.uint8)
    sar_mask = np.zeros(sar1.shape[:2], dtype=np.uint8)
    if optical_res.change_detected:
        # Approximate mask from details if available
        opt_mask = (np.abs(opt2[:, :, 0].astype(int) - opt1[:, :, 0].astype(int)) > 30).astype(np.uint8) * 255
    if sar_res.change_detected:
        sar_mask = (np.abs(sar2.astype(int) - sar1.astype(int)) > 25).astype(np.uint8) * 255

    base_rgb = opt2[:, :, :3]
    conf_res: ConfidenceResult = build_confidence_result(
        optical_res,
        sar_res,
        arbiter_decision,
        opt_mask,
        sar_mask,
        base_rgb
    )

    evidence_trace.append({
        "layer": "L4 — Confidence Engine",
        "diversity_weight": conf_res.diversity_weight,
        "agreement_strength": conf_res.agreement_strength,
        "survival_score": conf_res.survival_score,
        "spatial_stats": conf_res.spatial_stats
    })

    # -------------------------------------------------------------
    # Layer 5 — Verdict-to-Language (Strictly Constrained Translation)
    # Input: ONLY the StructuredVerdictObject! No raw imagery.
    # -------------------------------------------------------------
    verdict_obj = StructuredVerdictObject(
        verdict=arbiter_decision.verdict,
        claim=compiled.claim,
        negated_claim=compiled.negated_claim,
        query_type=compiled.query_type,
        target_class=compiled.target_class,
        optical={
            "change_detected": optical_res.change_detected,
            "change_score": optical_res.change_score,
            "cloud_cover_frac": optical_res.cloud_cover_frac,
            "optical_confidence": optical_res.optical_confidence
        },
        sar={
            "change_detected": sar_res.change_detected,
            "change_score": sar_res.change_score,
            "speckle_noise_level": sar_res.speckle_noise_level,
            "sar_confidence": sar_res.sar_confidence
        },
        survival_score=conf_res.survival_score,
        diversity_weight=conf_res.diversity_weight,
        rule_applied=arbiter_decision.rule_applied,
        blind_spot_identified=arbiter_decision.blind_spot_identified
    )

    plain_language_answer = translate_verdict_to_language(verdict_obj)

    evidence_trace.append({
        "layer": "L5 — Verdict-to-Language",
        "plain_language_answer": plain_language_answer,
        "total_pipeline_ms": round((time.time() - start_time) * 1000, 2)
    })

    visuals = {
        "optical_t1": previews["optical_t1"],
        "optical_t2": previews["optical_t2"],
        "sar_t1": previews["sar_t1"],
        "sar_t2": previews["sar_t2"],
        "optical_mask": optical_res.mask_data_url,
        "sar_mask": sar_res.mask_data_url,
        "confidence_overlay": conf_res.overlay_data_url,
    }

    return AnalysisResponse(
        compiled_query=compiled,
        optical_result=optical_res,
        sar_result=sar_res,
        arbiter_decision=arbiter_decision,
        confidence_result=conf_res,
        verdict_object=verdict_obj,
        plain_language_answer=plain_language_answer,
        evidence_trace=evidence_trace,
        visuals=visuals
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
