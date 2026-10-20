"""Scores and bias check inside the persistence simulation (see simulate_persistence.py).

    python -m training.experiments.simulate_scores

Bias check: a model is biased towards pneumonia when it finds pneumonia much more
often than it clears patients without it (sensitivity >> specificity).
"""

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, recall_score, roc_auc_score

from api.assessment import IMMEDIATE_HIGH
from training.experiments.simulate_persistence import remeasure
from training.train_stage2_v2 import MODELS, SEED, load_split


def scores(y, pred, score=None):
    sens, spec = recall_score(y, pred) * 100, recall_score(y, pred, pos_label=0) * 100
    return {"AUC": roc_auc_score(y, score) * 100 if score is not None else np.nan,
            "accuracy": accuracy_score(y, pred) * 100, "balanced acc": balanced_accuracy_score(y, pred) * 100,
            "pneumonia found": sens, "controls cleared": spec, "gap (found - cleared)": sens - spec}


def main():
    _, X_te, _, y = load_split()
    s1, s2 = joblib.load(MODELS / "stage1.joblib"), joblib.load(MODELS / "stage2.joblib")
    rows = {}
    for label, scale in [("real data (no noise)", 0.0), ("simulated, normal noise", 1.0)]:
        acc = []
        for i in range(20 if scale else 1):
            rng = np.random.default_rng(SEED + i)
            Xa, Xb = (X_te, X_te) if scale == 0 else (remeasure(X_te, scale, rng), remeasure(X_te, scale, rng))
            p1a = s1["model"].predict_proba(Xa[s1["features"]])[:, 1]
            p2a = s2["model"].predict_proba(Xa[s2["features"]])[:, 1]
            p1b = s1["model"].predict_proba(Xb[s1["features"]])[:, 1]
            p2b = s2["model"].predict_proba(Xb[s2["features"]])[:, 1]
            f1a = p1a >= s1["threshold"]
            pos_a = f1a & (p2a >= s2["threshold"])
            pos_b = (p1b >= s1["threshold"]) & (p2b >= s2["threshold"])
            high_now = pos_a & (p2a >= IMMEDIATE_HIGH)
            high_12h = high_now | (pos_a & (p2a < IMMEDIATE_HIGH) & pos_b)
            acc.append({
                "Stage 1 alone": scores(y, f1a, p1a),
                "Stage 2 alone": scores(y, p2a >= s2["threshold"], p2a),
                "Two-stage (current rule)": scores(y, pos_a, np.where(f1a, p2a, 0)),
                "Persistence: X-ray now": scores(y, high_now),
                "Persistence: High after 12 h": scores(y, high_12h),
            })
        for model in acc[0]:
            rows[(label, model)] = pd.DataFrame([a[model] for a in acc]).mean()

    table = pd.DataFrame(rows).T.round(1)
    pd.set_option("display.width", 200)
    print(table.to_string())


if __name__ == "__main__":
    main()
