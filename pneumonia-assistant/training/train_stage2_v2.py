"""Train Stage 2 v2: average of logistic regression and CatBoost on the full feature set.

    python -m training.train_stage2_v2

Same train/test split and cleaning as the notebook. Everything is chosen on the
training data (5-fold CV); the test set is used once for the final report.
Writes models/stage2_v2.joblib and models/stage2_v2_metrics.json. Stage 1 is
not touched.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from api.features_v2 import FEATURES, VITALS, build

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "data" / "pneumonia_dataset_with_labs.csv"
MODELS = ROOT / "models"
SEED = 42


def load_split():
    raw = pd.read_csv(DATA)
    X, y = raw.drop(columns=["hadm_id", "pneumonia_label"]), raw["pneumonia_label"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.20, stratify=y, random_state=SEED)
    return clean(X_tr), clean(X_te), y_tr.reset_index(drop=True), y_te.reset_index(drop=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """The notebook's cleaning, plus labs: a 0 with "_done" = 0 means not measured."""
    df = df.copy()
    df["spo2_mean"] = df["spo2_mean"].clip(upper=100)
    for v in VITALS:
        df[f"{v}_mean"] = df[f"{v}_mean"].clip(df[f"{v}_min"], df[f"{v}_max"] if v != "spo2" else None)
    for lab in ["wbc", "neutrophils", "lymphocytes", "crp"]:
        df[lab] = df[f"{lab}_value"].where(df[f"{lab}_done"] == 1)   # "_done" flags are not features (leakage)
    # Hypoxemia as the app computes it (api/safety.derive_hypoxemia): any SpO2 below 90, or the recorded
    # flag. The recorded flag alone matched that rule for only 59% of patients.
    df["hypoxemia"] = ((df["spo2_min"] < 90) | (df["hypoxemia"] == 1)).astype(int)
    return build(df).reset_index(drop=True)


def make_model():
    lr = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                   ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))])
    cat = CatBoostClassifier(iterations=700, depth=4, learning_rate=0.04, l2_leaf_reg=5,
                             auto_class_weights="Balanced", random_seed=SEED, verbose=0, thread_count=-1)
    # Soft voting = average of the two probabilities, so one patient can be scored on their own.
    return VotingClassifier([("logreg", lr), ("catboost", cat)], voting="soft")


