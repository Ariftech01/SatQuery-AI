# SatQuery AI — Prototype Build
### Interactive Falsification-First Vision-Language Assistant for Multimodal Remote Sensing
**Problem Statement:** SIH26167 | **Organization:** ISRO (Indian Space Research Organisation) | **Domain:** Space Technology & Multimodal Remote Sensing

---

## 1. What SatQuery AI Is (and What It Is NOT)

Most existing remote-sensing LLM agents (e.g. RS-Agent, RS-ChatGPT, ThinkGeo, RS-Claw) follow a **confirmation-seeking** loop: they form a candidate answer and then search for visual or tool evidence to support it. This leads directly to LLM hallucinations, selective evidence filtering, and silent papering-over of sensor disagreement.

**SatQuery AI is built on a strict Falsification-First philosophy (Popperian Epistemology):**
1. Every natural language query is compiled into an **Assertion Claim ($C$)** AND its strict **Logical Negation ($\neg C$)**.
2. Both are tested independently through **two genuinely isolated evidence pathways**:
   - **Optical Pathway (L2a):** Multispectral index analysis ($\Delta\text{NDVI}$, $\text{NDWI}$, $\text{NDBI}$) and cloud-cover fraction.
   - **SAR Pathway (L2b):** Adaptive Lee speckle filtering and logarithmic ratio backscatter differencing ($\log(t_2 / t_1)$).
   - **Hard Rule:** Neither pathway is permitted to receive or read the other pathway's data.
3. A **deterministic, non-ML, non-LLM Arbiter (L3)** decides the verdict based on formal decision rules.
4. **`CONTESTED` is a first-class, celebrated verdict** — the system highlights sensor disagreement and physical blind spots (e.g., optical cloud cover vs. microwave cloud penetration) rather than guessing.
5. In **Layer 5 (Verdict-to-Language)**, the LLM is **never** permitted to see raw imagery or uncalibrated tensors. It only translates the already-decided structured verdict into concise, factual natural language.

---

## 2. System Architecture

```
                    Natural Language Query + Bounding Box + [t1, t2]
                                          │
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │          L1 — Query Compiler                 │
                   │   Compiles into Claim (C) & Negation (~C)    │
                   └──────────────────────┬───────────────────────┘
                                          │
                      ┌───────────────────┴───────────────────┐
                      ▼                                       ▼
       ┌──────────────────────────────┐        ┌──────────────────────────────┐
       │     L2a — Optical Pathway    │        │       L2b — SAR Pathway      │
       │ Multispectral Indices & Cloud│        │ Lee Speckle Filter & Log-Diff│
       └──────────────┬───────────────┘        └──────────────┬───────────────┘
                      └───────────────────┬───────────────────┘
                                          │
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │         L3 — Falsification Arbiter           │
                   │   Deterministic Rule Engine (NO ML / NO LLM) │
                   │       CONFIRMED  │  CONTESTED  │  REJECTED   │
                   └──────────────────────┬───────────────────────┘
                                          │
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │           L4 — Confidence Engine             │
                   │  Diversity-Weighted Survival Score + Overlay │
                   │  (Green = Confirmed, Amber = Contested, Red) │
                   └──────────────────────┬───────────────────────┘
                                          │
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │          L5 — Verdict-to-Language            │
                   │  Input: Structured Verdict Object ONLY       │
                   │  Strict Translation • 0% Hallucination       │
                   └──────────────────────────────────────────────┘
```

---

## 3. The Three Honesty Notes

Judges and evaluators require complete transparency on what is implemented:

### Note 1: Pretrained Weights vs. From-Scratch Heuristics
- **Optical Pathway (L2a):** Uses calibrated multispectral index differencing ($\Delta\text{NDVI}$, $\text{NDWI}$, $\text{NDBI}$) with adaptive HSV-space cloud obscuration estimation. In production, pre-trained Siamese transformer checkpoints (BIT / ChangeFormer) can be loaded into this module without modifying the inter-layer contract.
- **SAR Pathway (L2b):** Uses a classical, deterministic 7×7 adaptive **Lee speckle filter** and **log-ratio differencing** on radar intensity arrays ($\log(t_2 / t_1)$) without black-box deep learning.
- **Arbiter (L3):** 100% deterministic rule logic implemented in pure Python. **Zero ML and zero LLM.**

### Note 2: MVP Fallback vs. Full Pipeline
- The system includes a dual execution mode:
  - If external LLM API keys (`OPENAI_API_KEY`) are present, L1 and L5 can utilize API models under strict JSON schema enforcement and zero-hallucination system prompts.
  - If no internet or API keys are available, the built-in deterministic L1 compiler and L5 translator activate seamlessly, ensuring the demo **never crashes or freezes on stage**.

