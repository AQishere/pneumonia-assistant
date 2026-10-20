"""Cost-sensitive Stage 2 v2: a missed pneumonia costs `ratio` times a false alarm.

    python -m training.train_stage2_cost [ratio | faN | equal] [--optuna]

Trains on stage2_train_pneumonia.csv + stage2_train_non_pneumonia.csv (made by
training.split_by_label); the test set is the usual held-out split.
faN (e.g. fa3) is the reverse: a false alarm costs N times a missed pneumonia.

Uses the original Stage 2 v2 settings; --optuna uses models/stage2_v2_tuning.json
instead. The cost goes into training as class weights, and the threshold is the
one with the lowest cost on out-of-fold training scores, where
cost = ratio * share of pneumonia missed + share of controls flagged.
"equal" trains with ratio 1 and picks the threshold where the share of pneumonia
caught equals the share of controls cleared.
Compares ratios 1, 2, 3 and 5 (and equal) on the test set, alone and after
Stage 1 as in the app, then saves the chosen model (default equal) as
models/stage2_v2.joblib, with results in models/stage2_v2_cost.json.
"""

import json
import sys

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from api.features_v2 import FEATURES
from training.train_stage2_v2 import DATA, MODELS, SEED, load_split

RATIOS = [1 / 5, 1 / 3, 1 / 2, 1, 2, 3, 5]
CURRENT = {"lr_C": 1.0, "iterations": 700, "depth": 4, "learning_rate": 0.04, "l2_leaf_reg": 5,
           "random_strength": 1.0, "bagging_temperature": 1.0, "cat_weight": 0.5}

_, X_te, _, y_te = load_split()
_train = pd.concat([pd.read_csv(DATA.parent / f) for f in
                    ("stage2_train_pneumonia.csv", "stage2_train_non_pneumonia.csv")], ignore_index=True)
X_tr, y_tr = _train[FEATURES], _train["pneumonia_label"]
_s1 = joblib.load(MODELS / "stage1.joblib")
STAGE1_FLAG = _s1["model"].predict_proba(X_te[_s1["features"]])[:, 1] >= _s1["threshold"]
folds = list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(X_tr, y_tr))
tuning_file = MODELS / "stage2_v2_tuning.json"
USE_OPTUNA = "--optuna" in sys.argv
PARAMS = json.loads(tuning_file.read_text())["best_params"] if USE_OPTUNA else CURRENT


def class_weights(ratio):
    """Balanced weights (each class counts equally overall), then pneumonia multiplied by the cost ratio."""
    n, n_pos = len(y_tr), int(y_tr.sum())
    return {0: n / (2 * (n - n_pos)), 1: ratio * n / (2 * n_pos)}


def make_model(ratio, p=PARAMS):
    w = class_weights(ratio)
    lr = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                   ("clf", LogisticRegression(C=p["lr_C"], max_iter=3000, class_weight=w))])
    cat = CatBoostClassifier(iterations=p["iterations"], depth=p["depth"], learning_rate=p["learning_rate"],
                             l2_leaf_reg=p["l2_leaf_reg"], random_strength=p["random_strength"],
                             bagging_temperature=p["bagging_temperature"],
                             class_weights=(w[0], w[1]),   # a tuple: a list or dict breaks sklearn's clone
                             random_seed=SEED, verbose=0, thread_count=-1)
    return VotingClassifier([("logreg", lr), ("catboost", cat)], voting="soft",
                            weights=[1 - p["cat_weight"], p["cat_weight"]])


def cost(y, pred, ratio):
    return ratio * ((pred == 0) & (y == 1)).sum() / (y == 1).sum() + ((pred == 1) & (y == 0)).sum() / (y == 0).sum()


def run(ratio, equal=False):
    oof = np.zeros(len(X_tr))
    for a, b in folds:
        oof[b] = make_model(ratio).fit(X_tr.loc[a], y_tr[a]).predict_proba(X_tr.loc[b])[:, 1]
    ths = np.round(np.arange(0.05, 0.96, 0.01), 2)
    y = y_tr.values
    if equal:
        gap = [abs((oof[y == 1] >= t).mean() - (oof[y == 0] < t).mean()) for t in ths]
        threshold = float(ths[np.argmin(gap)])
    else:
        threshold = float(ths[np.argmin([cost(y, (oof >= t).astype(int), ratio) for t in ths])])
    model = make_model(ratio).fit(X_tr, y_tr)
    p = model.predict_proba(X_te)[:, 1]
    pred = (p >= threshold).astype(int)
    app = (STAGE1_FLAG & (pred == 1)).astype(int)   # Stage 1 -> Stage 2, as in the app
    yt = y_te.values
    return model, {"ratio": "equal" if equal else ratio, "threshold": threshold, "auc": float(roc_auc_score(yt, p)),
                   "pneumonia_recall": float(recall_score(yt, pred)),
                   "control_recall": float(recall_score(yt, pred, pos_label=0)),
                   "missed": int(((pred == 0) & (yt == 1)).sum()), "false_alarms": int(((pred == 1) & (yt == 0)).sum()),
                   "app_pneumonia_recall": float(recall_score(yt, app)),
                   "app_control_recall": float(recall_score(yt, app, pos_label=0))}


def label(r):
    if r == "equal":
        return r
    return f"fa {1 / r:g}x" if r < 1 else f"{r:g}x"


def main():
    args = [a for a in sys.argv[1:] if a != "--optuna"]
    arg = args[0] if args else "equal"
    chosen = "equal" if arg == "equal" else 1 / float(arg[2:]) if arg.startswith("fa") else float(arg)
    ratios = sorted(set(RATIOS) | ({chosen} if chosen != "equal" else set())) + ["equal"]
    print(f"Settings: {'Optuna (' + tuning_file.name + ')' if USE_OPTUNA else 'original Stage 2 v2'}")
    print(f"Test set: {int(y_te.sum())} pneumonia, {int((y_te == 0).sum())} without\n")
    print(f"{'cost':>13s} {'threshold':>10s} {'AUC':>6s} {'pneumonia found':>16s} {'controls cleared':>17s} "
          f"{'missed':>7s} {'false alarms':>13s} {'app: found':>11s} {'app: cleared':>13s}")
    results, models = [], {}
    for r in ratios:
        models[r], m = run(1 if r == "equal" else r, equal=r == "equal")
        results.append(m)
        print(f"{label(r):>13s} {m['threshold']:>10.2f} {m['auc'] * 100:>6.1f} {m['pneumonia_recall'] * 100:>15.1f}% "
              f"{m['control_recall'] * 100:>16.1f}% {m['missed']:>7d} {m['false_alarms']:>13d} "
              f"{m['app_pneumonia_recall'] * 100:>10.1f}% {m['app_control_recall'] * 100:>12.1f}%")

    best = next(m for m in results if m["ratio"] == chosen)
    joblib.dump({"model": models[chosen], "features": FEATURES, "threshold": best["threshold"], "version": "stage2-v2",
                 "cost_ratio": 1 if chosen == "equal" else chosen,
                 "threshold_rule": "equal" if chosen == "equal" else "min_cost", "params": PARAMS},
                MODELS / "stage2_v2.joblib")
    (MODELS / "stage2_v2_cost.json").write_text(json.dumps({"chosen": chosen, "params": PARAMS,
                                                            "results": results}, indent=2))
    print(f"\nSaved the {label(chosen)} model as {MODELS / 'stage2_v2.joblib'} (threshold {best['threshold']})")


if __name__ == "__main__":
    main()
