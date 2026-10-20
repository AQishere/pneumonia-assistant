"""Trade-off table for the Stage 2 v2 threshold (Stage 1 unchanged).

    python -m training.threshold_table

Rows are computed on training data (5-fold out-of-fold scores, where a threshold
must be chosen) and checked on the test set. Counts are for the full two-stage
system, scaled to the 1,530-patient test set.
"""

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, recall_score
from sklearn.model_selection import StratifiedKFold

from training.train_stage2_v2 import MODELS, SEED, load_split, make_model


def rows(y, p1, p2, t1, thresholds, scale=1.0):
    out = []
    for t in thresholds:
        pred = ((p1 >= t1) & (p2 >= t)).astype(int)
        neg, pos = (y == 0), (y == 1)
        out.append((t, (pred[neg] == 1).sum() * scale, (pred[pos] == 0).sum() * scale,
                    recall_score(y, pred) * 100, recall_score(y, pred, pos_label=0) * 100,
                    accuracy_score(y, pred) * 100, balanced_accuracy_score(y, pred) * 100))
    return out


def main():
    X_tr, X_te, y_tr, y_te = load_split()
    s1 = joblib.load(MODELS / "stage1.joblib")
    v2 = joblib.load(MODELS / "stage2_v2.joblib")
    t1 = s1["threshold"]

    oof2 = np.zeros(len(X_tr))
    oof1 = np.zeros(len(X_tr))
    for a, b in StratifiedKFold(5, shuffle=True, random_state=SEED).split(X_tr, y_tr):
        oof2[b] = make_model().fit(X_tr.loc[a], y_tr[a]).predict_proba(X_tr.loc[b])[:, 1]
        # Stage 1 is a fixed model; its training-set scores are close enough for this table.
    oof1 = s1["model"].predict_proba(X_tr[s1["features"]])[:, 1]

    p1_te = s1["model"].predict_proba(X_te[s1["features"]])[:, 1]
    p2_te = v2["model"].predict_proba(X_te[v2["features"]])[:, 1]

    ths = [0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75]
    head = (f"{'thr':>5s} {'false alarms':>13s} {'missed':>7s} {'pneu found':>11s} "
            f"{'ctrl cleared':>13s} {'accuracy':>9s} {'bal.acc':>8s}")
    for name, y, p1, p2, scale in [("TRAINING (cross-validated, scaled to 1,530 patients)",
                                    y_tr, oof1, oof2, len(y_te) / len(y_tr)),
                                   ("TEST (1,530 real patients)", y_te, p1_te, p2_te, 1.0)]:
        print(f"\n{name}\n{head}")
        for t, fa, miss, sens, spec, acc, bal in rows(y.values, p1, p2, t1, ths, scale):
            print(f"{t:5.2f} {fa:13.0f} {miss:7.0f} {sens:10.1f}% {spec:12.1f}% {acc:8.1f}% {bal:7.1f}%")


if __name__ == "__main__":
    main()
