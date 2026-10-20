"""Can false alarms fall WITHOUT catching fewer pneumonia cases? (Stage 1 unchanged.)

    python -m training.experiments.reduce_false_alarms

Every method's threshold is set on training data (out-of-fold scores) so the
two-stage system catches at least as many pneumonia cases as the current v2
model; then false alarms are counted on the test set.
"""

import numpy as np
import pandas as pd
import joblib
from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

from api.features_v2 import BINARY, FEATURES
from training.train_stage2_v2 import MODELS, SEED, load_split

X_tr, X_te, y_tr, y_te = load_split()
s1 = joblib.load(MODELS / "stage1.joblib")
f1_tr = s1["model"].predict_proba(X_tr[s1["features"]])[:, 1] >= s1["threshold"]
f1_te = s1["model"].predict_proba(X_te[s1["features"]])[:, 1] >= s1["threshold"]
folds = list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(X_tr, y_tr))
CONT = [c for c in FEATURES if c not in BINARY]
BIN = [c for c in FEATURES if c in BINARY]


def lr():
    return Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler()),
                     ("c", LogisticRegression(max_iter=2000, class_weight="balanced"))])


def spline_lr():
    pre = ColumnTransformer([("cont", Pipeline([("i", SimpleImputer(strategy="median")),
                                                ("sp", SplineTransformer(n_knots=5)), ("s", StandardScaler())]), CONT),
                             ("bin", "passthrough", BIN)])
    return Pipeline([("p", pre), ("c", LogisticRegression(max_iter=3000, C=0.3, class_weight="balanced"))])


def cat():
    return CatBoostClassifier(iterations=700, depth=4, learning_rate=0.04, l2_leaf_reg=5,
                              auto_class_weights="Balanced", random_seed=SEED, verbose=0, thread_count=-1)


def lgbm():
    return LGBMClassifier(n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8,
                          subsample_freq=1, colsample_bytree=0.8, reg_lambda=2, class_weight="balanced",
                          random_state=SEED, verbose=-1)


def fit(make, X, y, w=None):
    m = make()
    if w is None:
        return m.fit(X, y)
    if isinstance(m, Pipeline):
        return m.fit(X, y, **{f"{m.steps[-1][0]}__sample_weight": w})
    return m.fit(X, y, sample_weight=w)


def oof_and_test(make, weights=None):
    oof = np.zeros(len(X_tr))
    for a, b in folds:
        w = None if weights is None else weights(a)
        oof[b] = fit(make, X_tr.loc[a], y_tr[a], w).predict_proba(X_tr.loc[b])[:, 1]
    w = None if weights is None else weights(np.arange(len(X_tr)))
    return oof, fit(make, X_tr, y_tr, w).predict_proba(X_te)[:, 1]


def counts(y, flag1, score, thr):
    pred = flag1 & (score >= thr)
    return int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum())


def threshold_for(score_tr, target_tp, flag1=f1_tr):
    """Highest threshold that still catches at least target_tp pneumonia cases in training."""
    for t in np.round(np.arange(0.95, 0.05, -0.005), 3):
        if counts(y_tr.values, flag1, score_tr, t)[0] >= target_tp:
            return t
    return 0.05


print("Fitting base models (5-fold)...")
base = {name: oof_and_test(make) for name, make in
        [("lr", lr), ("cat", cat), ("lgbm", lgbm), ("spline", spline_lr)]}
v2_tr = (base["lr"][0] + base["cat"][0]) / 2
v2_te = (base["lr"][1] + base["cat"][1]) / 2
target_tp = counts(y_tr.values, f1_tr, v2_tr, 0.52)[0]
yt = y_te.values
results = []


def report(name, tr, te, thr=None):
    thr = threshold_for(tr, target_tp) if thr is None else thr
    tp, fa = counts(yt, f1_te, te, thr)
    results.append((name, thr, tp, fa))


report("Current v2 (LR + CatBoost, threshold 0.52)", v2_tr, v2_te, 0.52)

# 1. Subgroup thresholds: patients with COPD / heart failure / kidney disease vs without.
grp_tr = (X_tr[["copd", "heart_failure", "renal"]].sum(axis=1) > 0).values
grp_te = (X_te[["copd", "heart_failure", "renal"]].sum(axis=1) > 0).values
best = None
grid = np.round(np.arange(0.30, 0.80, 0.01), 2)
for ta in grid:
    for tb in grid:
        thr_tr = np.where(grp_tr, ta, tb)
        tp, fa = counts(y_tr.values, f1_tr, v2_tr - thr_tr + 0.5, 0.5)
        if tp >= target_tp and (best is None or fa < best[2]):
            best = (ta, tb, fa)
ta, tb, _ = best
results.append((f"1. Subgroup thresholds (comorbid {ta}, others {tb})", "-",
                *counts(yt, f1_te, v2_te - np.where(grp_te, ta, tb) + 0.5, 0.5)))

# 2. Focus on hard negatives: up-weight non-pneumonia patients the model scores high (inner CV, no leakage).
def hard_negative_weights(idx):
    Xs, ys = X_tr.iloc[idx], y_tr.iloc[idx]
    inner = cross_val_predict(lr(), Xs, ys, cv=3, method="predict_proba")[:, 1]
    return np.where(ys.values == 0, 1 + 3 * inner, 1.0)


hn_lr = oof_and_test(lr, hard_negative_weights)
hn_cat = oof_and_test(cat, hard_negative_weights)
report("2. Hard-negative weighting (LR + CatBoost)", (hn_lr[0] + hn_cat[0]) / 2, (hn_lr[1] + hn_cat[1]) / 2)

# 3. Stacking: a logistic regression learns how to combine four different models.
S_tr = np.column_stack([base[k][0] for k in base])
S_te = np.column_stack([base[k][1] for k in base])
meta = LogisticRegression(max_iter=1000, class_weight="balanced")
stack_tr = cross_val_predict(meta, S_tr, y_tr, cv=5, method="predict_proba")[:, 1]
stack_te = meta.fit(S_tr, y_tr).predict_proba(S_te)[:, 1]
report("3. Stacking (LR, CatBoost, LightGBM, spline LR)", stack_tr, stack_te)

# 4. Simple average of all four models.
report("4. Average of four models", S_tr.mean(axis=1), S_te.mean(axis=1))

print(f"\nTest set: {int(yt.sum())} pneumonia, {int((yt == 0).sum())} without. "
      f"Target: catch at least as many as the current model.\n")
print(f"{'method':58s} {'pneumonia caught':>17s} {'false alarms':>13s}")
for name, thr, tp, fa in results:
    print(f"{name:58s} {tp:>17d} {fa:>13d}")
