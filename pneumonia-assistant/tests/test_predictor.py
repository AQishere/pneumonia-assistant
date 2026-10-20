"""Phase 1: the app must reproduce the notebook's assess() exactly."""

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from api import templates
from api.assessment import assess, display_score
from api.features import build_features
from api.predictor import Predictor
from tests.conftest import DATA_DIR, HEALTHY, NO_HISTORY, NOW, SICK, as_readings


@pytest.fixture(scope="module")
def predictor():
    """These parity tests check the ORIGINAL Stage 2 model against the notebook."""
    return Predictor(stage2_file="stage2.joblib")


def notebook_assess(predictor, readings, flags):
    """Copy of the notebook's assess() (cell 12), used as the reference."""
    f = dict(flags)
    for v in ["heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"]:
        a = np.asarray(readings[v], dtype=float)
        f[f"{v}_mean"], f[f"{v}_min"], f[f"{v}_max"] = a.mean(), a.min(), a.max()
        f[f"{v}_std"] = a.std(ddof=1) if len(a) > 1 else 0.0
    row = pd.DataFrame([f])
    s1, s2 = predictor.stage1, predictor.stage2
    p1 = s1["model"].predict_proba(row[s1["features"]])[0, 1]
    if p1 < s1["threshold"]:
        return {"stage": 1, "p_stage1": p1}
    p2 = s2["model"].predict_proba(row[s2["features"]])[0, 1]
    return {"stage": 2, "p_stage1": p1, "p_stage2": p2}


def run_app(predictor, values, history, distress, hypoxemia=None, extra=()):
    readings = as_readings(values) + list(extra)
    return assess(readings, history, distress, hypoxemia, predictor, NOW).response


def test_sick_patient_matches_notebook(predictor):
    r = run_app(predictor, SICK, {"copd": 1, "heart_failure": 0, "renal": 0}, 1, hypoxemia=1)
    assert (r["stage"], r["band"]) == (2, "High")
    assert r["risk_score_stage1"] == 0.85
    assert r["risk_score_stage2"] == 0.95


def test_healthy_patient_matches_notebook(predictor):
    r = run_app(predictor, HEALTHY, NO_HISTORY, 0, hypoxemia=0)
    assert (r["stage"], r["band"]) == (1, "Low")
    assert r["risk_score_stage1"] == 0.113


def test_exact_parity_on_random_patients(predictor):
    """Unrounded scores equal the notebook's on many random in-24h patients."""
    rng = np.random.default_rng(0)
    for _ in range(50):
        values = {
            "heart_rate": rng.normal(95, 15, 4).round(), "respiratory_rate": rng.normal(22, 5, 4).round(),
            "sbp": rng.normal(115, 15, 4).round(), "spo2": rng.normal(93, 3, 4).clip(80, 100).round(),
            "temperature": rng.normal(99.5, 1.2, 4).round(1),
        }
        history = {k: int(rng.integers(0, 2)) for k in ("copd", "heart_failure", "renal")}
        distress = int(rng.integers(0, 2))
        hypoxemia = int(values["spo2"].min() < 90)
        ref = notebook_assess(predictor, values, {"respiratory_distress": distress,
                                                  "hypoxemia": hypoxemia, **history})
        out = assess(as_readings(values), history, distress, None, predictor, NOW).record
        assert out["stage"] == ref["stage"]
        assert out["p_stage1"] == pytest.approx(ref["p_stage1"], abs=1e-12)
        if ref["stage"] == 2:
            assert out["p_stage2"] == pytest.approx(ref["p_stage2"], abs=1e-12)


def test_lower_spo2_strictly_increases_p1(predictor):
    scores = []
    for low in [96, 92, 88, 84]:
        f = build_features(dict(HEALTHY, spo2=[98, 97, low, 96]), {"respiratory_distress": 0})
        scores.append(predictor.run(f)["p_stage1"])
    assert scores == sorted(scores) and len(set(scores)) == 4
    assert [round(s, 3) for s in scores] == [0.116, 0.13, 0.145, 0.161]   # notebook check 3


def test_batch_auc_on_test_set(predictor):
    test = pd.read_csv(DATA_DIR / "test_clean.csv")
    y = test["pneumonia_label"]
    s1, s2 = predictor.stage1, predictor.stage2
    auc1 = roc_auc_score(y, s1["model"].predict_proba(test[s1["features"]])[:, 1]) * 100
    auc2 = roc_auc_score(y, s2["model"].predict_proba(test[s2["features"]])[:, 1]) * 100
    assert abs(auc1 - 78.2) < 0.1
    assert abs(auc2 - 79.7) < 0.1


