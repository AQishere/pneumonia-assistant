"""Readings -> model features, plus the per-stage input checks.

Feature logic matches the notebook's assess(): mean/min/max and sample std
(ddof=1) per vital. One difference on purpose: with a single reading the std
is None, never 0.0. The spread features were never zero in training, so Stage 2
requires at least two readings per vital instead.
"""

import numpy as np

from api.validation import VITALS

HISTORY_FLAGS = ("copd", "heart_failure", "renal")          # used by the original Stage 2 model
CONDITIONS = (*HISTORY_FLAGS, "asthma", "diabetes", "hypertension")   # all asked at signup
SYMPTOMS = ("cough", "fever", "weakness")                   # reported by the patient per assessment
STAGE2_SYMPTOMS = ("weakness",)                             # the only symptom answer Stage 2 v2 uses
LAB_FIELDS = ("wbc", "neutrophils", "lymphocytes", "crp")   # uploaded lab results

STAGE1_MIN_READINGS = 1   # per vital, last 24 h (Stage 1 uses no std features)
STAGE2_MIN_READINGS = 2   # per vital, last 7 days
LOW_COUNT_WARNING = 3     # fewer than this adds a data_quality warning

VITAL_NAMES = {
    "heart_rate": "heart rate",
    "respiratory_rate": "respiratory rate",
    "sbp": "systolic BP",
    "spo2": "SpO2",
    "temperature": "temperature",
}
FLAG_NAMES = {"copd": "COPD", "heart_failure": "heart failure", "renal": "kidney disease",
              "asthma": "asthma", "diabetes": "diabetes", "hypertension": "high blood pressure"}
SYMPTOM_NAMES = {"cough": "a cough", "fever": "feeling feverish", "weakness": "unusual weakness or tiredness"}


def build_features(readings: dict[str, list[float]], flags: dict) -> dict:
    """Feature dict for every vital that has readings, merged with the flags."""
    f = {k: int(v) for k, v in flags.items()}
    for vital in VITALS:
        values = readings.get(vital) or []
        if not values:
            continue
        a = np.asarray(values, dtype=float)
        f[f"{vital}_mean"] = float(a.mean())
        f[f"{vital}_min"] = float(a.min())
        f[f"{vital}_max"] = float(a.max())
        f[f"{vital}_std"] = float(a.std(ddof=1)) if len(a) >= 2 else None
    return f


def counts(readings: dict[str, list[float]]) -> dict[str, int]:
    return {v: len(readings.get(v) or []) for v in VITALS}


def _missing_readings(readings, need, stage, window) -> list[dict]:
    out = []
    for vital, have in counts(readings).items():
        if have < need:
            if have == 0:
                msg = f"No {VITAL_NAMES[vital]} reading in the last {window}."
            else:
                msg = (f"Only {have} {VITAL_NAMES[vital]} reading(s) in the last {window}; "
                       f"Stage {stage} needs at least {need}.")
            out.append({"item": vital, "type": "reading", "stage": stage, "window": window,
                        "have": have, "need": need, "message": msg})
    return out


def missing_stage1(readings_24h: dict, respiratory_distress: int | None) -> list[dict]:
    out = _missing_readings(readings_24h, STAGE1_MIN_READINGS, 1, "24h")
    if respiratory_distress is None:
        out.append({"item": "respiratory_distress", "type": "input", "stage": 1,
                    "message": "Respiratory distress (yes/no) was not provided."})
    return out


def missing_stage2(readings_7d: dict, history: dict) -> list[dict]:
    out = _missing_readings(readings_7d, STAGE2_MIN_READINGS, 2, "7d")
    for flag in HISTORY_FLAGS:
        if history.get(flag) is None:
            out.append({"item": flag, "type": "history_flag", "stage": 2,
                        "message": f"{FLAG_NAMES[flag]} history is not on record."})
    return out


def missing_stage2_v2(readings_7d: dict, profile: dict, symptoms: dict, labs: dict | None) -> list[dict]:
    """Stage 2 v2 inputs: readings, the full profile, today's symptoms and recent lab results."""
    out = _missing_readings(readings_7d, STAGE2_MIN_READINGS, 2, "7d")
    for flag in CONDITIONS:
        if profile.get(flag) is None:
            out.append({"item": flag, "type": "history_flag", "stage": 2,
                        "message": f"{FLAG_NAMES[flag]} history is not on record."})
    for field, label in (("age", "Age"), ("sex", "Sex")):
        if profile.get(field) is None:
            out.append({"item": field, "type": "profile", "stage": 2, "message": f"{label} is not on record."})
    for s in STAGE2_SYMPTOMS:
        if symptoms.get(s) is None:
            out.append({"item": s, "type": "symptom", "stage": 2,
                        "message": f"Not answered yet: does the patient have {SYMPTOM_NAMES[s]}?"})
    if labs is None or any(labs.get(k) is None for k in LAB_FIELDS):
        out.append({"item": "labs", "type": "labs", "stage": 2,
                    "message": "No complete lab results (WBC, neutrophils, lymphocytes, CRP) "
                               "from the last 7 days."})
    return out


def data_quality(readings: dict, window: str, stage: int) -> list[dict]:
    out = []
    for vital, have in counts(readings).items():
        if 0 < have < LOW_COUNT_WARNING:
            out.append({"vital": vital, "stage": stage, "window": window, "count": have,
                        "message": f"Only {have} {VITAL_NAMES[vital]} reading(s) in the last "
                                   f"{window} for Stage {stage}; the result is less reliable."})
    return out
