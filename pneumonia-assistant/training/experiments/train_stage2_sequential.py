"""Two-step cost-sensitive Stage 2 v2: first a false alarm costs 3x, then training continues with a miss costing 3x.

    python -m training.experiments.train_stage2_sequential

Step 1 is train_stage2_cost's fa3 model. Step 2 continues it on the same
training data with pneumonia weighted 3x: CatBoost adds trees on top of the
step-1 trees (init_model); logistic regression restarts from the step-1
coefficients (warm_start). Each step is scored on the test set at two
thresholds, both set on out-of-fold training scores:
  - keep: the threshold that clears as many controls as step 1 did
  - min cost: lowest cost with a miss costing 3x
Saves models/stage2_v2_sequential.joblib; the live stage2_v2.joblib is not changed.
"""

import joblib
import numpy as np
from catboost import CatBoostClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.metrics import recall_score, roc_auc_score
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import Bunch

from api.features_v2 import FEATURES
from training.train_stage2_cost import CURRENT, MODELS, SEED, X_te, X_tr, class_weights, cost, folds, make_model, y_te, y_tr

STEP2_ITERATIONS = 700


def continue_training(step1: VotingClassifier, X, y, ratio=3) -> VotingClassifier:
    """Step 2: keep training the step-1 models with pneumonia weighted `ratio` times."""
    lr, cat = step1.estimators_
    w = class_weights(ratio)
    lr.named_steps["clf"].set_params(class_weight=w, warm_start=True)
    lr.fit(X, y)
    p = CURRENT
    cat2 = CatBoostClassifier(iterations=STEP2_ITERATIONS, depth=p["depth"], learning_rate=p["learning_rate"],
                              l2_leaf_reg=p["l2_leaf_reg"], random_strength=p["random_strength"],
                              bagging_temperature=p["bagging_temperature"], class_weights=(w[0], w[1]),
                              random_seed=SEED, verbose=0, thread_count=-1)
    cat2.fit(X, y, init_model=cat)
    # A fitted VotingClassifier with the continued models, so the API can load it like any Stage 2 model.
    out = VotingClassifier(step1.estimators, voting="soft", weights=step1.weights)
    out.estimators_ = [lr, cat2]
    out.named_estimators_ = Bunch(logreg=lr, catboost=cat2)
    out.le_ = LabelEncoder().fit(y)
    out.classes_ = out.le_.classes_
    return out


def keep_threshold(oof, y, cleared):
    """Lowest threshold that still clears at least `cleared` of the controls (out-of-fold)."""
    for t in np.round(np.arange(0.05, 0.96, 0.01), 2):
        if (oof[y == 0] < t).mean() >= cleared:
            return float(t)
    return 0.95


def scores(step):
    """Out-of-fold training scores and test scores for step 1 or step 2."""
    oof = np.zeros(len(X_tr))
    for a, b in folds:
        m = make_model(1 / 3).fit(X_tr.loc[a], y_tr[a])
        if step == 2:
            m = continue_training(m, X_tr.loc[a], y_tr[a])
        oof[b] = m.predict_proba(X_tr.loc[b])[:, 1]
    m = make_model(1 / 3).fit(X_tr, y_tr)
    if step == 2:
        m = continue_training(m, X_tr, y_tr)
    return m, oof, m.predict_proba(X_te)[:, 1]


def row(name, p, thr):
    yt = y_te.values
    pred = (p >= thr).astype(int)
    print(f"{name:34s} {thr:>9.2f} {roc_auc_score(yt, p) * 100:>6.1f} {recall_score(yt, pred) * 100:>15.1f}% "
          f"{recall_score(yt, pred, pos_label=0) * 100:>16.1f}% {int(((pred == 0) & (yt == 1)).sum()):>7d} "
          f"{int(((pred == 1) & (yt == 0)).sum()):>13d}")


def main():
    y = y_tr.values
    ths = np.round(np.arange(0.05, 0.96, 0.01), 2)
    _, oof1, p1 = scores(1)
    thr1 = float(ths[np.argmin([cost(y, (oof1 >= t).astype(int), 1 / 3) for t in ths])])
    cleared1 = (oof1[y == 0] < thr1).mean()
    model2, oof2, p2 = scores(2)
    keep = keep_threshold(oof2, y, cleared1)
    thr2 = float(ths[np.argmin([cost(y, (oof2 >= t).astype(int), 3) for t in ths])])

    print(f"Test set: {int(y_te.sum())} pneumonia, {int((y_te == 0).sum())} without\n")
    print(f"{'':34s} {'threshold':>9s} {'AUC':>6s} {'pneumonia found':>16s} {'controls cleared':>17s} "
          f"{'missed':>7s} {'false alarms':>13s}")
    row("Step 1: false alarm 3x", p1, thr1)
    row("Step 2: + miss 3x, keep clearing", p2, keep)
    row("Step 2: + miss 3x, min cost", p2, thr2)

    joblib.dump({"model": model2, "features": FEATURES, "threshold": keep, "version": "stage2-v2",
                 "training": "fa3 then miss 3x (continued)", "threshold_rule": "keep step-1 clearing"},
                MODELS / "stage2_v2_sequential.joblib")
    print(f"\nSaved {MODELS / 'stage2_v2_sequential.joblib'} (threshold {keep}); stage2_v2.joblib unchanged")


if __name__ == "__main__":
    main()
