"""
Pre-baked Demo Scenarios & Multimodal Remote Sensing Synthetic Tile Generator.

Provides 5 rich, geographically accurate scenarios covering:
1. CONFIRMED: Wayanad Landslide / Canopy Loss (Kerala, India)
2. CONTESTED: Brahmaputra Flood with Optical Monsoon Cloud Blind Spot (Assam, India)
3. REJECTED: Thar Desert Arid Control Site (Rajasthan, India)
4. CONFIRMED: Hasdeo Arand Forest Canopy Disruption (Chhattisgarh, India)
5. CONTESTED: Peri-Urban Agrarian Crop Shift vs Built-up Construction False Alarm (Karnataka, India)
"""

import numpy as np
import cv2
import base64
import io
from PIL import Image
from typing import Dict, Any, List

def _to_data_url(arr: np.ndarray) -> str:
    """Converts numpy array to PNG Data URL."""
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    pil_img = Image.fromarray(arr)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

def _generate_realistic_optical_sar_pair(scenario_id: str, size: int = 256):
    """
    Generates realistic paired optical (RGB + NIR) and SAR backscatter arrays.
    Returns:
    optical_t1 (H, W, 4), optical_t2 (H, W, 4),
    sar_t1 (H, W), sar_t2 (H, W),
    preview URLs
    """
    np.random.seed(abs(hash(scenario_id)) % (2**31))

    # Base coordinates grid
    y, x = np.mgrid[0:size, 0:size]
    center_y, center_x = size // 2, size // 2

    if scenario_id == "wayanad_confirmed":
        # Dense forest terrain
        base_green = np.random.normal(120, 15, (size, size))
        base_red = np.random.normal(45, 10, (size, size))
        base_blue = np.random.normal(30, 8, (size, size))
        base_nir = np.random.normal(210, 20, (size, size)) # High NIR for healthy canopy

        opt1 = np.stack([base_red, base_green, base_blue, base_nir], axis=2)
        opt2 = opt1.copy()

        # Landslide scar: teardrop shape along slope
        dist = np.sqrt(((x - center_x) * 1.8)**2 + ((y - center_y) * 0.7)**2)
        scar = (dist < 55) & (y > center_y - 30)
        # In t2, scar replaces green canopy with mud/soil (low NIR, higher Red/Brown)
        opt2[scar, 0] = np.random.normal(160, 15, np.sum(scar)) # Red/brown soil
        opt2[scar, 1] = np.random.normal(110, 12, np.sum(scar)) # Mud
        opt2[scar, 2] = np.random.normal(70, 10, np.sum(scar))
        opt2[scar, 3] = np.random.normal(60, 10, np.sum(scar)) # Drastic drop in NIR

        # SAR: Forest volume scattering in t1 (moderate return with speckle)
        sar1 = np.random.gamma(3.0, 30.0, (size, size)) # SAR Rayleigh/Gamma speckle
        sar2 = sar1.copy()
        # In t2, scar creates rough dielectric debris and surface roughness change
        sar2[scar] = np.random.gamma(7.0, 22.0, np.sum(scar)) # Strong backscatter shift

    elif scenario_id == "brahmaputra_contested":
        # River reach with floodplains
        # River meandering channel
        river_channel = np.abs(y - (center_y + 40 * np.sin(x / 40.0))) < 18
        
        opt1 = np.zeros((size, size, 4), dtype=np.float32)
        # Land
        opt1[:, :, 0] = np.random.normal(70, 12, (size, size))
        opt1[:, :, 1] = np.random.normal(115, 14, (size, size))
        opt1[:, :, 2] = np.random.normal(55, 10, (size, size))
        opt1[:, :, 3] = np.random.normal(170, 15, (size, size))
        # River water in t1 (dark blue/brown, low NIR)
        opt1[river_channel, 0] = 30
        opt1[river_channel, 1] = 50
        opt1[river_channel, 2] = 80
        opt1[river_channel, 3] = 15

        opt2 = opt1.copy()
        # Optical t2 is HEAVILY OBSCURED by monsoon cloud cover (75% of image)
        cloud_noise = np.random.normal(0, 1, (size, size))
        cloud_field = cv2.GaussianBlur(cloud_noise, (51, 51), 0)
        cloud_mask = cloud_field > -0.4 # ~75% cloud cover
        # Clouds are bright white in RGB
        opt2[cloud_mask, 0] = np.random.normal(235, 10, np.sum(cloud_mask))
        opt2[cloud_mask, 1] = np.random.normal(235, 10, np.sum(cloud_mask))
        opt2[cloud_mask, 2] = np.random.normal(245, 8, np.sum(cloud_mask))
        opt2[cloud_mask, 3] = np.random.normal(180, 15, np.sum(cloud_mask))

        # SAR: Microwave penetrates clouds completely!
        sar1 = np.random.gamma(4.0, 25.0, (size, size))
        sar1[river_channel] = np.random.gamma(1.5, 8.0, np.sum(river_channel)) # Smooth water = dark
        
        sar2 = sar1.copy()
        # In t2, massive flood inundation occurs across the floodplains!
        flood_mask = np.abs(y - (center_y + 40 * np.sin(x / 40.0))) < 65
        # Smooth open water acts as specular reflector -> very low radar backscatter!
        sar2[flood_mask] = np.random.gamma(1.2, 7.0, np.sum(flood_mask))

    elif scenario_id == "thar_rejected":
        # Desert arid landscape, dry sand and rock
        base_sand = np.random.normal(190, 15, (size, size))
        opt1 = np.zeros((size, size, 4), dtype=np.float32)
        opt1[:, :, 0] = base_sand + 15
        opt1[:, :, 1] = base_sand - 10
        opt1[:, :, 2] = base_sand - 40
        opt1[:, :, 3] = np.random.normal(50, 8, (size, size)) # Very low NIR (no vegetation)
        
        # t2 is practically identical (no change)
        opt2 = opt1 + np.random.normal(0, 2.0, opt1.shape)

        sar1 = np.random.gamma(3.0, 18.0, (size, size))
        sar2 = sar1 + np.random.normal(0, 1.5, sar1.shape)

    elif scenario_id == "hasdeo_confirmed":
        # Forest canopy
        opt1 = np.zeros((size, size, 4), dtype=np.float32)
        opt1[:, :, 0] = np.random.normal(40, 8, (size, size))
        opt1[:, :, 1] = np.random.normal(130, 12, (size, size))
        opt1[:, :, 2] = np.random.normal(35, 6, (size, size))
        opt1[:, :, 3] = np.random.normal(220, 15, (size, size)) # Dense forest canopy

        opt2 = opt1.copy()
        # Rectangular mining clearing parcel
        parcel = (x > 80) & (x < 180) & (y > 70) & (y < 170)
        opt2[parcel, 0] = np.random.normal(140, 15, np.sum(parcel)) # Pit soil
        opt2[parcel, 1] = np.random.normal(110, 12, np.sum(parcel))
        opt2[parcel, 2] = np.random.normal(85, 10, np.sum(parcel))
        opt2[parcel, 3] = np.random.normal(40, 8, np.sum(parcel)) # Canopy gone

        sar1 = np.random.gamma(5.0, 24.0, (size, size)) # Canopy volume scattering
        sar2 = sar1.copy()
        sar2[parcel] = np.random.gamma(1.8, 12.0, np.sum(parcel)) # Surface roughness / clearing

    else: # periurban_contested
        # Agricultural plots
        opt1 = np.zeros((size, size, 4), dtype=np.float32)
        opt1[:, :, 0] = np.random.normal(55, 10, (size, size))
        opt1[:, :, 1] = np.random.normal(140, 15, (size, size)) # Green crops
        opt1[:, :, 2] = np.random.normal(45, 8, (size, size))
        opt1[:, :, 3] = np.random.normal(190, 15, (size, size))

        opt2 = opt1.copy()
        # Post-harvest seasonal dry soil (color changes drastically from green to yellow/tan)
        fields = (x > 50) & (x < 210) & (y > 50) & (y < 210)
        opt2[fields, 0] = np.random.normal(175, 15, np.sum(fields))
        opt2[fields, 1] = np.random.normal(150, 12, np.sum(fields))
        opt2[fields, 2] = np.random.normal(90, 10, np.sum(fields))
        opt2[fields, 3] = np.random.normal(70, 12, np.sum(fields))

        # SAR: Soil is still flat bare field, no 3D vertical structure, no building walls!
        sar1 = np.random.gamma(2.5, 20.0, (size, size))
        sar2 = sar1 + np.random.normal(0, 2.0, (size, size)) # Negligible backscatter difference!

    # Normalize to uint8
    opt1_u8 = np.clip(opt1, 0, 255).astype(np.uint8)
    opt2_u8 = np.clip(opt2, 0, 255).astype(np.uint8)
    sar1_u8 = np.clip(sar1, 0, 255).astype(np.uint8)
    sar2_u8 = np.clip(sar2, 0, 255).astype(np.uint8)

    # Render True-Color RGB data URLs
    rgb1_url = _to_data_url(opt1_u8[:, :, :3])
    rgb2_url = _to_data_url(opt2_u8[:, :, :3])
    # SAR as grayscale data URLs
    sar1_url = _to_data_url(sar1_u8)
    sar2_url = _to_data_url(sar2_u8)

    return opt1_u8, opt2_u8, sar1_u8, sar2_u8, {
        "optical_t1": rgb1_url,
        "optical_t2": rgb2_url,
        "sar_t1": sar1_url,
        "sar_t2": sar2_url
    }

