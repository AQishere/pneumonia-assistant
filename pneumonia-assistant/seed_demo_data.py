"""Create the demo patients: 7 days of readings, 4 to 6 per vital per day.

Demo data only: no real or MIMIC patient records. Readings are generated
deterministically relative to "now", and one assessment per past day is stored
so the risk trend has history.

Usage (uses DB_BACKEND / FIREBASE_* from .env):
    python seed_demo_data.py
"""

import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from api.assessment import assess
from api.predictor import Predictor
from api.validation import RANGES, VITALS

DAYS = 7


def steady(**vitals):
    """Same (mean, sd) every day."""
    return lambda vital, days_ago: vitals[vital]


def worsening(before: dict, after: dict, from_days_ago: int):
    """`before` until `from_days_ago`, then `after` for the most recent days."""
    return lambda vital, days_ago: (after if days_ago < from_days_ago else before)[vital]


NORMAL = dict(heart_rate=(76, 4), respiratory_rate=(15, 1.2), sbp=(124, 5),
              spo2=(98, 0.8), temperature=(98.4, 0.25))

# Each patient: display name, history flags (None = never asked), the respiratory
# distress answer used for the seeded daily assessments, a vital-sign profile and
# optional special cases. Several patients exist only for agent test scenarios.
PATIENTS = {
    "demo-healthy": dict(
        name="Demo Patient 1 (healthy)",
        flags={"copd": 0, "heart_failure": None, "renal": 0},   # null flag: scenario 15
        distress=0, profile=steady(**NORMAL)),
    "demo-sick": dict(
        name="Demo Patient 2 (sick)",
        flags={"copd": 0, "heart_failure": 0, "renal": 0},
        distress=1,
        profile=worsening(
            dict(NORMAL, heart_rate=(82, 4), respiratory_rate=(16, 1.2), temperature=(98.7, 0.3)),
            dict(heart_rate=(118, 6), respiratory_rate=(31, 2), sbp=(96, 5),
                 spo2=(88, 1.5), temperature=(101.8, 0.5)),
            from_days_ago=3)),
    "demo-borderline": dict(
        name="Demo Patient 3 (borderline)",
        flags={"copd": 0, "heart_failure": 0, "renal": None},   # null flag: scenario 12
        distress=1,
        profile=steady(heart_rate=(84, 5), respiratory_rate=(18, 1.5), sbp=(120, 6),
                       spo2=(96, 1), temperature=(98.7, 0.3))),
    "demo-copd": dict(
        name="Demo Patient 4 (COPD, low SpO2)",
        flags={"copd": 1, "heart_failure": 0, "renal": 0},
        distress=1,
        profile=steady(heart_rate=(94, 5), respiratory_rate=(23, 2), sbp=(122, 6),
                       spo2=(90, 1.2), temperature=(99.2, 0.4))),
    "demo-old-hypoxia": dict(
        name="Demo Patient 5 (low SpO2 five days ago)",
        flags={"copd": 0, "heart_failure": 0, "renal": 0},
        distress=1,
        profile=steady(heart_rate=(86, 4), respiratory_rate=(18, 1.2), sbp=(120, 5),
                       spo2=(96, 0.8), temperature=(98.9, 0.3)),
        extra=[("spo2", 5 * 24, 86.0), ("spo2", 5 * 24 - 2, 85.0)]),
    "demo-low-spo2": dict(
        name="Demo Patient 6 (one critical SpO2 today)",
        flags={"copd": 0, "heart_failure": 0, "renal": 0},
        distress=0, profile=steady(**NORMAL),
        extra=[("spo2", 3, 84.0)]),                              # scenario 10
    "demo-no-spo2": dict(
        name="Demo Patient 7 (no SpO2 readings)",
        flags={"copd": 0, "heart_failure": 0, "renal": 0},
        distress=0, profile=steady(**NORMAL),
        skip={"spo2"}),                                          # scenario 5
    "demo-no-temp": dict(
        name="Demo Patient 8 (no temperature today, critical SpO2)",
        flags={"copd": 0, "heart_failure": 0, "renal": 0},
        distress=0, profile=steady(**NORMAL),
        skip_recent={"temperature"}, extra=[("spo2", 2, 84.0)]), # scenario 16
    "demo-sparse": dict(
        name="Demo Patient 9 (one SBP reading in 7 days)",
        flags={"copd": 0, "heart_failure": 0, "renal": 0},
        distress=1,
        profile=steady(heart_rate=(104, 5), respiratory_rate=(26, 2), sbp=(108, 5),
                       spo2=(92, 1), temperature=(100.6, 0.4)),
        single={"sbp"}),                                         # scenario 13
}


# Made-up profile details for the demo patients (the models don't use age or sex).
DEMO_PROFILES = {
    "demo-healthy": (34, "female"), "demo-sick": (71, "male"), "demo-borderline": (58, "female"),
    "demo-copd": (66, "male"), "demo-old-hypoxia": (49, "female"), "demo-low-spo2": (42, "male"),
    "demo-no-spo2": (29, "female"), "demo-no-temp": (55, "male"), "demo-sparse": (63, "female"),
}


