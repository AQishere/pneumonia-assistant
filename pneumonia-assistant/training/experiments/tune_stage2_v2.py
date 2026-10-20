"""Tune Stage 2 v2 with Optuna: CatBoost and logistic regression settings, and how much each counts.

    python -m training.experiments.tune_stage2_v2 [n_trials]

Each trial is scored by 5-fold CV AUC on the training data only; the test set is
used once, at the end, to compare the tuned model with the current one.
Writes models/stage2_v2_tuning.json. Does not replace stage2_v2.joblib.
"""

import json
import sys

import numpy as np
import optuna
from catboost import CatBoostClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from training.train_stage2_v2 import MODELS, SEED, bootstrap_ci, load_split, make_model

X_tr, X_te, y_tr, y_te = load_split()
folds = list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(X_tr, y_tr))


def make_lr(p):
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                     ("clf", LogisticRegression(C=p["lr_C"], max_iter=3000, class_weight="balanced"))])


def make_cat(p):
    return CatBoostClassifier(iterations=p["iterations"], depth=p["depth"], learning_rate=p["learning_rate"],
                              l2_leaf_reg=p["l2_leaf_reg"], random_strength=p["random_strength"],
                              bagging_temperature=p["bagging_temperature"], auto_class_weights="Balanced",
                              random_seed=SEED, verbose=0, thread_count=-1)


def blend(p, a, b, X_out):
    """Weighted average of the two models' probabilities, trained on rows a of the training data."""
    lr = make_lr(p).fit(X_tr.loc[a], y_tr[a]).predict_proba(X_out)[:, 1]
    cat = make_cat(p).fit(X_tr.loc[a], y_tr[a]).predict_proba(X_out)[:, 1]
    return p["cat_weight"] * cat + (1 - p["cat_weight"]) * lr


def objective(trial):
    p = {"lr_C": trial.suggest_float("lr_C", 0.005, 10, log=True),
         "iterations": trial.suggest_int("iterations", 300, 1500, step=100),
         "depth": trial.suggest_int("depth", 3, 7),
         "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.12, log=True),
         "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1, 30, log=True),
         "random_strength": trial.suggest_float("random_strength", 0.1, 5, log=True),
         "bagging_temperature": trial.suggest_float("bagging_temperature", 0, 3),
         "cat_weight": trial.suggest_float("cat_weight", 0, 1)}
    aucs = []
    for i, (a, b) in enumerate(folds):
        aucs.append(roc_auc_score(y_tr[b], blend(p, a, b, X_tr.loc[b])))
        trial.report(float(np.mean(aucs)), i)
        if trial.should_prune():
            raise optuna.TrialPruned()
    return float(np.mean(aucs))


def main():
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED),
                                pruner=optuna.pruners.MedianPruner(n_startup_trials=8, n_warmup_steps=1))
    # Trial 0 is the current model's settings, so the search starts from it.
    study.enqueue_trial({"lr_C": 1.0, "iterations": 700, "depth": 4, "learning_rate": 0.04, "l2_leaf_reg": 5,
                         "random_strength": 1.0, "bagging_temperature": 1.0, "cat_weight": 0.5})
    study.optimize(objective, n_trials=n_trials,
                   callbacks=[lambda s, t: print(f"trial {t.number:3d}  {t.state.name:8s} "
                                                 f"CV AUC {t.value * 100 if t.value else float('nan'):.2f}  "
                                                 f"best {s.best_value * 100:.2f}", flush=True)])
    p = study.best_params
    current_cv = study.trials[0].value

    # Threshold on out-of-fold scores (training data only), as in train_stage2_v2.
    oof = np.zeros(len(X_tr))
    for a, b in folds:
        oof[b] = blend(p, a, b, X_tr.loc[b])
    ths = np.round(np.arange(0.20, 0.81, 0.01), 2)
    threshold = float(ths[np.argmax([balanced_accuracy_score(y_tr, oof >= t) for t in ths])])

    # One look at the test set: tuned vs current, both trained on all training data.
    tuned = blend(p, np.arange(len(X_tr)), None, X_te)
    current = make_model().fit(X_tr, y_tr).predict_proba(X_te)[:, 1]
    current_thr = json.loads((MODELS / "stage2_v2_metrics.json").read_text())["threshold"]

    def summary(score, thr):
        pred = (score >= thr).astype(int)
        return {"auc": float(roc_auc_score(y_te, score)), "auc_ci95": bootstrap_ci(y_te, score, roc_auc_score),
                "pneumonia_recall": float(recall_score(y_te, pred)),
                "control_recall": float(recall_score(y_te, pred, pos_label=0)),
                "missed": int(((pred == 0) & (y_te == 1)).sum()), "false_alarms": int(((pred == 1) & (y_te == 0)).sum())}

    out = {"best_params": p, "threshold": threshold, "cv_auc_tuned": study.best_value, "cv_auc_current": current_cv,
           "n_trials": n_trials, "test_tuned": summary(tuned, threshold), "test_current": summary(current, current_thr)}
    (MODELS / "stage2_v2_tuning.json").write_text(json.dumps(out, indent=2))

    print(f"\nBest settings: {p}")
    print(f"CV AUC (training data)   current {current_cv * 100:.2f}   tuned {study.best_value * 100:.2f}")
    print(f"\nTest set                 current      tuned")
    c, t = out["test_current"], out["test_tuned"]
    print(f"  AUC                    {c['auc'] * 100:6.1f}     {t['auc'] * 100:6.1f}  "
          f"(95% CI {t['auc_ci95'][0] * 100:.1f}-{t['auc_ci95'][1] * 100:.1f})")
    print(f"  Pneumonia found        {c['pneumonia_recall'] * 100:6.1f}     {t['pneumonia_recall'] * 100:6.1f}")
    print(f"  Controls cleared       {c['control_recall'] * 100:6.1f}     {t['control_recall'] * 100:6.1f}")
    print(f"  Missed pneumonia       {c['missed']:6d}     {t['missed']:6d}")
    print(f"  False alarms           {c['false_alarms']:6d}     {t['false_alarms']:6d}")
    print(f"  Threshold              {current_thr:6.2f}     {threshold:6.2f}")


if __name__ == "__main__":
    main()
