"""Clinical feature engineering for Stage 2, tested step by step. Nothing is saved.

    python -m training.experiments.feature_engineering_experiment

Each step adds to the previous one; all use the equal model (cost ratio 1,
threshold where caught = cleared on out-of-fold training scores):
  0. live model
  1. hypoxemia redefined as the app computes it: any SpO2 < 90, or the recorded flag
  2. + clinical features: SIRS score, ROX proxy, temperature/WBC distance from normal,
     coefficient of variation per vital, SII proxy, COPD/heart-failure interactions
  3. + splines for the logistic regression (curved risk, e.g. low and high WBC both bad)
  4. + MICE imputation instead of the median, for the logistic regression
Then the three-zone split (green / amber / red) on the best step.
Temperatures in the data are in °F.
"""

import numpy as np
from catboost import CatBoostClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import VotingClassifier
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer, SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

from api.features_v2 import BINARY, FEATURES
from training.experiments.labs_only_experiment import equal_threshold, rates
from training.train_stage2_cost import CURRENT, class_weights
from training.train_stage2_v2 import SEED, bootstrap_ci, load_split

FEVER_F, HYPOTHERMIA_F, NORMAL_F = 100.4, 96.8, 98.6
VITALS = ["heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"]
NEW = (["sirs_score", "rox_proxy", "rox_mean_proxy", "temp_deviation", "wbc_deviation", "sii_proxy",
        "copd_x_spo2_min", "hf_without_fever", "infectious_distress"] + [f"{v}_cv" for v in VITALS])
NEW_BINARY = {"hf_without_fever", "infectious_distress"}


def app_hypoxemia(df):
    df = df.copy()
    df["hypoxemia"] = ((df.spo2_min < 90) | (df.hypoxemia == 1)).astype(int)
    return df


def clinical(df):
    df = df.copy()
    hot_or_cold = ((df.temperature_max >= FEVER_F) | (df.temperature_min <= HYPOTHERMIA_F)).astype(int)
    wbc_abnormal = ((df.wbc > 12) | (df.wbc < 4)).astype(int)        # NaN WBC counts as normal
    df["sirs_score"] = hot_or_cold + (df.heart_rate_max > 90) + (df.respiratory_rate_max > 20) + wbc_abnormal
    df["rox_proxy"] = df.spo2_min / df.respiratory_rate_max.clip(lower=1)
    df["rox_mean_proxy"] = df.spo2_mean / df.respiratory_rate_mean.clip(lower=1)
    df["temp_deviation"] = (df.temperature_max - NORMAL_F).abs()
    df["wbc_deviation"] = (df.wbc - 7.5).abs()
    df["sii_proxy"] = df.nlr * df.wbc
    df["copd_x_spo2_min"] = df.copd * df.spo2_min
    df["hf_without_fever"] = ((df.heart_failure == 1) & (hot_or_cold == 0) & (wbc_abnormal == 0)).astype(int)
    df["infectious_distress"] = ((df.respiratory_distress == 1) & ((hot_or_cold == 1) | (wbc_abnormal == 1))).astype(int)
    for v in VITALS:
        df[f"{v}_cv"] = df[f"{v}_std"] / df[f"{v}_mean"].clip(lower=0.1)
    return df


def make_model(cols, splines=False, mice=False):
    w = class_weights(1)
    impute = IterativeImputer(max_iter=10, random_state=SEED) if mice else SimpleImputer(strategy="median")
    if splines:
        cont = [c for c in cols if c not in BINARY | NEW_BINARY]
        pre = ColumnTransformer([("cont", Pipeline([("sp", SplineTransformer(n_knots=4, degree=2)),
                                                    ("s", StandardScaler())]), cont)], remainder="passthrough")
        lr = Pipeline([("impute", impute), ("pre", pre),
                       ("clf", LogisticRegression(C=0.3, max_iter=4000, class_weight=w))])
        # The imputer turns the frame into an array, so the transformer selects columns by position.
        pre.transformers[0] = ("cont", pre.transformers[0][1], [cols.index(c) for c in cont])
    else:
        lr = Pipeline([("impute", impute), ("scale", StandardScaler()),
                       ("clf", LogisticRegression(max_iter=3000, class_weight=w))])
    p = CURRENT
    cat = CatBoostClassifier(iterations=p["iterations"], depth=p["depth"], learning_rate=p["learning_rate"],
                             l2_leaf_reg=p["l2_leaf_reg"], class_weights=(w[0], w[1]), random_seed=SEED,
                             verbose=0, thread_count=-1)
    return VotingClassifier([("logreg", lr), ("catboost", cat)], voting="soft")


