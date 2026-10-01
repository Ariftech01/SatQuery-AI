"""
Core Pydantic models for SatQuery AI.
Strict schemas defining contracts between all 5 layers:
L1: Query Compiler
L2a: Optical Pathway
L2b: SAR Pathway
L3: Falsification Arbiter
L4: Confidence Engine
L5: Verdict-to-Language
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

# -------------------------------------------------------------
# L1 — Query Compiler Schemas
# -------------------------------------------------------------

class RegionBBox(BaseModel):
    type: Literal["bbox"] = "bbox"
    # [minLon, minLat, maxLon, maxLat]
    coords: List[float] = Field(..., min_length=4, max_length=4, description="[minLon, minLat, maxLon, maxLat]")

class QueryInput(BaseModel):
    query: str = Field(..., description="Free-text query from the user")
    region: Optional[RegionBBox] = None
    t1: Optional[str] = Field(None, description="Start date YYYY-MM-DD")
    t2: Optional[str] = Field(None, description="End date YYYY-MM-DD")
    scenario_id: Optional[str] = Field(None, description="Optional ID of pre-baked scenario")

class CompiledQuery(BaseModel):
    claim: str = Field(..., description="The literal assertion being tested, e.g. 'vegetation loss occurred in the region between t1 and t2'")
    negated_claim: str = Field(..., description="The logical negation of claim")
    query_type: Literal["change_detection", "presence_detection", "classification", "measurement"] = "change_detection"
    region: RegionBBox
    t1: Optional[str] = Field(None, description="YYYY-MM-DD or null")
    t2: Optional[str] = Field(None, description="YYYY-MM-DD or null")
    target_class: Optional[str] = Field(None, description="e.g. 'vegetation', 'water', 'built-up', 'deforestation'")

# -------------------------------------------------------------
# L2a & L2b — Pathway Output Schemas
# -------------------------------------------------------------

class OpticalPathwayResult(BaseModel):
    pathway: Literal["optical"] = "optical"
    change_detected: bool
    change_score: float = Field(..., ge=0.0, le=1.0, description="Scalar change magnitude 0.0 - 1.0")
    cloud_cover_frac: float = Field(..., ge=0.0, le=1.0, description="Cloud cover fraction 0.0 - 1.0")
    optical_confidence: float = Field(..., ge=0.0, le=1.0, description="1.0 - cloud_cover_frac adjusted by signal quality")
    ndvi_t1_mean: Optional[float] = None
    ndvi_t2_mean: Optional[float] = None
    delta_ndvi_mean: Optional[float] = None
    mask_path: Optional[str] = None
    mask_data_url: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

class SarPathwayResult(BaseModel):
    pathway: Literal["sar"] = "sar"
    change_detected: bool
    change_score: float = Field(..., ge=0.0, le=1.0, description="Scalar change magnitude 0.0 - 1.0")
    speckle_noise_level: float = Field(..., ge=0.0, le=1.0, description="Speckle noise level 0.0 - 1.0")
    sar_confidence: float = Field(..., ge=0.0, le=1.0, description="Signal quality after Lee filter")
    backscatter_t1_mean_db: Optional[float] = None
    backscatter_t2_mean_db: Optional[float] = None
    log_ratio_mean: Optional[float] = None
    mask_path: Optional[str] = None
    mask_data_url: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

# -------------------------------------------------------------
# L3 — Falsification Arbiter Schemas
# -------------------------------------------------------------

VerdictType = Literal["CONFIRMED", "CONTESTED", "REJECTED"]

class ArbiterDecision(BaseModel):
    verdict: VerdictType
    agreement_threshold: float = Field(0.25, description="Calibrated tolerance between pathway scores")
    score_difference: float = Field(..., description="abs(optical.change_score - sar.change_score)")
    rule_applied: str = Field(..., description="Plain-text name of deterministic rule triggered")
    decision_steps: List[str] = Field(default_factory=list, description="Step-by-step trace of the logic")
    blind_spot_identified: Optional[str] = Field(None, description="Identified blind spot if any (e.g. optical cloud cover)")

# -------------------------------------------------------------
# L4 — Confidence Engine Schemas
# -------------------------------------------------------------

class ConfidenceResult(BaseModel):
    diversity_weight: float = Field(..., description="1 - correlation(optical_errors, sar_errors)")
    agreement_strength: float = Field(..., description="1 - score_difference or discordance penalty")
    survival_score: float = Field(..., description="diversity_weight * agreement_strength, calibrated")
    overlay_path: Optional[str] = None
    overlay_data_url: Optional[str] = None
    overlay_legend: Dict[str, str] = Field(
        default_factory=lambda: {
            "green": "CONFIRMED: Dual-pathway agreement on change",
            "amber": "CONTESTED: Pathway disagreement or optical/SAR blind spot",
            "red_or_clear": "REJECTED / STABLE: No significant change detected"
        }
    )
    spatial_stats: Dict[str, float] = Field(default_factory=dict)

# -------------------------------------------------------------
# L5 — Verdict-to-Language & Full Response Schemas
# -------------------------------------------------------------

class StructuredVerdictObject(BaseModel):
    """The ONLY object Layer 5 LLM is permitted to read."""
    verdict: VerdictType
    claim: str
    negated_claim: str
    query_type: str
    target_class: Optional[str] = None
    optical: Dict[str, Any]
    sar: Dict[str, Any]
    survival_score: float
    diversity_weight: float
    rule_applied: str
    blind_spot_identified: Optional[str] = None

class AnalysisResponse(BaseModel):
    compiled_query: CompiledQuery
    optical_result: OpticalPathwayResult
    sar_result: SarPathwayResult
    arbiter_decision: ArbiterDecision
    confidence_result: ConfidenceResult
    verdict_object: StructuredVerdictObject
    plain_language_answer: str
    evidence_trace: List[Dict[str, Any]]
    visuals: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Keys: optical_t1, optical_t2, sar_t1, sar_t2, optical_mask, sar_mask, confidence_overlay, composite"
    )