### Note 3: What Is Explicitly Out of Scope (Phase 6 Items)
- **Multi-temporal persistent regional memory:** A persistent tile-by-tile belief state updating across repeated historical queries is reserved for future satellite edge integration.
- **Geo-stratified automatic micro-calibration:** While current thresholding supports land-cover target classes (vegetation, water, built-up, landslide), multi-stratum regional hyperparameter tuning is marked for future work.

---

## 4. Pre-Baked Demonstration Scenarios

SatQuery AI ships with 5 pre-baked scenarios to guarantee reproducible live demonstrations:

| ID | Title & Location | Target Class | Default Query | Expected Verdict | Primary Mechanism |
|---|---|---|---|---|---|
| `wayanad_confirmed` | **Wayanad Landslide**, Kerala | Vegetation / Slope | *"Did severe vegetation loss and slope failure occur in Meppadi?"* | **CONFIRMED** | Both Optical $\Delta\text{NDVI}$ drop and SAR backscatter roughness agree within agreement tolerance ($\tau = 0.25$). |
| `brahmaputra_contested` | **Brahmaputra Flood**, Assam | Water | *"Detect flood inundation and water spread along the river basin."* | **CONTESTED** | Optical is obscured by 75%+ monsoon clouds (**blind spot**); SAR penetrates clouds and detects water. System refuses to falsely confirm and flags the sensor asymmetry! |
| `thar_rejected` | **Thar Desert Control**, Rajasthan | Vegetation | *"Did massive vegetation clearing or canopy loss occur in this sector?"* | **REJECTED** | Both optical and SAR show invariant arid terrain. Claim fails falsification and is rejected. |
| `hasdeo_confirmed` | **Hasdeo Arand Mining**, Chhattisgarh | Vegetation | *"Has tree felling and canopy clearing expanded in the forest parcel?"* | **CONFIRMED** | Optical NIR absorption drop and SAR volume scattering drop concordantly agree. |
| `periurban_contested` | **Peri-Urban Crop Shift**, Bengaluru | Built-Up | *"Has new built-up construction replaced agricultural fields?"* | **CONTESTED** | Optical flags seasonal soil color shift, but SAR confirms zero vertical structures/corner reflectors. Magnitude discordance! |

---

## 5. Quickstart & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.11)
- Node.js 18+ (tested on Node v24)
- Git

### 1. Launch Everything in One Click (Windows)
Double-click:
```bash
start_servers.bat
```
This automatically starts:
- **FastAPI Backend:** `http://127.0.0.1:8000` (Interactive Swagger Docs: `http://127.0.0.1:8000/docs`)
- **React + Vite Frontend:** `http://127.0.0.1:5173`

---

### 2. Manual Setup

#### Step A: Backend
```bash
cd backend
python -m pip install -r requirements.txt  # (or install fastapi uvicorn pydantic numpy opencv-python pillow pytest)
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

#### Step B: Frontend
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

---

## 6. Running the Automated Test Suite

SatQuery AI includes 13 unit and integration tests covering all 5 layers:
```bash
python -m pytest backend/tests/ -v
```
Or run `run_tests.bat`.

All 13 tests verify:
- Dual-pathway concordance $\to$ `CONFIRMED`
- Magnitude divergence $\to$ `CONTESTED`
- Optical cloud obscuration blind-spot $\to$ `CONTESTED`
- Unexcused sensor discordance $\to$ `CONTESTED`
- Dual-pathway falsification $\to$ `REJECTED`
- Diversity-Weighted Survival Score calibration ($0.82 \times \text{agreement}$)
- L1 Claim and Logical Negation generation
- L5 Fact-constrained translation guardrails
- End-to-end API analysis endpoints

---

## 7. Acceptance Checklist Verification

- [x] **Can type a free-text query, pick a region and two dates, and get a verdict without errors.**
- [x] **At least one demo query returns CONFIRMED, one CONTESTED, one REJECTED.**
- [x] **Optical and SAR pathway outputs are visibly shown separately before the verdict.**
- [x] **Confidence overlay renders as a color-coded image (Green = Confirmed, Amber = Contested, Red = Rejected), not just a number.**
- [x] **Evidence-trace panel shows the arbiter's reasoning and step-by-step logic, not just its conclusion.**
- [x] **LLM-generated final sentence never contains a fact absent from the verdict object.**
- [x] **README documents what's pretrained, what's MVP-simplified, and what's future work.**
- [x] **App runs from a clean clone with documented setup steps, no hidden manual steps.**