def evaluate(X_tr, y, X_te, cols, **kw):
    oof, aucs = np.zeros(len(y)), []
    for a, b in StratifiedKFold(5, shuffle=True, random_state=SEED).split(X_tr, y):
        oof[b] = make_model(cols, **kw).fit(X_tr.loc[a, cols], y[a]).predict_proba(X_tr.loc[b, cols])[:, 1]
        aucs.append(roc_auc_score(y[b], oof[b]))
    return oof, aucs, make_model(cols, **kw).fit(X_tr[cols], y).predict_proba(X_te[cols])[:, 1]


def zones(p, yt, lo, hi):
    green, red = p < lo, p >= hi
    sure = green | red
    return {"amber": 1 - sure.mean(), "accuracy": ((red & (yt == 1)) | (green & (yt == 0)))[sure].mean(),
            "ppv": yt[red].mean(), "npv": (yt[green] == 0).mean(),
            "caught": (red & (yt == 1)).sum() / (sure & (yt == 1)).sum(),
            "cleared": (green & (yt == 0)).sum() / (sure & (yt == 0)).sum()}


def main():
    X_tr, X_te, y_tr, y_te = load_split()
    y, yt = y_tr.values, y_te.values
    hx_tr, hx_te = app_hypoxemia(X_tr), app_hypoxemia(X_te)
    cl_tr, cl_te = clinical(hx_tr), clinical(hx_te)
    steps = [("0. live model", X_tr, X_te, FEATURES, {}),
             ("1. hypoxemia as the app computes it", hx_tr, hx_te, FEATURES, {}),
             ("2. + clinical features", cl_tr, cl_te, FEATURES + NEW, {}),
             ("3. + splines (logistic regression)", cl_tr, cl_te, FEATURES + NEW, {"splines": True}),
             ("4. + MICE imputation", cl_tr, cl_te, FEATURES + NEW, {"splines": True, "mice": True})]
    print(f"Test set: {len(yt)} patients ({int(yt.sum())} pneumonia, {int((yt == 0).sum())} without)\n")
    print(f"{'':38s} {'CV AUC':>13s} {'test AUC (95% CI)':>19s} {'caught':>7s} {'cleared':>8s}")
    best = None
    for name, tr, te, cols, kw in steps:
        oof, aucs, p = evaluate(tr, y, te, cols, **kw)
        thr = equal_threshold(oof, y)
        lo, hi = bootstrap_ci(y_te, p, roc_auc_score)
        found, cleared = rates(p, yt, thr)
        print(f"{name:38s} {np.mean(aucs) * 100:6.2f} +/- {np.std(aucs) * 100:.1f} "
              f"{roc_auc_score(yt, p) * 100:7.1f} ({lo * 100:.1f}-{hi * 100:.1f}) {found * 100:6.1f}% {cleared * 100:7.1f}%",
              flush=True)
        if best is None or np.mean(aucs) > best[0]:
            best = (np.mean(aucs), name, p, oof)

    _, name, p, oof = best
    print(f"\nThree zones on the best step by CV ({name}); amber = send for chest X-ray")
    print(f"   {'green <':>8s} {'red >=':>7s} {'amber':>7s} {'accuracy':>9s} {'PPV':>6s} {'NPV':>6s} {'caught':>7s} {'cleared':>8s}")
    for lo, hi in [(0.43, 0.63), (0.40, 0.65), (0.35, 0.70)]:
        z = zones(p, yt, lo, hi)
        print(f"   {lo:>8.2f} {hi:>7.2f} {z['amber'] * 100:6.1f}% {z['accuracy'] * 100:8.1f}% {z['ppv'] * 100:5.1f}% "
              f"{z['npv'] * 100:5.1f}% {z['caught'] * 100:6.1f}% {z['cleared'] * 100:7.1f}%")
    print(f"   (PPV and NPV depend on the 75% pneumonia share of this dataset; at home PPV would be far lower.)")


if __name__ == "__main__":
    main()