DEMO_SCENARIOS = {
    "wayanad_confirmed": {
        "id": "wayanad_confirmed",
        "title": "Wayanad Landslide & Canopy Disruption",
        "location": "Meppadi / Chooralmala, Kerala, India",
        "bbox": [76.15, 11.50, 76.28, 11.60],
        "t1": "2024-07-01",
        "t2": "2024-08-05",
        "target_class": "vegetation",
        "query_type": "change_detection",
        "default_query": "Did severe vegetation loss and slope failure occur in the Meppadi region between July and August 2024?",
        "expected_verdict": "CONFIRMED",
        "description": "Devastating slope failure and canopy stripping. Both Optical (ΔNDVI drop) and SAR (microwave backscatter variance) agree concordantly.",
        "badge_color": "emerald"
    },
    "brahmaputra_contested": {
        "id": "brahmaputra_contested",
        "title": "Brahmaputra Flood vs Optical Cloud Obscuration",
        "location": "Kaziranga Reach, Assam, India",
        "bbox": [92.80, 26.50, 93.10, 26.80],
        "t1": "2024-06-15",
        "t2": "2024-07-10",
        "target_class": "water",
        "query_type": "change_detection",
        "default_query": "Detect flood inundation and water spread along the river basin between June and July 2024.",
        "expected_verdict": "CONTESTED",
        "description": "Monsoon cloud cover blocks 75% of optical imagery (blind spot). SAR penetrates clouds and detects specular water reflection. System flags CONTESTED due to optical blind spot!",
        "badge_color": "amber"
    },
    "thar_rejected": {
        "id": "thar_rejected",
        "title": "Thar Desert Arid Sector (Stability Control)",
        "location": "Bhadla, Rajasthan, India",
        "bbox": [71.85, 27.40, 72.05, 27.55],
        "t1": "2024-01-10",
        "t2": "2024-04-20",
        "target_class": "vegetation",
        "query_type": "change_detection",
        "default_query": "Did massive vegetation clearing or forest canopy loss occur in this desert sector?",
        "expected_verdict": "REJECTED",
        "description": "Arid stable landscape. Both optical and SAR detect zero significant change. The claim fails falsification and is rejected.",
        "badge_color": "crimson"
    },
    "hasdeo_confirmed": {
        "id": "hasdeo_confirmed",
        "title": "Hasdeo Arand Canopy Deforestation",
        "location": "Hasdeo Forest, Chhattisgarh, India",
        "bbox": [82.70, 22.75, 82.90, 22.95],
        "t1": "2023-11-01",
        "t2": "2024-03-30",
        "target_class": "vegetation",
        "query_type": "change_detection",
        "default_query": "Has tree felling and canopy clearing expanded in the designated forest parcel?",
        "expected_verdict": "CONFIRMED",
        "description": "Clearance parcel verified by optical NIR absorption loss and SAR canopy volume scattering drop.",
        "badge_color": "emerald"
    },
    "periurban_contested": {
        "id": "periurban_contested",
        "title": "Peri-Urban Crop Harvesting (Built-Up False Alarm)",
        "location": "Devanahalli Corridor, Karnataka, India",
        "bbox": [77.65, 13.05, 77.80, 13.20],
        "t1": "2024-02-01",
        "t2": "2024-05-15",
        "target_class": "built-up",
        "query_type": "change_detection",
        "default_query": "Has new built-up construction replaced agricultural fields?",
        "expected_verdict": "CONTESTED",
        "description": "Optical sees strong surface color shift from post-harvest dry soil, but SAR detects no vertical structures or corner reflectors. Disagreement on magnitude!",
        "badge_color": "amber"
    }
}

# Cache pre-generated scenario assets
_SCENARIO_ASSET_CACHE: Dict[str, Any] = {}

def get_scenario_assets(scenario_id: str):
    """Retrieves or generates realistic multispectral and SAR tiles for a scenario."""
    if scenario_id not in _SCENARIO_ASSET_CACHE:
        opt1, opt2, sar1, sar2, previews = _generate_realistic_optical_sar_pair(scenario_id)
        _SCENARIO_ASSET_CACHE[scenario_id] = {
            "opt1": opt1,
            "opt2": opt2,
            "sar1": sar1,
            "sar2": sar2,
            "previews": previews
        }
    return _SCENARIO_ASSET_CACHE[scenario_id]
