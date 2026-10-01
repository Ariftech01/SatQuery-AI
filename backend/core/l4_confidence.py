"""
L4 — Confidence Engine & Spatial Overlay Generator

Implements:
1. Diversity-Weighted Survival Score:
   Score confidence by how well the claim survived independent, dissimilar pathways,
   weighted by sensor error orthogonality:
   diversity_weight = 1 - correlation(optical_errors, sar_errors)
   survival_score = diversity_weight * agreement_strength
2. Spatial Confidence Overlay:
   Pixel-level color-coded heatmap:
   - Green = CONFIRMED (dual-pathway agreement)
   - Amber = CONTESTED (sensor disagreement or blind spot)
   - Red / Subtle Slate = REJECTED / STABLE (no detected change)
"""

import numpy as np
import cv2
import base64
import io
from PIL import Image
from typing import Optional, Dict, Any, Tuple
from .models import OpticalPathwayResult, SarPathwayResult, ArbiterDecision, ConfidenceResult

# Calibration notes:
# Error correlation r between Optical (passive solar reflectance, cloud-sensitive)
# and SAR (active microwave backscatter, speckle-sensitive) estimated at r ~ 0.18 on paired SEN12MS/LEVIR-CD.
DEFAULT_ERROR_CORRELATION = 0.18
DEFAULT_DIVERSITY_WEIGHT = round(1.0 - DEFAULT_ERROR_CORRELATION, 2) # 0.82

def compute_survival_score(
    optical: OpticalPathwayResult,
    sar: SarPathwayResult,
    arbiter: ArbiterDecision,
    diversity_weight: float = DEFAULT_DIVERSITY_WEIGHT
) -> Tuple[float, float]:
    """
    Computes agreement strength and the Diversity-Weighted Survival Score.
    """
    diff = arbiter.score_difference
    threshold = arbiter.agreement_threshold

    if arbiter.verdict == "CONFIRMED":
        # Both pathways detected change with low divergence
        norm_diff = min(1.0, diff / max(threshold, 1e-4))
        agreement_strength = 1.0 - (norm_diff * 0.5)
        # Combined evidence survival
        raw_survival = 0.65 + 0.35 * agreement_strength
        survival_score = diversity_weight * raw_survival
    elif arbiter.verdict == "CONTESTED":
        # Disagreement or blind spot
        agreement_strength = max(0.1, 1.0 - diff)
        raw_survival = 0.45 * agreement_strength
        survival_score = diversity_weight * raw_survival
    else: # REJECTED
        # Claim failed both pathways
        agreement_strength = 0.05
        max_residual = max(optical.change_score, sar.change_score)
        survival_score = max(0.02, 0.15 * (1.0 - max_residual) * (1.0 - diversity_weight))

    return round(float(np.clip(agreement_strength, 0.0, 1.0)), 4), round(float(np.clip(survival_score, 0.0, 1.0)), 4)

def generate_spatial_confidence_overlay(
    optical_mask_arr: np.ndarray,
    sar_mask_arr: np.ndarray,
    base_image: Optional[np.ndarray] = None,
    alpha: float = 0.65
) -> Tuple[np.ndarray, str, Dict[str, float]]:
    """
    Renders spatial confidence overlay:
    - Green [16, 185, 129]: Dual-sensor confirmed change pixels
    - Amber [245, 158, 11]: Contested change pixels (single sensor detection or discordance)
    - Red [239, 68, 68]: Falsified / rejected pixels or stable terrain
    """
    h, w = optical_mask_arr.shape[:2]
    # Ensure boolean masks
    opt_bool = optical_mask_arr > 0 if optical_mask_arr.ndim == 2 else optical_mask_arr[:, :, 0] > 0
    sar_bool = sar_mask_arr > 0 if sar_mask_arr.ndim == 2 else sar_mask_arr[:, :, 0] > 0

    confirmed_mask = opt_bool & sar_bool
    contested_mask = opt_bool ^ sar_bool
    stable_mask = (~opt_bool) & (~sar_bool)

    # 4-channel RGBA overlay
    overlay_rgba = np.zeros((h, w, 4), dtype=np.uint8)

    # Green for Confirmed
    overlay_rgba[confirmed_mask] = [16, 185, 129, int(255 * alpha)]
    # Amber for Contested
    overlay_rgba[contested_mask] = [245, 158, 11, int(230 * alpha)]
    # Red outline / very light tint for stable/rejected areas
    overlay_rgba[stable_mask] = [30, 41, 59, 30]

    # Calculate spatial stats
    total_px = float(h * w)
    confirmed_ratio = float(np.sum(confirmed_mask) / total_px)
    contested_ratio = float(np.sum(contested_mask) / total_px)
    stable_ratio = float(np.sum(stable_mask) / total_px)

    # Composite with base image if provided
    if base_image is not None:
        if base_image.shape[:2] != (h, w):
            base_image = cv2.resize(base_image, (w, h))
        if base_image.ndim == 2:
            base_rgb = cv2.cvtColor(base_image, cv2.COLOR_GRAY2RGB)
        else:
            base_rgb = base_image[:, :, :3]
        
        # Alpha blending
        overlay_rgb = overlay_rgba[:, :, :3]
        overlay_a = (overlay_rgba[:, :, 3] / 255.0)[:, :, np.newaxis]
        composite = (overlay_rgb * overlay_a + base_rgb * (1.0 - overlay_a)).astype(np.uint8)
    else:
        composite = overlay_rgba

    # Encode to Base64 PNG data URL
    pil_img = Image.fromarray(composite)
    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    overlay_data_url = f"data:image/png;base64,{b64}"

    stats = {
        "confirmed_area_pct": round(confirmed_ratio * 100, 2),
        "contested_area_pct": round(contested_ratio * 100, 2),
        "stable_area_pct": round(stable_ratio * 100, 2),
        "confirmed_pixels": int(np.sum(confirmed_mask)),
        "contested_pixels": int(np.sum(contested_mask))
    }

    return composite, overlay_data_url, stats

def build_confidence_result(
    optical: OpticalPathwayResult,
    sar: SarPathwayResult,
    arbiter: ArbiterDecision,
    optical_mask: np.ndarray,
    sar_mask: np.ndarray,
    base_image: Optional[np.ndarray] = None
) -> ConfidenceResult:
    """Combines survival score calculation with spatial overlay rendering."""
    agreement_strength, survival_score = compute_survival_score(optical, sar, arbiter)
    _, overlay_data_url, stats = generate_spatial_confidence_overlay(optical_mask, sar_mask, base_image)

    return ConfidenceResult(
        diversity_weight=DEFAULT_DIVERSITY_WEIGHT,
        agreement_strength=agreement_strength,
        survival_score=survival_score,
        overlay_path="spatial_confidence_overlay.png",
        overlay_data_url=overlay_data_url,
        spatial_stats=stats
    )
