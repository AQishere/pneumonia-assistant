"""Phase 2: storage model and seed data (in-memory backend, same interface as Firestore)."""

from datetime import timedelta

import numpy as np
import pytest

from api.assessment import STAGE1_WINDOW, STAGE2_WINDOW, group_readings
from api.db import MemoryRepository, ensure_plain
from api.features import counts
from seed_demo_data import DAYS, PATIENTS, seed
from tests.conftest import NOW


@pytest.fixture(scope="module")
def seeded(predictor):
    repo = MemoryRepository()
    summary = seed(repo, predictor, NOW)
    return repo, summary


def test_seed_creates_every_demo_patient(seeded):
    repo, summary = seeded
    assert set(summary) == set(PATIENTS)
    assert {p["patient_id"] for p in repo.list_patients()} == set(PATIENTS)


def test_seeded_readings_cover_7_days_with_4_to_6_per_vital_per_day(seeded):
    repo, _ = seeded
    readings = repo.get_readings("demo-healthy", NOW - timedelta(days=30))
    for days_ago in range(DAYS):
        day = group_readings(readings, NOW - timedelta(days=days_ago + 1), NOW - timedelta(days=days_ago))
        assert all(4 <= n <= 6 for n in counts(day).values()), (days_ago, counts(day))


def test_24h_and_7d_counts(seeded):
    repo, _ = seeded
    readings = repo.get_readings("demo-healthy", NOW - STAGE2_WINDOW)
    c24 = counts(group_readings(readings, NOW - STAGE1_WINDOW, NOW))
    c7 = counts(group_readings(readings, NOW - STAGE2_WINDOW, NOW))
    assert all(4 <= n <= 6 for n in c24.values())
    assert all(DAYS * 4 <= n <= DAYS * 6 for n in c7.values())


def test_fixture_patients_have_their_gaps(seeded):
    repo, _ = seeded
    since = NOW - STAGE2_WINDOW
    assert counts(group_readings(repo.get_readings("demo-no-spo2", since), since, NOW))["spo2"] == 0
    r24 = group_readings(repo.get_readings("demo-no-temp", since), NOW - STAGE1_WINDOW, NOW)
    assert r24["temperature"] == [] and min(r24["spo2"]) == 84
    assert counts(group_readings(repo.get_readings("demo-sparse", since), since, NOW))["sbp"] == 1
    old = group_readings(repo.get_readings("demo-old-hypoxia", since), since, NOW - STAGE1_WINDOW)
    assert min(old["spo2"]) < 90


def test_unset_history_flags_read_back_as_null(seeded):
    repo, _ = seeded
    assert repo.get_patient("demo-healthy")["heart_failure"] is None
    assert repo.get_patient("demo-borderline")["renal"] is None
    assert repo.get_patient("demo-sick")["copd"] == 0


def test_seed_stores_daily_assessment_history(seeded):
    repo, _ = seeded
    history = repo.list_assessments("demo-sick")
    assert len(history) == DAYS - 1
    assert history[0]["created_at"] > history[-1]["created_at"]   # newest first


def test_numpy_types_never_reach_storage(seeded):
    repo, _ = seeded
    with pytest.raises(TypeError):
        ensure_plain({"p": np.float64(0.5)})
    with pytest.raises(TypeError):
        ensure_plain({"flags": [np.int64(1)]})
    with pytest.raises(TypeError):
        repo.add_readings("demo-healthy", [{"vital": "spo2", "value": np.float64(97),
                                            "taken_at": NOW, "entered_by": "doctor"}])
    # Everything the seed wrote passed the same check.
    for pid in PATIENTS:
        for a in repo.list_assessments(pid):
            ensure_plain(a)


def test_readings_are_stored_one_bucket_per_hour():
    from api.db import group_by_hour, hour_key
    t = NOW.replace(minute=0)
    readings = [{"vital": "spo2", "value": 97.0, "taken_at": t + timedelta(minutes=m), "entered_by": "device"}
                for m in range(0, 120)]                       # one reading a minute for 2 hours
    buckets = group_by_hour(readings)
    assert list(buckets) == [hour_key(t), hour_key(t + timedelta(hours=1))]
    assert [len(v) for v in buckets.values()] == [60, 60]
    assert hour_key(t) == "2026-10-17T12"


def test_bucketed_readings_read_back_with_exact_window(predictor):
    repo = MemoryRepository()
    repo.create_patient("p1", "Test", {"copd": 0, "heart_failure": 0, "renal": 0}, NOW)
    t = NOW - timedelta(hours=2)
    repo.add_readings("p1", [{"vital": "heart_rate", "value": float(70 + m), "entered_by": "device",
                              "taken_at": t + timedelta(minutes=m)} for m in range(90)])
    # Window starts mid-hour: only readings at or after `since` come back, oldest first.
    rows = repo.get_readings("p1", t + timedelta(minutes=30))
    assert len(rows) == 60 and rows[0]["value"] == 100.0 and rows[-1]["value"] == 159.0
    assert all(type(r["value"]) is float for r in rows)


def test_profile_fields_stored(predictor):
    repo = MemoryRepository()
    repo.create_patient("p1", "Test", {"copd": 1, "heart_failure": 0, "renal": 0}, NOW,
                        age=60, sex="female", doctor_ids=["dr-1"])
    p = repo.get_patient("p1")
    assert (p["age"], p["sex"], p["doctor_ids"], p["copd"]) == (60, "female", ["dr-1"], 1)
    repo.update_patient("p1", {"heart_failure": 1, "age": 61})
    p = repo.get_patient("p1")
    assert (p["heart_failure"], p["age"], p["copd"]) == (1, 61, 1)


def test_reseeding_replaces_demo_patients(predictor):
    repo = MemoryRepository()
    seed(repo, predictor, NOW)
    first = len(repo.get_readings("demo-sick", NOW - timedelta(days=30)))
    seed(repo, predictor, NOW)
    assert len(repo.get_readings("demo-sick", NOW - timedelta(days=30))) == first
