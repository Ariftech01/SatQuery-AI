"""
L2a — Optical Pathway (Independent Evidence Source #1)

HARD ARCHITECTURAL RULE:
This module must NEVER receive or use SAR data.
It must be fully computable from optical imagery alone.
"""

import numpy as np
import cv2
import base64
import io
from typing import Tuple, Dict, Any, Optional
from PIL import Image
from .models import OpticalPathwayResult

def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """NDVI (Normalized Difference Vegetation Index): (NIR - Red) / (NIR + Red + 1e-6)"""
    nir_f = nir.astype(np.float32)
    red_f = red.astype(np.float32)
    denom = nir_f + red_f + 1e-6
    ndvi = (nir_f - red_f) / denom
    return np.clip(ndvi, -1.0, 1.0)

def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI (Normalized Difference Water Index): (Green - NIR) / (Green + NIR + 1e-6)"""
    green_f = green.astype(np.float32)
    nir_f = nir.astype(np.float32)
    denom = green_f + nir_f + 1e-6
    ndwi = (green_f - nir_f) / denom
    return np.clip(ndwi, -1.0, 1.0)

def compute_ndbi(swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDBI (Normalized Difference Built-up Index): (SWIR - NIR) / (SWIR + NIR + 1e-6)"""
    swir_f = swir.astype(np.float32)
    nir_f = nir.astype(np.float32)
    denom = swir_f + nir_f + 1e-6
    ndbi = (swir_f - nir_f) / denom
    return np.clip(ndbi, -1.0, 1.0)

def estimate_cloud_cover(rgb_img: np.ndarray) -> Tuple[float, np.ndarray]:
    """
    Estimates cloud cover fraction from optical tile.
    Clouds typically exhibit high reflectance across all RGB channels and low saturation.
    """
    hsv = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2HSV)
    v_channel = hsv[:, :, 2]
    s_channel = hsv[:, :, 1]
    # Bright & low saturation
    cloud_mask = (v_channel > 210) & (s_channel < 50)
    cloud_frac = float(np.mean(cloud_mask))
    return cloud_frac, cloud_mask

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

def analyze_optical_change(
    optical_t1: np.ndarray,
    optical_t2: np.ndarray,
    target_class: Optional[str] = "vegetation",
    threshold: float = 0.20
) -> OpticalPathwayResult:
    """
    Independent Optical Change Analysis.
    Takes t1 and t2 multispectral optical tiles (H x W x C where channels include RGB and NIR/SWIR).
    If 3-channel RGB provided, simulates NIR via channel synthesis.
    """
    # Channel extraction
    h, w, c = optical_t1.shape
    if c >= 4:
        r1, g1, b1, nir1 = optical_t1[:,:,0], optical_t1[:,:,1], optical_t1[:,:,2], optical_t1[:,:,3]
        r2, g2, b2, nir2 = optical_t2[:,:,0], optical_t2[:,:,1], optical_t2[:,:,2], optical_t2[:,:,3]
    else:
        # Standard RGB: construct NIR approximation from Green & Red reflectance
        r1, g1, b1 = optical_t1[:,:,0], optical_t1[:,:,1], optical_t1[:,:,2]
        r2, g2, b2 = optical_t2[:,:,0], optical_t2[:,:,1], optical_t2[:,:,2]
        nir1 = np.clip(g1.astype(np.float32) * 1.3 + (255 - r1.astype(np.float32)) * 0.3, 0, 255).astype(np.uint8)
        nir2 = np.clip(g2.astype(np.float32) * 1.3 + (255 - r2.astype(np.float32)) * 0.3, 0, 255).astype(np.uint8)

    # Cloud cover estimation on t2 (and t1)
    rgb2 = optical_t2[:, :, :3]
    cloud_frac, cloud_mask = estimate_cloud_cover(rgb2)
    
    # Compute indices
    ndvi1 = compute_ndvi(nir1, r1)
    ndvi2 = compute_ndvi(nir2, r2)
    ndwi1 = compute_ndwi(g1, nir1)
    ndwi2 = compute_ndwi(g2, nir2)

    # Change analysis tailored to target class
    if target_class == "water":
        diff = ndwi2 - ndwi1
        change_mask = (diff > threshold) & (~cloud_mask)
        mean_diff = float(np.mean(diff[~cloud_mask])) if np.any(~cloud_mask) else 0.0
    elif target_class == "built-up":
        # Multi-spectral Euclidean difference
        diff_rgb = np.linalg.norm(optical_t2.astype(np.float32) - optical_t1.astype(np.float32), axis=2) / 255.0
        change_mask = (diff_rgb > threshold) & (~cloud_mask)
        mean_diff = float(np.mean(diff_rgb[~cloud_mask])) if np.any(~cloud_mask) else 0.0
    else:
        # Default: vegetation loss or land clearing (drop in NDVI)
        delta_ndvi = ndvi2 - ndvi1
        # Loss corresponds to delta_ndvi < -threshold
        change_mask = (delta_ndvi < -threshold) & (~cloud_mask)
        mean_diff = float(np.mean(delta_ndvi[~cloud_mask])) if np.any(~cloud_mask) else 0.0

    # Change fraction and change score
    valid_pixels = np.sum(~cloud_mask)
    if valid_pixels > 0 and cloud_frac < 0.35:
        change_ratio = float(np.sum(change_mask) / valid_pixels)
    else:
        change_ratio = 0.0

    # Scale change score to 0.0 - 1.0 (calibrated for remote sensing tile proportions)
    change_score = float(np.clip(change_ratio * 7.0, 0.0, 1.0))
    # If cloud cover is high (>= 35%), optical cannot reliably confirm surface change
    if cloud_frac >= 0.35:
        change_detected = False
        change_score = min(change_score, 0.10)
    else:
        change_detected = change_score >= 0.10

    # Optical confidence is strictly penalized by cloud cover
    optical_confidence = float(np.clip(1.0 - cloud_frac, 0.05, 1.0))

    # Mask visualization: binary mask as grayscale/colored array
    mask_viz = np.zeros((h, w, 3), dtype=np.uint8)
    mask_viz[change_mask] = [0, 240, 255] # Cyan highlight for optical change
    if cloud_frac > 0.10:
        mask_viz[cloud_mask] = [180, 180, 180] # Grey highlight for clouds

    mask_data_url = array_to_data_url(mask_viz)

    return OpticalPathwayResult(
        pathway="optical",
        change_detected=change_detected,
        change_score=round(change_score, 4),
        cloud_cover_frac=round(cloud_frac, 4),
        optical_confidence=round(optical_confidence, 4),
        ndvi_t1_mean=round(float(np.mean(ndvi1)), 4),
        ndvi_t2_mean=round(float(np.mean(ndvi2)), 4),
        delta_ndvi_mean=round(mean_diff, 4),
        mask_path="optical_change_mask.png",
        mask_data_url=mask_data_url,
        details={
            "change_pixel_count": int(np.sum(change_mask)),
            "valid_pixel_count": int(valid_pixels),
            "cloud_pixel_count": int(np.sum(cloud_mask)),
            "change_area_ratio": round(change_ratio, 4)
        }
    )