def test_outputs_are_plain_python_floats(predictor):
    rec = run_app(predictor, SICK, NO_HISTORY, 1)
    out = assess(as_readings(SICK), NO_HISTORY, 1, None, predictor, NOW).record
    assert type(out["p_stage1"]) is float and type(out["p_stage2"]) is float
    assert all(type(v) in (float, int) for v in out["features_stage2"].values())
    assert rec["model_version"].startswith("stage1:")


# --- Time windows -----------------------------------------------------------

def test_old_high_heart_rate_changes_stage2_only(predictor):
    old = [{"vital": "heart_rate", "value": 160.0, "entered_by": "seed",
            "taken_at": NOW - timedelta(days=5)}]
    base = assess(as_readings(SICK), NO_HISTORY, 1, None, predictor, NOW).record
    with_old = assess(as_readings(SICK) + old, NO_HISTORY, 1, None, predictor, NOW).record
    assert with_old["features_stage1"]["heart_rate_max"] == base["features_stage1"]["heart_rate_max"] == 124
    assert base["features_stage2"]["heart_rate_max"] == 124
    assert with_old["features_stage2"]["heart_rate_max"] == 160


def test_old_low_spo2_sets_hypoxemia_without_alert(predictor):
    old = [{"vital": "spo2", "value": 84.0, "entered_by": "seed", "taken_at": NOW - timedelta(days=5)}]
    r = run_app(predictor, HEALTHY, NO_HISTORY, 0, extra=old)
    assert r["alerts"] == [] and r["critical_notice"] is None
    assert r["hypoxemia_derived"] == 1


def test_readings_older_than_7_days_are_ignored(predictor):
    ancient = [{"vital": "heart_rate", "value": 200.0, "entered_by": "seed",
                "taken_at": NOW - timedelta(days=8)}]
    rec = assess(as_readings(SICK) + ancient, NO_HISTORY, 1, None, predictor, NOW).record
    assert rec["features_stage2"]["heart_rate_max"] == 124


# --- Stage-by-stage input checks ---------------------------------------------

def test_one_reading_in_7_days_is_missing_for_stage2_not_std_zero(predictor):
    values = dict(SICK, sbp=[88])
    r = run_app(predictor, values, NO_HISTORY, 1)
    assert (r["stage"], r["band"]) == (1, "Pending")
    assert r["risk_score_stage2"] is None
    assert [m["item"] for m in r["missing"]] == ["sbp"]
    assert r["missing"][0]["have"] == 1 and r["missing"][0]["need"] == 2


def test_flagged_with_null_history_flag_is_pending(predictor):
    r = run_app(predictor, SICK, {"copd": 1, "heart_failure": None, "renal": 0}, 1)
    assert (r["stage"], r["band"]) == (1, "Pending")
    assert r["recommendation"] == templates.RECOMMENDATIONS["Pending"]
    assert [m["item"] for m in r["missing"]] == ["heart_failure"]


def test_low_with_null_history_flag_ignores_stage2_gaps(predictor):
    r = run_app(predictor, dict(HEALTHY, sbp=[125]), {"copd": None, "heart_failure": None, "renal": None}, 0)
    assert (r["stage"], r["band"]) == (1, "Low")
    assert r["missing"] == []


def test_predictor_pending_and_low_without_stage2_features(predictor):
    sick = build_features(SICK, {"respiratory_distress": 1})
    healthy = build_features(HEALTHY, {"respiratory_distress": 0})
    assert predictor.run(sick, None)["band"] == "Pending"
    assert predictor.run(healthy, None)["band"] == "Low"


def test_stage1_inputs_missing_still_returns_alerts(predictor):
    values = {k: v for k, v in SICK.items() if k != "temperature"}
    out = assess(as_readings(values), NO_HISTORY, 1, None, predictor, NOW)
    r = out.response
    assert out.record is None
    assert r["stage"] is None and r["band"] is None and r["risk_score_stage1"] is None
    assert [m["item"] for m in r["missing"]] == ["temperature"]
    assert "LOW_SPO2" in {a["code"] for a in r["alerts"]}
    assert r["critical_notice"] == templates.CRITICAL_NOTICE


def test_missing_respiratory_distress_blocks_stage1(predictor):
    r = run_app(predictor, HEALTHY, NO_HISTORY, None)
    assert r["band"] is None
    assert [m["item"] for m in r["missing"]] == ["respiratory_distress"]


def test_data_quality_warning_for_fewer_than_3_readings(predictor):
    r = run_app(predictor, dict(HEALTHY, heart_rate=[72, 78]), NO_HISTORY, 0)
    assert r["band"] == "Low"
    assert [(d["vital"], d["count"]) for d in r["data_quality"]] == [("heart_rate", 2)]


def test_display_score_never_rounds_across_threshold():
    assert display_score(0.2599, 0.26) == 0.259
    assert display_score(0.26, 0.26) == 0.26
    assert display_score(0.4996, 0.5) == 0.499
    assert display_score(0.8504, 0.26) == 0.85
