"""
L2b — SAR Pathway (Independent Evidence Source #2)

HARD ARCHITECTURAL RULE:
This module must NEVER receive or use optical data.
It must be fully computable from SAR (Synthetic Aperture Radar) data alone.
"""

import numpy as np
import cv2
import base64
import io
from typing import Tuple, Dict, Any, Optional
from PIL import Image
from .models import SarPathwayResult

def lee_speckle_filter(img: np.ndarray, window_size: int = 7) -> np.ndarray:
    """
    Classical Lee Speckle Filter for SAR intensity imagery.
    W = window_size x window_size.
    Computes local mean and variance to adaptively smooth speckle noise while preserving edges.
    """
    img_f = img.astype(np.float32)
    kernel = np.ones((window_size, window_size), dtype=np.float32) / (window_size * window_size)
    
    local_mean = cv2.filter2D(img_f, -1, kernel)
    local_sq_mean = cv2.filter2D(img_f ** 2, -1, kernel)
    local_var = np.maximum(local_sq_mean - local_mean ** 2, 0.0)
    
    # Estimate overall noise variance from overall image variance
    overall_var = np.var(img_f)
    noise_var = overall_var * 0.15 # Typical empirical speckle estimate
    
    # Weighting factor k = var / (var + noise_var)
    weight = local_var / (local_var + noise_var + 1e-6)
    filtered = local_mean + weight * (img_f - local_mean)
    return np.clip(filtered, 0.0, 255.0)

def estimate_speckle_noise(raw_sar: np.ndarray, filtered_sar: np.ndarray) -> float:
    """
    Estimates residual speckle noise level as normalized mean squared difference.
    Returns scalar 0.0 - 1.0.
    """
    diff = np.abs(raw_sar.astype(np.float32) - filtered_sar.astype(np.float32))
    noise_lvl = float(np.mean(diff) / (np.mean(raw_sar) + 1e-6))
    return float(np.clip(noise_lvl, 0.02, 0.95))

def array_to_data_url(img_arr: np.ndarray) -> str:
    """Encodes numpy uint8 RGB or RGBA or Gray image to a Base64 PNG data URL."""
    if img_arr.dtype != np.uint8:
        if img_arr.max() <= 1.0 and img_arr.min() >= 0.0:
            img_arr = (img_arr * 255).astype(np.uint8)
        else:
            img_arr = np.clip(img_arr, 0, 255).astype(np.uint8)
            
    pil_img = Image.fromarray(img_arr)
    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

def analyze_sar_change(
    sar_t1: np.ndarray,
    sar_t2: np.ndarray,
    threshold: float = 0.45
) -> SarPathwayResult:
    """
    Independent SAR Change Analysis.
    Takes t1 and t2 single or dual-channel SAR backscatter amplitude/intensity tiles.
    Uses Lee speckle filtering followed by log-ratio differencing:
    log_ratio = log(filtered_t2 / filtered_t1)
    """
    # Ensure 2D single channel for backscatter analysis
    if sar_t1.ndim == 3:
        s1 = sar_t1[:, :, 0]
    else:
        s1 = sar_t1

    if sar_t2.ndim == 3:
        s2 = sar_t2[:, :, 0]
    else:
        s2 = sar_t2

    # Step 1: Preprocessing with Lee speckle filter
    filtered_t1 = lee_speckle_filter(s1)
    filtered_t2 = lee_speckle_filter(s2)

    # Estimate speckle noise level
    speckle_noise = estimate_speckle_noise(s2, filtered_t2)

    # Step 2: Log-ratio differencing
    eps = 1.0
    f1 = filtered_t1.astype(np.float32) + eps
    f2 = filtered_t2.astype(np.float32) + eps
    log_ratio = np.log(f2 / f1)
    abs_log_ratio = np.abs(log_ratio)

    # Step 3: Thresholding
    change_mask = abs_log_ratio > threshold
    change_ratio = float(np.mean(change_mask))

    # Scale change score to 0.0 - 1.0 (calibrated for remote sensing area ratio)
    change_score = float(np.clip(change_ratio * 7.0, 0.0, 1.0))
    change_detected = change_score >= 0.10

    # SAR confidence is penalized by high speckle noise
    sar_confidence = float(np.clip(1.0 - (speckle_noise * 0.6), 0.1, 0.98))

    # Convert to approximate dB for telemetry
    db_t1 = float(10 * np.log10(np.mean(f1) + 1e-4))
    db_t2 = float(10 * np.log10(np.mean(f2) + 1e-4))

    # SAR mask visualization (electric purple / magenta highlight for SAR change)
    h, w = s1.shape[:2]
    mask_viz = np.zeros((h, w, 3), dtype=np.uint8)
    mask_viz[change_mask] = [238, 0, 255] # Magenta highlight for SAR change

    mask_data_url = array_to_data_url(mask_viz)

    return SarPathwayResult(
        pathway="sar",
        change_detected=change_detected,
        change_score=round(change_score, 4),
        speckle_noise_level=round(speckle_noise, 4),
        sar_confidence=round(sar_confidence, 4),
        backscatter_t1_mean_db=round(db_t1, 2),
        backscatter_t2_mean_db=round(db_t2, 2),
        log_ratio_mean=round(float(np.mean(abs_log_ratio)), 4),
        mask_path="sar_change_mask.png",
        mask_data_url=mask_data_url,
        details={
            "change_pixel_count": int(np.sum(change_mask)),
            "total_pixels": int(s1.size),
            "change_area_ratio": round(change_ratio, 4)
        }
    )