# Made-up labs (WBC 10^9/L, neutrophils %, lymphocytes %, CRP mg/L), symptom answers
# (cough, fever, weakness) and the extra conditions asked at signup.
DEMO_HEALTH = {
    "demo-healthy":     dict(labs=(6.8, 58, 32, 2), symptoms=(0, 0, 0), conditions={}),
    "demo-sick":        dict(labs=(16.5, 88, 6, 160), symptoms=(1, 1, 1),
                             conditions={"diabetes": 1, "hypertension": 1}),
    "demo-borderline":  dict(labs=(10.5, 76, 14, 35), symptoms=(1, 0, 0), conditions={}),
    "demo-copd":        dict(labs=(12.0, 80, 11, 55), symptoms=(1, 0, 1), conditions={"hypertension": 1}),
    "demo-old-hypoxia": dict(labs=(11.5, 80, 11, 70), symptoms=(1, 0, 1), conditions={}),
    "demo-low-spo2":    dict(labs=(7.0, 60, 30, 3), symptoms=(0, 0, 0), conditions={}),
    "demo-no-spo2":     dict(labs=(6.5, 57, 33, 2), symptoms=(0, 0, 0), conditions={}),
    "demo-no-temp":     dict(labs=(7.2, 61, 29, 4), symptoms=(0, 0, 0), conditions={}),
    "demo-sparse":      dict(labs=(13.5, 83, 9, 90), symptoms=(1, 1, 0), conditions={}),
}
LAB_TIMES = (timedelta(days=6, hours=12), timedelta(hours=12))   # two uploads: last week and today


def demo_symptoms(pid: str) -> dict:
    return dict(zip(("cough", "fever", "weakness"), DEMO_HEALTH[pid]["symptoms"]))


def _labs_as_of(labs: list[dict], as_of: datetime) -> dict | None:
    usable = [l for l in labs if as_of - timedelta(days=7) <= l["taken_at"] <= as_of]
    return max(usable, key=lambda l: l["taken_at"]) if usable else None


def _round(vital: str, value: float) -> float:
    lo, hi = RANGES[vital]
    value = min(max(value, lo), hi)
    return round(value, 1) if vital == "temperature" else float(round(value))


def generate_readings(patient_id: str, spec: dict, now: datetime) -> list[dict]:
    rng = random.Random(patient_id)   # deterministic per patient
    skip, skip_recent, single = (spec.get(k, set()) for k in ("skip", "skip_recent", "single"))
    out = []
    for days_ago in range(DAYS - 1, -1, -1):
        day_start = now - timedelta(days=days_ago + 1)
        for vital in VITALS:
            if vital in skip or vital in single or (days_ago == 0 and vital in skip_recent):
                continue
            mean, sd = spec["profile"](vital, days_ago)
            n = rng.randint(4, 6)
            for i in range(n):
                # Spread across the day, never later than now.
                t = day_start + timedelta(hours=24 * (i + 0.5) / n + rng.uniform(-0.5, 0.5))
                out.append({"vital": vital, "value": _round(vital, rng.gauss(mean, sd)),
                            "taken_at": min(t, now - timedelta(minutes=5)), "entered_by": "seed"})
    for vital in single:
        mean, _ = spec["profile"](vital, 0)
        out.append({"vital": vital, "value": _round(vital, mean),
                    "taken_at": now - timedelta(hours=4), "entered_by": "seed"})
    for vital, hours_ago, value in spec.get("extra", []):
        out.append({"vital": vital, "value": value,
                    "taken_at": now - timedelta(hours=hours_ago), "entered_by": "seed"})
    return out


def seed(repo, predictor: Predictor, now: datetime | None = None) -> dict:
    """Replace the demo patients in `repo`. Returns {patient_id: reading count}."""
    now = now or datetime.now(timezone.utc)
    summary = {}
    for pid, spec in PATIENTS.items():
        repo.delete_patient(pid)
        age, sex = DEMO_PROFILES[pid]
        health = DEMO_HEALTH[pid]
        flags = {"asthma": 0, "diabetes": 0, "hypertension": 0, **health["conditions"], **spec["flags"]}
        repo.create_patient(pid, spec["name"], flags, now - timedelta(days=DAYS), age=age, sex=sex)
        readings = generate_readings(pid, spec, now)
        repo.add_readings(pid, readings)
        labs = [dict(zip(("wbc", "neutrophils", "lymphocytes", "crp"), map(float, health["labs"])),
                     taken_at=now - ago, entered_by="seed") for ago in LAB_TIMES]
        for lab in labs:
            repo.add_labs(pid, lab)
        profile = repo.get_patient(pid)
        # One stored assessment per past day, as the daily job would have made.
        for days_ago in range(DAYS - 1, 0, -1):
            as_of = now - timedelta(days=days_ago)
            outcome = assess(readings, profile, spec["distress"], None, predictor, as_of,
                             previous=repo.list_assessments(pid, 10), symptoms=demo_symptoms(pid),
                             labs=_labs_as_of(labs, as_of))
            if outcome.record:
                repo.add_assessment(pid, outcome.record)
        summary[pid] = len(readings)
    return summary


if __name__ == "__main__":
    load_dotenv()
    from api.assessment import STAGE1_WINDOW, STAGE2_WINDOW
    from api.db import repository_from_env

    repo = repository_from_env()
    print(f"Seeding demo patients into: {repo.backend}")
    now = datetime.now(timezone.utc)
    summary = seed(repo, Predictor(), now)
    # Read everything back, so a successful run proves writes and queries both work.
    print(f"\n{'patient':18s} {'written':>7s} {'read 24h':>8s} {'read 7d':>7s} {'assessments':>11s}")
    for pid, n in summary.items():
        r24 = len(repo.get_readings(pid, now - STAGE1_WINDOW))
        r7 = len(repo.get_readings(pid, now - STAGE2_WINDOW))
        print(f"{pid:18s} {n:7d} {r24:8d} {r7:7d} {len(repo.list_assessments(pid)):11d}")
