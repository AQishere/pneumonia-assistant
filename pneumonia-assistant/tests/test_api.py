"""Every route through FastAPI's TestClient, on seeded demo data, with Stage 2 v2 (labs + symptoms)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from api import templates
from api.db import MemoryRepository
from api.main import create_app
from seed_demo_data import PATIENTS, demo_symptoms, seed
from tests.conftest import NOW

KEY = "test-key"
SIX_CONDITIONS = ("copd", "heart_failure", "renal", "asthma", "diabetes", "hypertension")


@pytest.fixture
def repo(predictor):
    r = MemoryRepository()
    seed(r, predictor, NOW)
    return r


@pytest.fixture
def client(repo, predictor):
    app = create_app(repo=repo, predictor=predictor, api_key=KEY, clock=lambda: NOW)
    return TestClient(app, headers={"X-API-Key": KEY})


def assess(client, pid, **override):
    """Assess a demo patient with its usual breathing and symptom answers."""
    body = {"respiratory_distress": PATIENTS[pid]["distress"], **demo_symptoms(pid), **override}
    return client.post(f"/patients/{pid}/assess", json={k: v for k, v in body.items() if v is not None}).json()


def test_api_key_or_sign_in_required(repo, predictor):
    app = create_app(repo=repo, predictor=predictor, api_key=KEY, clock=lambda: NOW)
    anon = TestClient(app)
    assert anon.get("/patients").status_code == 401
    assert anon.get("/patients", headers={"X-API-Key": "wrong"}).status_code == 401
    assert anon.get("/health").status_code == 200          # health is public: no patient data


def test_health(client):
    body = client.get("/health").json()
    assert body["model_version"].startswith("stage1:") and "stage2-v2" in body["model_version"]
    assert body["thresholds"] == {"stage1": 0.26, "stage2": 0.53}
    assert body["database"] == {"backend": "memory", "reachable": True}


def test_list_and_get_patient(client):
    ids = {p["patient_id"] for p in client.get("/patients").json()["patients"]}
    assert {"demo-healthy", "demo-sick"} <= ids
    body = client.get("/patients/demo-healthy").json()
    assert body["history_flags"] == {"copd": 0, "heart_failure": None, "renal": 0,
                                     "asthma": 0, "diabetes": 0, "hypertension": 0}
    assert body["history_flags_not_on_record"] == ["heart_failure"]
    assert all(4 <= n <= 6 for n in body["reading_counts"]["24h"].values())
    assert body["stage1_ready"] is True and body["missing_for_stage1"] == []
    assert body["alerts"] == [] and body["critical_notice"] is None
    assert body["labs"]["crp"] == 2.0 and set(body["latest_readings"]) == {
        "heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"}
    assert client.get("/patients/nope").status_code == 404


def test_get_patient_shows_alerts_and_stage1_gaps(client):
    body = client.get("/patients/demo-no-temp").json()
    assert [a["code"] for a in body["alerts"]] == ["LOW_SPO2"]
    assert body["critical_notice"] == templates.CRITICAL_NOTICE
    assert body["lead_text"] == f"{templates.CRITICAL_NOTICE} Blood oxygen (SpO2) dropped to 84% (below 90%)."
    assert body["stage1_ready"] is False and body["missing_for_stage1"] == ["temperature"]
    assert "temperature" in body["next_step"] and "device" in body["next_step"]
    # Sparse SBP is a Stage 2 gap only: Stage 1 is still ready.
    assert client.get("/patients/demo-sparse").json()["stage1_ready"] is True


SIGNUP = {"patient_id": "uid-abc123", "display_name": "New Patient", "age": 45, "sex": "female",
          "copd": 0, "heart_failure": 1, "renal": 0, "asthma": 1, "diabetes": 0, "hypertension": 0}


def test_signup_creates_patient_with_conditions(client):
    r = client.post("/patients", json=SIGNUP)
    assert r.status_code == 201
    body = r.json()
    assert body["history_flags"] == {k: SIGNUP[k] for k in SIX_CONDITIONS}
    assert (body["age"], body["sex"]) == (45, "female")
    # Conditions answered at signup: nothing for the agent to ask.
    assert client.get("/patients/uid-abc123").json()["history_flags_not_on_record"] == []
    assert client.post("/patients", json=SIGNUP).status_code == 409


def test_signup_requires_every_condition_answer(client):
    for missing in SIX_CONDITIONS:
        body = {k: v for k, v in SIGNUP.items() if k != missing}
        assert client.post("/patients", json=body).status_code == 422, missing
    assert client.post("/patients", json={**SIGNUP, "copd": None}).status_code == 422
    assert client.post("/patients", json={**SIGNUP, "age": 200}).status_code == 422


def test_profile_edit_adds_a_new_condition(client):
    client.post("/patients", json=SIGNUP)
    r = client.patch("/patients/uid-abc123", json={"copd": 1, "diabetes": 1, "age": 46})
    assert r.status_code == 200
    assert r.json()["history_flags"]["copd"] == 1 and r.json()["history_flags"]["diabetes"] == 1
    assert r.json()["age"] == 46
    assert client.patch("/patients/uid-abc123", json={}).status_code == 422
    assert client.patch("/patients/nobody", json={"age": 30}).status_code == 404


def test_add_readings_stores_valid_values(client, repo):
    before = len(repo.get_readings("demo-healthy", NOW - timedelta(days=30)))
    r = client.post("/patients/demo-healthy/readings", json={"readings": [
        {"vital": "temperature", "value": 101.3, "unit": "°F"},
        {"vital": "spo2", "value": 95, "taken_at": (NOW - timedelta(hours=1)).isoformat()},
    ]})
    assert r.status_code == 200 and r.json()["stored"] == 2
    assert len(repo.get_readings("demo-healthy", NOW - timedelta(days=30))) == before + 2


def test_add_readings_422_stores_nothing(client, repo):
    before = len(repo.get_readings("demo-healthy", NOW - timedelta(days=30)))
    r = client.post("/patients/demo-healthy/readings", json={"readings": [
        {"vital": "spo2", "value": 96},
        {"vital": "temperature", "value": 38.5},
        {"vital": "spo2", "value": 105},
    ]})
    assert r.status_code == 422
    body = r.json()
    assert body["stored"] == 0
    assert [(e["index"], e["code"]) for e in body["errors"]] == [(1, "LIKELY_CELSIUS"), (2, "OUT_OF_RANGE")]
    assert body["errors"][0]["suggested_value"] == 101.3
    assert len(repo.get_readings("demo-healthy", NOW - timedelta(days=30))) == before


def test_malformed_request_gives_structured_422(client):
    r = client.post("/patients/demo-healthy/readings", json={"readings": [{"vital": "glucose", "value": 5}]})
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "INVALID_REQUEST"


def test_update_flags_partial(client):
    r = client.put("/patients/demo-borderline/flags", json={"renal": 1, "asthma": 1})
    assert r.json()["history_flags"]["renal"] == 1 and r.json()["history_flags"]["asthma"] == 1
    assert client.put("/patients/demo-borderline/flags", json={}).status_code == 422
    assert client.put("/patients/demo-borderline/flags", json={"renal": 2}).status_code == 422


def test_upload_labs_and_validation(client, repo):
    r = client.post("/patients/demo-healthy/labs", json={"wbc": 9.1, "neutrophils": 70, "lymphocytes": 20, "crp": 12})
    assert r.status_code == 201
    assert repo.latest_labs("demo-healthy", NOW - timedelta(days=7))["crp"] == 12.0
    bad = client.post("/patients/demo-healthy/labs", json={"wbc": 900, "neutrophils": 80, "lymphocytes": 30, "crp": -1})
    assert bad.status_code == 422
    assert {e["field"] for e in bad.json()["errors"]} == {"wbc", "crp"}
    inconsistent = client.post("/patients/demo-healthy/labs",
                               json={"wbc": 9, "neutrophils": 80, "lymphocytes": 30, "crp": 5})
    assert inconsistent.json()["errors"][0]["code"] == "INCONSISTENT"


def test_assess_sick_is_high_with_alerts_first(client):
    body = assess(client, "demo-sick")
    assert (body["stage"], body["band"]) == (2, "High")
    assert body["recommendation"] == templates.RECOMMENDATIONS["High"]
    assert "LOW_SPO2" in {a["code"] for a in body["alerts"]}
    assert body["critical_notice"] == templates.CRITICAL_NOTICE
    assert body["lead_text"].startswith(templates.CRITICAL_NOTICE)
    assert body["windows"] == {"stage1": "24h", "stage2": "7d", "alerts": "24h", "hypoxemia": "7d"}
    assert body["disclaimer"] == templates.DISCLAIMER
    assert body["assessment_id"]


def test_assess_healthy_is_low_despite_null_flag(client):
    body = assess(client, "demo-healthy")
    assert (body["stage"], body["band"]) == (1, "Low")
    assert body["recommendation"] == templates.RECOMMENDATIONS["Low"]
    assert body["missing"] == [] and body["alerts"] == []
    assert body["lead_text"] is None


def test_low_needs_no_symptoms_or_labs(client):
    """Stage 1 Low never waits for Stage 2 inputs (symptoms, labs)."""
    body = client.post("/patients/demo-healthy/assess", json={"respiratory_distress": 0}).json()
    assert body["band"] == "Low" and body["missing"] == []


def test_flagged_without_symptom_answers_is_pending(client):
    body = assess(client, "demo-sick", cough=None, fever=None, weakness=None)
    assert (body["stage"], body["band"]) == (1, "Pending")
    assert [m["item"] for m in body["missing"]] == ["weakness"]
    assert all(m["type"] == "symptom" for m in body["missing"])


def test_flagged_without_recent_labs_is_pending(predictor):
    repo = MemoryRepository()
    seed(repo, predictor, NOW)
    later = NOW + timedelta(days=8)            # both seeded lab uploads are now older than 7 days
    client = TestClient(create_app(repo=repo, predictor=predictor, api_key=KEY, clock=lambda: later),
                        headers={"X-API-Key": KEY})
    client.post("/patients/demo-sick/readings", json={"readings": [
        {"vital": v, "value": x, "taken_at": (later - timedelta(hours=h)).isoformat()}
        for v, x in [("heart_rate", 118), ("respiratory_rate", 31), ("sbp", 96), ("spo2", 88),
                     ("temperature", 101.8)] for h in (1, 2)]})
    body = assess(client, "demo-sick")
    assert body["band"] == "Pending" and [m["item"] for m in body["missing"]] == ["labs"]


def test_assess_without_distress_is_missing(client, repo):
    n = len(repo.list_assessments("demo-healthy"))
    body = client.post("/patients/demo-healthy/assess", json={}).json()
    assert body["band"] is None and body["risk_score_stage1"] is None
    assert [m["item"] for m in body["missing"]] == ["respiratory_distress"]
    assert len(repo.list_assessments("demo-healthy")) == n      # nothing stored


def test_missing_stage1_input_still_returns_alert(client, repo):
    n = len(repo.list_assessments("demo-no-temp"))
    body = assess(client, "demo-no-temp")
    assert body["band"] is None and body["stage"] is None
    assert [m["item"] for m in body["missing"]] == ["temperature"]
    assert [a["code"] for a in body["alerts"]] == ["LOW_SPO2"]
    assert body["critical_notice"]
    assert len(repo.list_assessments("demo-no-temp")) == n


def test_no_spo2_is_missing(client):
    body = assess(client, "demo-no-spo2")
    assert body["band"] is None
    assert [m["item"] for m in body["missing"]] == ["spo2"]


def test_flagged_null_flag_is_pending_then_runs_after_answer(client, repo):
    body = assess(client, "demo-borderline")
    assert (body["stage"], body["band"]) == (1, "Pending")
    assert body["risk_score_stage2"] is None
    assert [m["item"] for m in body["missing"]] == ["renal"]
    assert body["recommendation"] == templates.RECOMMENDATIONS["Pending"]
    assert repo.list_assessments("demo-borderline")[0]["band"] == "Pending"   # stored: Stage 1 ran

    client.put("/patients/demo-borderline/flags", json={"renal": 0})
    body = assess(client, "demo-borderline")
    assert body["stage"] == 2 and body["band"] in ("Moderate", "Watch", "High")
    assert body["missing"] == []


def test_flagged_sparse_vital_is_pending_until_second_reading(client):
    body = assess(client, "demo-sparse")
    assert (body["stage"], body["band"]) == (1, "Pending")
    assert [(m["item"], m["have"], m["need"]) for m in body["missing"]] == [("sbp", 1, 2)]

    client.post("/patients/demo-sparse/readings", json={"readings": [
        {"vital": "sbp", "value": 106, "taken_at": (NOW - timedelta(hours=1)).isoformat()}]})
    body = assess(client, "demo-sparse")
    assert body["stage"] == 2 and body["band"] in ("Moderate", "Watch", "High")
    assert any(d["vital"] == "sbp" for d in body["data_quality"])     # 2 readings: still a warning


def test_old_low_spo2_no_alert_but_hypoxemia(client):
    body = assess(client, "demo-old-hypoxia")
    assert body["alerts"] == [] and body["critical_notice"] is None
    assert body["hypoxemia_derived"] == 1
    assert body["stage"] == 2


def test_critical_spo2_with_low_band(client):
    body = assess(client, "demo-low-spo2")
    assert body["band"] == "Low"
    assert [a["code"] for a in body["alerts"]] == ["LOW_SPO2"]
    assert body["critical_notice"]


def test_assessment_and_reading_history(client):
    assess(client, "demo-sick")
    rows = client.get("/patients/demo-sick/assessments?limit=3").json()["assessments"]
    assert len(rows) == 3
    assert rows[0]["band"] == "High" and rows[0]["stage"] == 2
    assert {"created_at", "risk_score_stage1", "risk_score_stage2", "alerts"} <= set(rows[0])
    assert client.get("/patients/demo-sick/assessments?limit=0").status_code == 422
    readings = client.get("/patients/demo-sick/readings?days=1").json()["readings"]
    assert readings and all(r["taken_at"] for r in readings)
