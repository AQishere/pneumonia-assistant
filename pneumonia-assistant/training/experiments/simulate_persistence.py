"""Simulation: what does the persistence rule do over two assessments 12 hours apart?

    python -m training.experiments.simulate_persistence

Built from the 1,530 REAL test patients (true labels unchanged). Each patient is
"re-measured" twice by adding the same kind of measurement noise to everyone's
vital-sign features; the app's real Stage 1 / Stage 2 models and the persistence
settings are then applied. Results describe this simulation and its noise
assumption, not real-world performance: they must be confirmed on real IoT data.

Writes ../data/synthetic_repeated_assessments.csv (local only; derived from MIMIC rows,
so it must not be uploaded to Firestore or shared).
"""

import joblib
import numpy as np
import pandas as pd

from api.assessment import IMMEDIATE_HIGH
from training.train_stage2_v2 import MODELS, ROOT, SEED, load_split

# Typical change in each feature between two assessments 12 h apart (1x noise level).
NOISE = {
    "heart_rate_max": 6.0, "heart_rate_std": 1.5,
    "respiratory_rate_max": 2.5, "respiratory_rate_mean": 1.5,
    "sbp_min": 6.0, "sbp_std": 1.5,
    "spo2_min": 1.5, "spo2_mean": 0.8,
    "temperature_max": 0.5, "temperature_std": 0.1,
}
LIMITS = {"spo2_min": (50, 100), "spo2_mean": (50, 100)}


def remeasure(X: pd.DataFrame, scale: float, rng) -> pd.DataFrame:
    X = X.copy()
    for col, sd in NOISE.items():
        X[col] = X[col] + rng.normal(0, sd * scale, len(X))
        if col.endswith("_std"):
            X[col] = X[col].clip(lower=0)
        if col in LIMITS:
            X[col] = X[col].clip(*LIMITS[col])
    X["spo2_mean"] = np.maximum(X["spo2_mean"], X["spo2_min"])
    return X


def run(X_te, y, s1, s2, scale, seed):
    rng = np.random.default_rng(seed)
    out = {}
    for name in ("a", "b"):                      # two assessments, 12 h apart
        X = remeasure(X_te, scale, rng)
        p1 = s1["model"].predict_proba(X[s1["features"]])[:, 1]
        p2 = s2["model"].predict_proba(X[s2["features"]])[:, 1]
        out[f"p1_{name}"], out[f"p2_{name}"] = p1, p2
        out[f"pos_{name}"] = (p1 >= s1["threshold"]) & (p2 >= s2["threshold"])
    df = pd.DataFrame(out)
    df["pneumonia"] = y.values

    # Current approach: High (X-ray now) whenever Stage 2 is positive.
    df["current_xray_now"] = df.pos_a
    # Persistence: High now only if very confident; otherwise Watch, confirmed at assessment b.
    df["persist_high_now"] = df.pos_a & (df.p2_a >= IMMEDIATE_HIGH)
    df["persist_watch"] = df.pos_a & (df.p2_a < IMMEDIATE_HIGH)
    df["persist_confirmed"] = df.persist_watch & df.pos_b
    df["persist_high_by_b"] = df.persist_high_now | df.persist_confirmed
    df["persist_deescalated"] = df.persist_watch & ~df.pos_b      # flagged, then not confirmed
    return df


def summarise(df, label):
    pn, ct = df[df.pneumonia == 1], df[df.pneumonia == 0]
    row = {"noise": label}
    for k, col in [("X-ray now: current", "current_xray_now"), ("X-ray now: persistence", "persist_high_now"),
                   ("Watch (flagged, waiting)", "persist_watch"),
                   ("High after 12 h: persistence", "persist_high_by_b"),
                   ("De-escalated after 12 h", "persist_deescalated")]:
        row[f"{k} | pneumonia"] = int(pn[col].sum())
        row[f"{k} | no pneumonia"] = int(ct[col].sum())
    return row


def main():
    _, X_te, _, y_te = load_split()
    s1 = joblib.load(MODELS / "stage1.joblib")
    s2 = joblib.load(MODELS / "stage2.joblib")          # the Stage 2 model the app uses now
    print(f"{len(y_te)} real test patients: {int(y_te.sum())} pneumonia, {int((y_te == 0).sum())} without.")
    print("Simulated: two assessments 12 h apart with measurement noise. Stage 2 = model in the app now.\n")

    rows, saved = [], None
    for label, scale in [("half", 0.5), ("normal", 1.0), ("double", 2.0)]:
        runs = [run(X_te, y_te, s1, s2, scale, SEED + i) for i in range(20)]   # average over 20 simulations
        mean = pd.DataFrame([summarise(r, label) for r in runs]).drop(columns="noise").mean().round(0)
        rows.append({"noise": label, **mean.to_dict()})
        if scale == 1.0:
            saved = runs[0]

    table = pd.DataFrame(rows).set_index("noise").T
    print(table.astype(int).to_string())

    saved.assign(synthetic_remeasurement=1).round(4).to_csv(
        ROOT.parent / "data" / "synthetic_repeated_assessments.csv", index_label="test_patient")
    print("\nSaved one simulated run (normal noise) to synthetic_repeated_assessments.csv (local only).")


if __name__ == "__main__":
    main()
