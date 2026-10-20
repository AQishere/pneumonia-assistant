"""Is Stage 2 any worse without CRP? (CRP was measured for only 13% of patients.)

    python -m training.experiments.drop_crp_experiment

The equal model (cost ratio 1, threshold where the share of pneumonia caught
equals the share of controls cleared) with and without the crp feature:
5-fold CV on the training patients, then one look at the test set, overall and
for the patients who had CRP measured. Nothing is saved.
"""

import numpy as np
from sklearn.metrics import roc_auc_score

from api.features_v2 import FEATURES
from training.experiments.labs_only_experiment import equal_threshold, rates
from training.train_stage2_cost import X_te, X_tr, folds, make_model, y_te, y_tr
from training.train_stage2_v2 import bootstrap_ci


def main():
    y, yt = y_tr.values, y_te.values
    crp_te = X_te.crp.notna().values
    print(f"Test set: {len(yt)} patients ({int((yt == 0).sum())} without pneumonia); "
          f"CRP measured for {crp_te.sum()} ({int((yt[crp_te] == 0).sum())} without)\n")
    print(f"{'':16s} {'CV AUC':>13s} {'test AUC (95% CI)':>19s} {'pneumonia found':>16s} {'controls cleared':>17s} "
          f"{'AUC, CRP measured':>18s}")
    for name, cols in [("with CRP", FEATURES), ("without CRP", [f for f in FEATURES if f != "crp"])]:
        oof, aucs = np.zeros(len(y)), []
        for a, b in folds:
            oof[b] = make_model(1).fit(X_tr.loc[a, cols], y[a]).predict_proba(X_tr.loc[b, cols])[:, 1]
            aucs.append(roc_auc_score(y[b], oof[b]))
        thr = equal_threshold(oof, y)
        p = make_model(1).fit(X_tr[cols], y).predict_proba(X_te[cols])[:, 1]
        lo, hi = bootstrap_ci(y_te, p, roc_auc_score)
        found, cleared = rates(p, yt, thr)
        print(f"{name:16s} {np.mean(aucs) * 100:6.2f} +/- {np.std(aucs) * 100:3.1f} "
              f"{roc_auc_score(yt, p) * 100:7.1f} ({lo * 100:.1f}-{hi * 100:.1f}) {found * 100:>15.1f}% "
              f"{cleared * 100:>16.1f}% {roc_auc_score(yt[crp_te], p[crp_te]) * 100:>17.1f}")


if __name__ == "__main__":
    main()
