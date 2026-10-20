"""Stage 2 v2 features: all vital statistics, engineered vitals, profile, symptoms and labs.

Shared by training (training/train_stage2_v2.py) and, later, the API, so both
compute features identically. Works on a DataFrame with one row per patient.
"""

import numpy as np
import pandas as pd

VITALS = ["heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"]

# spo2_max is not used: it was 100 for every patient in the training data.
VITAL_STATS = [f"{v}_{s}" for v in VITALS for s in ("mean", "min", "max", "std") if f"{v}_{s}" != "spo2_max"]
ENGINEERED = ["shock_index", "news_vitals", "fever_measured", "spo2_drop", "heart_rate_range",
              "respiratory_rate_range", "sbp_range", "temperature_range"]
PROFILE = ["age", "gender_male", "copd", "asthma", "diabetes", "hypertension", "heart_failure", "renal"]
# cough and fever are not used: they were recorded for only 1-2% of training patients, so the model
# learned nothing from them. Fever is covered by temperature, breathing by respiratory_distress.
SYMPTOMS = ["weakness", "hypoxemia"]
LABS = ["wbc", "neutrophils", "lymphocytes", "nlr", "crp"]

FEATURES = VITAL_STATS + ENGINEERED + ["respiratory_distress"] + PROFILE + SYMPTOMS + LABS
BINARY = {"respiratory_distress", "gender_male", "copd", "asthma", "diabetes", "hypertension", "heart_failure",
          "renal", "weakness", "hypoxemia", "fever_measured"}

WBC_CAP = 100.0   # values above this in the training data are artefacts (max was 471.7)


def _points(x: float, bands: list[tuple[float, int]]) -> int:
    for upper, pts in bands:
        if x <= upper:
            return pts
    return bands[-1][1]


def add_lab_features(df: pd.DataFrame) -> pd.DataFrame:
    """Lab values as given (NaN = not measured), WBC capped, plus the neutrophil-lymphocyte ratio."""
    df = df.copy()
    df["wbc"] = df["wbc"].clip(upper=WBC_CAP)
    df["nlr"] = df["neutrophils"] / df["lymphocytes"].replace(0, np.nan)
    return df


def add_engineered(df: pd.DataFrame) -> pd.DataFrame:
    """NEWS2-style vital points, shock index, measured fever, SpO2 drop and per-vital ranges."""
    df = df.copy()
    df["shock_index"] = df.heart_rate_max / df.sbp_min
    t_max_c = (df.temperature_max - 32) * 5 / 9
    t_min_c = (df.temperature_min - 32) * 5 / 9
    rr = df.respiratory_rate_max.map(lambda v: _points(v, [(8, 3), (11, 1), (20, 0), (24, 2), (999, 3)]))
    sp = df.spo2_min.map(lambda v: _points(v, [(91, 3), (93, 2), (95, 1), (999, 0)]))
    bp = df.sbp_min.map(lambda v: _points(v, [(90, 3), (100, 2), (110, 1), (219, 0), (999, 3)]))
    hr = df.heart_rate_max.map(lambda v: _points(v, [(40, 3), (50, 1), (90, 0), (110, 1), (130, 2), (999, 3)]))
    hot = t_max_c.map(lambda v: _points(v, [(38.0, 0), (39.0, 1), (999, 2)]))
    cold = t_min_c.map(lambda v: _points(v, [(35.0, 3), (36.0, 1), (999, 0)]))
    df["news_vitals"] = rr + sp + bp + hr + np.maximum(hot, cold)
    df["fever_measured"] = (df.temperature_max >= 100.4).astype(int)
    df["spo2_drop"] = df.spo2_mean - df.spo2_min
    for v in ["heart_rate", "respiratory_rate", "sbp", "temperature"]:
        df[f"{v}_range"] = df[f"{v}_max"] - df[f"{v}_min"]
    return df


def build(df: pd.DataFrame) -> pd.DataFrame:
    """Raw columns (vital stats, profile, symptoms, wbc/neutrophils/lymphocytes/crp) -> model input."""
    return add_engineered(add_lab_features(df))[FEATURES]


def from_app_inputs(vital_stats: dict, profile: dict, symptoms: dict, labs: dict,
                    respiratory_distress: int, hypoxemia: int) -> dict:
    """One patient's app inputs -> the Stage 2 v2 feature dict (same code path as training)."""
    raw = {k: vital_stats[k] for k in VITAL_STATS}
    raw["spo2_mean"] = min(raw["spo2_mean"], 100.0)
    raw.update(respiratory_distress=int(respiratory_distress), hypoxemia=int(hypoxemia),
               age=float(profile["age"]), gender_male=int(profile.get("sex") == "male"),
               **{k: int(profile[k]) for k in ("copd", "asthma", "diabetes", "hypertension",
                                               "heart_failure", "renal")},
               weakness=int(symptoms["weakness"]),
               **{k: float(labs[k]) for k in ("wbc", "neutrophils", "lymphocytes", "crp")})
    row = build(pd.DataFrame([raw])).iloc[0]
    return {k: (int(v) if k in BINARY else float(v)) for k, v in row.items()}