def bootstrap_ci(y, p, metric, n=2000, seed=SEED):
    rng, vals = np.random.default_rng(seed), []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].nunique() == 2:
            vals.append(metric(y[i], p[i]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def main():
    X_tr, X_te, y_tr, y_te = load_split()
    print(f"Train {len(X_tr)}, test {len(X_te)}, features {len(FEATURES)}")

    # 1. Cross-validation on training data: AUC and out-of-fold scores for the threshold.
    oof = np.zeros(len(X_tr))
    fold_aucs = []
    for a, b in StratifiedKFold(5, shuffle=True, random_state=SEED).split(X_tr, y_tr):
        m = make_model().fit(X_tr.loc[a], y_tr[a])
        oof[b] = m.predict_proba(X_tr.loc[b])[:, 1]
        fold_aucs.append(roc_auc_score(y_tr[b], oof[b]))
    print(f"CV AUC {np.mean(fold_aucs)*100:.1f} (+/- {np.std(fold_aucs)*100:.1f})")

    # 2. Threshold: maximise balanced accuracy on the out-of-fold scores (training data only).
    ths = np.round(np.arange(0.20, 0.81, 0.01), 2)
    threshold = float(ths[np.argmax([balanced_accuracy_score(y_tr, oof >= t) for t in ths])])
    print(f"Threshold chosen on training data: {threshold}")

    # 3. Final model on all training data; one evaluation on the test set.
    model = make_model().fit(X_tr, y_tr)
    p_te = model.predict_proba(X_te)[:, 1]
    pred = (p_te >= threshold).astype(int)

    # Current Stage 2 on the same test patients, for a paired comparison.
    old = joblib.load(MODELS / "stage2.joblib")
    p_old = old["model"].predict_proba(X_te[old["features"]])[:, 1]
    pred_old = (p_old >= old["threshold"]).astype(int)

    # Two-stage system on the test set, with the unchanged Stage 1.
    s1 = joblib.load(MODELS / "stage1.joblib")
    flagged = s1["model"].predict_proba(X_te[s1["features"]])[:, 1] >= s1["threshold"]
    two_new = (flagged & (pred == 1)).astype(int)
    two_old = (flagged & (pred_old == 1)).astype(int)

    rng, diffs = np.random.default_rng(SEED), []
    for _ in range(2000):
        i = rng.integers(0, len(y_te), len(y_te))
        if y_te[i].nunique() == 2:
            diffs.append(roc_auc_score(y_te[i], p_te[i]) - roc_auc_score(y_te[i], p_old[i]))

    def summary(y, p, pr):
        return {"auc": float(roc_auc_score(y, p)) if p is not None else None,
                "balanced_accuracy": float(balanced_accuracy_score(y, pr)),
                "pneumonia_recall": float(recall_score(y, pr)),
                "control_recall": float(recall_score(y, pr, pos_label=0))}

    metrics = {
        "model": "Stage 2 v2: soft-voting average of logistic regression and CatBoost",
        "features": FEATURES,
        "threshold": threshold,
        "cv_auc_mean": float(np.mean(fold_aucs)), "cv_auc_std": float(np.std(fold_aucs)),
        "test": {**summary(y_te, p_te, pred), "auc_ci95": bootstrap_ci(y_te, p_te, roc_auc_score),
                 "balanced_accuracy_ci95": bootstrap_ci(y_te, (p_te >= threshold).astype(float),
                                                        lambda a, b: balanced_accuracy_score(a, b >= 0.5))},
        "test_current_stage2": summary(y_te, p_old, pred_old),
        "auc_gain_vs_current": float(roc_auc_score(y_te, p_te) - roc_auc_score(y_te, p_old)),
        "auc_gain_ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
        "two_stage_test": {"v2": summary(y_te, None, two_new), "current": summary(y_te, None, two_old)},
    }

    joblib.dump({"model": model, "features": FEATURES, "threshold": threshold, "version": "stage2-v2"},
                MODELS / "stage2_v2.joblib")
    (MODELS / "stage2_v2_metrics.json").write_text(json.dumps(metrics, indent=2))

    t, c = metrics["test"], metrics["test_current_stage2"]
    print("\nTest set (1,530 real patients)         current Stage 2      Stage 2 v2")
    print(f"  AUC                                   {c['auc']*100:6.1f}            {t['auc']*100:6.1f}  "
          f"(95% CI {t['auc_ci95'][0]*100:.1f}-{t['auc_ci95'][1]*100:.1f})")
    for k, label in [("balanced_accuracy", "Balanced accuracy"), ("pneumonia_recall", "Pneumonia found"),
                     ("control_recall", "Controls cleared")]:
        print(f"  {label:37s} {c[k]*100:6.1f}            {t[k]*100:6.1f}")
    lo, hi = metrics["auc_gain_ci95"]
    print(f"  AUC gain {metrics['auc_gain_vs_current']*100:+.1f}, 95% CI [{lo*100:+.1f}, {hi*100:+.1f}] -> "
          f"{'significant' if lo > 0 else 'not significant'}")
    tn, to = metrics["two_stage_test"]["v2"], metrics["two_stage_test"]["current"]
    print("\nTwo-stage system (unchanged Stage 1 -> Stage 2)   current      with v2")
    for k, label in [("balanced_accuracy", "Balanced accuracy"), ("pneumonia_recall", "Pneumonia found"),
                     ("control_recall", "Controls cleared")]:
        print(f"  {label:47s} {to[k]*100:6.1f}       {tn[k]*100:6.1f}")
    print(f"\nSaved {MODELS / 'stage2_v2.joblib'} and stage2_v2_metrics.json")


if __name__ == "__main__":
    main()
