"""
L1 — Query Compiler
Translates natural language questions + region coordinates + temporal timestamps
into a strictly structured JSON containing the claim and its logical negation.

The compiler has zero authority over the final answer; it acts solely as a parser.
"""

import re
import os
import json
from typing import Optional, Dict, Any
from .models import QueryInput, CompiledQuery, RegionBBox

SYSTEM_PROMPT = """You are the SatQuery AI Query Compiler.
Your ONLY job is to compile a remote-sensing natural language question and parameters into a structured JSON claim and its exact logical negation.
Do NOT answer the question. Do NOT assume results.
You must output valid JSON only, with no markdown fences, no explanation.

Schema:
{
  "claim": "string, the literal assertion being tested, e.g. 'vegetation loss occurred in the region between t1 and t2'",
  "negated_claim": "string, the logical negation of claim, e.g. 'no significant vegetation loss occurred in the region between t1 and t2'",
  "query_type": "change_detection" | "presence_detection" | "classification" | "measurement",
  "region": {"type": "bbox", "coords": [minLon, minLat, maxLon, maxLat]},
  "t1": "YYYY-MM-DD or null",
  "t2": "YYYY-MM-DD or null",
  "target_class": "vegetation" | "water" | "built-up" | "deforestation" | "landslide" | "infrastructure" | null
}
"""

def _rule_based_fallback(query_input: QueryInput) -> CompiledQuery:
    """
    Robust deterministic rule-based compiler.
    Ensures the system operates 100% reliably in zero-internet or demo environments.
    """
    q = query_input.query.lower().strip()
    
    # Target class heuristic
    target_class = "vegetation"
    if any(k in q for k in ["flood", "water", "inundation", "river", "lake", "submerged"]):
        target_class = "water"
    elif any(k in q for k in ["built-up", "urban", "construction", "building", "road", "structure", "expansion"]):
        target_class = "built-up"
    elif any(k in q for k in ["deforest", "tree", "forest", "canopy", "clearing", "vegetation", "logging", "greenery"]):
        target_class = "vegetation"
    elif any(k in q for k in ["landslide", "slope", "debris", "mudslide"]):
        target_class = "landslide"

    # Query type heuristic
    query_type = "change_detection"
    if any(k in q for k in ["is there", "presence of", "detect if present"]):
        query_type = "presence_detection"

    # Formulate claim and strict logical negation
    t1 = query_input.t1 or "t1"
    t2 = query_input.t2 or "t2"
    
    if target_class == "vegetation":
        if "loss" in q or "deforest" in q or "clearing" in q or "drop" in q:
            claim = f"Vegetation loss and canopy reduction occurred in the target region between {t1} and {t2}"
            negated_claim = f"No significant vegetation loss occurred in the target region between {t1} and {t2}"
        else:
            claim = f"Vegetation dynamics or change occurred in the target region between {t1} and {t2}"
            negated_claim = f"Vegetation canopy remained stable with no detectable change between {t1} and {t2}"
    elif target_class == "water":
        claim = f"Water surface expansion or flood inundation occurred in the target region between {t1} and {t2}"
        negated_claim = f"No significant water expansion or flood inundation occurred in the target region between {t1} and {t2}"
    elif target_class == "built-up":
        claim = f"New built-up structural emergence or ground development occurred between {t1} and {t2}"
        negated_claim = f"No new structural built-up emergence occurred in the region between {t1} and {t2}"
    elif target_class == "landslide":
        claim = f"Slope failure and severe terrain scar displacement occurred between {t1} and {t2}"
        negated_claim = f"Slope and terrain surface remained geomorphologically intact between {t1} and {t2}"
    else:
        claim = f"Surface change conforming to '{query_input.query}' occurred between {t1} and {t2}"
        negated_claim = f"No surface change conforming to '{query_input.query}' occurred between {t1} and {t2}"

    # Default bbox if not supplied
    coords = query_input.region.coords if query_input.region else [76.15, 11.50, 76.28, 11.60]

    return CompiledQuery(
        claim=claim,
        negated_claim=negated_claim,
        query_type=query_type,
        region=RegionBBox(coords=coords),
        t1=query_input.t1,
        t2=query_input.t2,
        target_class=target_class
    )

def compile_query(query_input: QueryInput) -> CompiledQuery:
    """
    Compiles free-text query into structured claim & negated claim.
    Tries LLM if API key exists, otherwise falls back to deterministic rule-based compiler.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    
    if api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            prompt = f"User query: {query_input.query}\nRegion: {query_input.region.coords if query_input.region else 'default'}\nt1: {query_input.t1}\nt2: {query_input.t2}"
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            raw_json = response.choices[0].message.content
            parsed = json.loads(raw_json)
            # Ensure coordinates are populated
            if "region" not in parsed or not parsed["region"].get("coords"):
                parsed["region"] = {"type": "bbox", "coords": query_input.region.coords if query_input.region else [76.15, 11.50, 76.28, 11.60]}
            return CompiledQuery(**parsed)
        except Exception as e:
            print(f"[L1 Compiler] LLM call failed or not configured ({e}), falling back to deterministic compiler.")

    return _rule_based_fallback(query_input)
