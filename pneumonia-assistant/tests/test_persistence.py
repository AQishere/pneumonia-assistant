"""Persistence rule: a positive Stage 2 result becomes High only if very confident or repeated."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from api import templates
from api.assessment import persistence
from api.db import MemoryRepository
from api.main import create_app
from seed_demo_data import demo_symptoms, seed
from tests.conftest import NOW

THR = 0.5


def record(hours_ago, positive=True, stage=2, **extra):
    return {"created_at": NOW - timedelta(hours=hours_ago), "stage": stage,
            "stage2_positive": positive, **extra}


def test_very_confident_result_is_high_immediately():
    band, info = persistence(0.85, THR, [], NOW)
    assert (band, info["status"]) == ("High", "immediate")


def test_first_positive_is_watch_with_reassessment_window():
    band, info = persistence(0.60, THR, [], NOW)
    assert (band, info["status"]) == ("Watch", "first_positive")
    assert info["reassess_after"] == NOW + timedelta(hours=4)
    assert info["reassess_before"] == NOW + timedelta(hours=36)


def test_repeat_positive_confirms_high():
    band, info = persistence(0.60, THR, [record(6)], NOW)
    assert (band, info["status"]) == ("High", "confirmed")
    assert info["confirmed_by"] == NOW - timedelta(hours=6)


@pytest.mark.parametrize("hours_ago", [0.5, 3.9, 36.5, 72])
def test_previous_positive_too_recent_or_too_old_does_not_confirm(hours_ago):
    assert persistence(0.60, THR, [record(hours_ago)], NOW)[0] == "Watch"


def test_most_recent_eligible_assessment_decides():
    # Positive 20 h ago, but negative 6 h ago: not a persistent positive.
    history = [record(20), record(6, positive=False)]
    assert persistence(0.60, THR, history, NOW)[0] == "Watch"


def test_stage1_only_records_do_not_confirm():
    assert persistence(0.60, THR, [record(6, stage=1)], NOW)[0] == "Watch"


def test_older_records_without_the_flag_use_their_band():
    legacy = {"created_at": NOW - timedelta(hours=8), "stage": 2, "band": "High"}
    assert persistence(0.60, THR, [legacy], NOW)[0] == "High"


def test_full_flow_watch_then_confirmed_high(predictor):
    """Same patient assessed now (Watch), 2 h later (still Watch: no new data), 6 h later (High)."""
    repo = MemoryRepository()
    seed(repo, predictor, NOW)
    # A copy of demo-old-hypoxia (Stage 2 v2 score ~0.54) with no assessment history.
    src = repo.get_patient("demo-old-hypoxia")
    repo.create_patient("p-watch", "Persistence check", src, NOW, age=src["age"], sex=src["sex"])
    repo.add_readings("p-watch", [{k: r[k] for k in ("vital", "value", "taken_at", "entered_by")}
                                  for r in repo.get_readings("demo-old-hypoxia", NOW - timedelta(days=8))])
    lab = repo.latest_labs("demo-old-hypoxia", NOW - timedelta(days=7))
    repo.add_labs("p-watch", {k: lab[k] for k in ("wbc", "neutrophils", "lymphocytes", "crp", "taken_at")})
    answers = {"respiratory_distress": 1, **demo_symptoms("demo-old-hypoxia")}
    clock = {"now": NOW}
    app = create_app(repo=repo, predictor=predictor, api_key="k", clock=lambda: clock["now"])
    client = TestClient(app, headers={"X-API-Key": "k"})

    first = client.post("/patients/p-watch/assess", json=answers).json()
    assert (first["stage"], first["band"]) == (2, "Watch")
    assert first["persistence"]["status"] == "first_positive"
    assert first["recommendation"] == templates.RECOMMENDATIONS["Watch"]
    assert first["missing"] == []

    clock["now"] = NOW + timedelta(hours=2)
    soon = client.post("/patients/p-watch/assess", json=answers).json()
    assert soon["band"] == "Watch"                     # a repeat 2 h later can't confirm

    clock["now"] = NOW + timedelta(hours=6)
    later = client.post("/patients/p-watch/assess", json=answers).json()
    assert (later["band"], later["persistence"]["status"]) == ("High", "confirmed")
    assert later["recommendation"] == templates.RECOMMENDATIONS["High"]


def test_alerts_are_not_delayed_by_persistence(predictor):
    repo = MemoryRepository()
    seed(repo, predictor, NOW)
    client = TestClient(create_app(repo=repo, predictor=predictor, api_key="k", clock=lambda: NOW),
                        headers={"X-API-Key": "k"})
    body = client.post("/patients/demo-sick/assess",
                       json={"respiratory_distress": 1, **demo_symptoms("demo-sick")}).json()
    assert body["band"] == "High" and body["critical_notice"]
