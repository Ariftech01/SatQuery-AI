import pytest
from fastapi.testclient import TestClient
from main import app
from core.models import QueryInput

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "Falsification-First" in data["architecture"]

def test_get_scenarios():
    res = client.get("/api/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) >= 5
    ids = [s["id"] for s in scenarios]
    assert "wayanad_confirmed" in ids
    assert "brahmaputra_contested" in ids
    assert "thar_rejected" in ids

def test_end_to_end_analyze_confirmed():
    payload = {
        "query": "Did severe vegetation loss and slope failure occur in the Meppadi region between July and August 2024?",
        "scenario_id": "wayanad_confirmed",
        "t1": "2024-07-01",
        "t2": "2024-08-05"
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["arbiter_decision"]["verdict"] == "CONFIRMED"
    assert data["confidence_result"]["survival_score"] >= 0.60
    assert "optical_result" in data
    assert "sar_result" in data
    assert data["optical_result"]["pathway"] == "optical"
    assert data["sar_result"]["pathway"] == "sar"
    assert len(data["evidence_trace"]) >= 5
    assert "CONFIRMED" in data["plain_language_answer"]

def test_end_to_end_analyze_contested():
    payload = {
        "query": "Detect flood inundation and water spread along the river basin between June and July 2024.",
        "scenario_id": "brahmaputra_contested",
        "t1": "2024-06-15",
        "t2": "2024-07-10"
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["arbiter_decision"]["verdict"] == "CONTESTED"
    assert "cloud" in str(data["arbiter_decision"]["blind_spot_identified"]).lower()
    assert "CONTESTED" in data["plain_language_answer"]

def test_end_to_end_analyze_rejected():
    payload = {
        "query": "Did massive vegetation clearing occur in this desert sector?",
        "scenario_id": "thar_rejected",
        "t1": "2024-01-10",
        "t2": "2024-04-20"
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["arbiter_decision"]["verdict"] == "REJECTED"
    assert data["confidence_result"]["survival_score"] <= 0.20
    assert "REJECTED" in data["plain_language_answer"]
