"""Three ideas for the live (equal) Stage 2 model, tested offline. Nothing is saved.

    python -m training.experiments.improvements_experiment

1. Vital-sign trends: add the dataset's *_trend columns as features (CV and test AUC).
2. Calibration: isotonic regression on out-of-fold scores, so the score reads as a
   probability. Measured by Brier score and calibration error on the test set.
3. Uncertain band: scores close to the threshold get "re-measure" instead of yes/no;
   how accurate are the remaining yes/no answers, and how many patients are uncertain.
All choices are made on training data (5-fold out-of-fold scores).
"""

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split

from api.features_v2 import FEATURES
from training.experiments.labs_only_experiment import equal_threshold, rates
from training.train_stage2_cost import make_model
from training.train_stage2_v2 import DATA, SEED, bootstrap_ci, load_split

TRENDS = [f"{v}_trend" for v in ["heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"]]

X_tr, X_te, y_tr, y_te = load_split()
# Trend columns, split exactly like load_split (same rows, same order).
raw = pd.read_csv(DATA)
t_tr, t_te = train_test_split(raw[TRENDS], test_size=0.20, stratify=raw["pneumonia_label"], random_state=SEED)
X_tr[TRENDS], X_te[TRENDS] = t_tr.reset_index(drop=True), t_te.reset_index(drop=True)
y, yt = y_tr.values, y_te.values
folds = list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(X_tr, y))


def oof_and_test(cols):
    oof, aucs = np.zeros(len(y)), []
    for a, b in folds:
        oof[b] = make_model(1).fit(X_tr.loc[a, cols], y[a]).predict_proba(X_tr.loc[b, cols])[:, 1]
        aucs.append(roc_auc_score(y[b], oof[b]))
    return oof, aucs, make_model(1).fit(X_tr[cols], y).predict_proba(X_te[cols])[:, 1]


def calibration_error(p, y_true, bins=10):
    """Average gap between predicted risk and observed pneumonia rate, over equal-size bins."""
    order = np.argsort(p)
    return float(np.mean([abs(p[i].mean() - y_true[i].mean()) for i in np.array_split(order, bins)]))


def main():
    print(f"Test set: {len(yt)} patients ({int(yt.sum())} pneumonia, {int((yt == 0).sum())} without)\n")

    print("1. Vital-sign trends")
    base_oof, base_aucs, base_p = oof_and_test(FEATURES)
    for name, oof, aucs, p in [("live (43 features)", base_oof, base_aucs, base_p),
                               ("+ 5 trend features", *oof_and_test(FEATURES + TRENDS))]:
        thr = equal_threshold(oof, y)
        lo, hi = bootstrap_ci(y_te, p, roc_auc_score)
        found, cleared = rates(p, yt, thr)
        print(f"   {name:22s} CV AUC {np.mean(aucs) * 100:5.2f} +/- {np.std(aucs) * 100:.1f}   "
              f"test AUC {roc_auc_score(yt, p) * 100:5.1f} ({lo * 100:.1f}-{hi * 100:.1f})   "
              f"caught {found * 100:4.1f}%  cleared {cleared * 100:4.1f}%")

    print("\n2. Calibration (live model)")
    iso = IsotonicRegression(out_of_bounds="clip").fit(base_oof, y)
    cal_p = iso.predict(base_p)
    for name, p in [("raw score", base_p), ("calibrated", cal_p)]:
        print(f"   {name:12s} Brier {brier_score_loss(yt, p):.3f}   calibration error {calibration_error(p, yt) * 100:4.1f} "
              f"points   AUC {roc_auc_score(yt, p) * 100:.1f}")
    print(f"   Note: calibrated to this dataset, where {y.mean() * 100:.0f}% have pneumonia; at home the real "
          f"risk is far lower.")

    print("\n3. Uncertain band around the threshold (live model)")
    thr = equal_threshold(base_oof, y)
    print(f"   threshold {thr}")
    print(f"   {'band':>12s} {'uncertain':>10s} {'yes/no correct':>15s} {'caught':>8s} {'cleared':>8s} "
          f"{'missed':>7s} {'false alarms':>13s}")
    for width in [0.0, 0.05, 0.10, 0.15]:
        unsure = np.abs(base_p - thr) < width
        sure = ~unsure
        pred = base_p >= thr
        miss = int((sure & ~pred & (yt == 1)).sum())
        fa = int((sure & pred & (yt == 0)).sum())
        correct = (pred[sure] == yt[sure]).mean()
        caught = (sure & pred & (yt == 1)).sum() / (sure & (yt == 1)).sum()
        cleared = (sure & ~pred & (yt == 0)).sum() / (sure & (yt == 0)).sum()
        print(f"   {'+/- ' + str(width):>12s} {unsure.mean() * 100:>9.1f}% {correct * 100:>14.1f}% "
              f"{caught * 100:>7.1f}% {cleared * 100:>7.1f}% {miss:>7d} {fa:>13d}")


if __name__ == "__main__":
    main()
