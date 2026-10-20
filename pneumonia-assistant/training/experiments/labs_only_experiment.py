"""Does Stage 2 do better on patients who had all four labs done, as every app user does?

    python -m training.experiments.labs_only_experiment

Compares, on the same labs-complete patients:
  A. the equal model trained on all training patients (labs missing for most)
  B. the same model trained only on labs-complete patients
Out-of-fold scores (5 folds x 5 repeats) on the labs-complete training patients,
then one check on the labs-complete test patients. Threshold: equal share of
pneumonia caught and controls cleared, set on out-of-fold training scores.
Nothing is saved.
"""

import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

from training.train_stage2_cost import SEED, X_te, X_tr, make_model, y_te, y_tr
from training.train_stage2_v2 import bootstrap_ci

LABS = ["wbc", "neutrophils", "lymphocytes", "crp"]
REPEATS = 5


def equal_threshold(score, y):
    ths = np.round(np.arange(0.05, 0.96, 0.01), 2)
    return float(ths[np.argmin([abs((score[y == 1] >= t).mean() - (score[y == 0] < t).mean()) for t in ths])])


def rates(score, y, thr):
    pred = score >= thr
    return pred[y == 1].mean(), (~pred[y == 0]).mean()


def main():
    has_tr = X_tr[LABS].notna().all(axis=1).values
    has_te = X_te[LABS].notna().all(axis=1).values
    y_all, ytr, yte = y_tr.values, y_tr.values[has_tr], y_te.values[has_te]
    idx = np.where(has_tr)[0]
    print(f"Labs-complete patients: training {has_tr.sum()} ({int((ytr == 0).sum())} without pneumonia), "
          f"test {has_te.sum()} ({int((yte == 0).sum())} without)\n")

    # Out-of-fold scores on the labs-complete training patients, repeated, for both training sets.
    oof_a, oof_b = np.zeros((REPEATS, len(idx))), np.zeros((REPEATS, len(idx)))
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=REPEATS, random_state=SEED)
    for k, (a, b) in enumerate(cv.split(idx, ytr)):
        rep = k // 5
        # A: everything except the held-out labs-complete patients (so the full data is used for training).
        train_a = np.setdiff1d(np.arange(len(X_tr)), idx[b])
        oof_a[rep, b] = make_model(1).fit(X_tr.iloc[train_a], y_all[train_a]).predict_proba(X_tr.iloc[idx[b]])[:, 1]
        # B: only labs-complete patients.
        oof_b[rep, b] = make_model(1).fit(X_tr.iloc[idx[a]], ytr[a]).predict_proba(X_tr.iloc[idx[b]])[:, 1]

    print(f"{'Cross-validation (training)':40s} {'AUC':>12s} {'pneumonia found':>16s} {'controls cleared':>17s}")
    thr = {}
    for name, oof in [("A. trained on all patients", oof_a), ("B. trained on labs-complete only", oof_b)]:
        aucs = [roc_auc_score(ytr, o) for o in oof]
        thr[name] = equal_threshold(oof.mean(axis=0), ytr)
        found, cleared = np.mean([rates(o, ytr, thr[name]) for o in oof], axis=0)
        print(f"{name:40s} {np.mean(aucs) * 100:5.1f} +/- {np.std(aucs) * 100:3.1f} {found * 100:>15.1f}% "
              f"{cleared * 100:>16.1f}%")

    print(f"\n{'Test check (labs-complete test patients)':40s} {'AUC (95% CI)':>18s} {'pneumonia found':>16s} "
          f"{'controls cleared':>17s}")
    tests = [("A. trained on all patients", make_model(1).fit(X_tr, y_all)),
             ("B. trained on labs-complete only", make_model(1).fit(X_tr[has_tr], ytr))]
    for name, model in tests:
        p = model.predict_proba(X_te[has_te])[:, 1]
        lo, hi = bootstrap_ci(y_te[has_te].reset_index(drop=True), p, roc_auc_score)
        found, cleared = rates(p, yte, thr[name])
        print(f"{name:40s} {roc_auc_score(yte, p) * 100:5.1f} ({lo * 100:.0f}-{hi * 100:.0f}) "
              f"{found * 100:>15.1f}% {cleared * 100:>16.1f}%")


if __name__ == "__main__":
    main()
