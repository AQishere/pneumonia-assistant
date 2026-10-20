"""Accuracy and ROC AUC on the test set for current Stage 2, Stage 2 v2 and the two-stage system.

    python -m training.report_metrics
"""

import joblib
from sklearn.metrics import accuracy_score, roc_auc_score

from training.train_stage2_v2 import MODELS, load_split


def main():
    _, X_te, _, y_te = load_split()
    s1 = joblib.load(MODELS / "stage1.joblib")
    old = joblib.load(MODELS / "stage2.joblib")
    v2 = joblib.load(MODELS / "stage2_v2.joblib")

    p1 = s1["model"].predict_proba(X_te[s1["features"]])[:, 1]
    po = old["model"].predict_proba(X_te[old["features"]])[:, 1]
    p2 = v2["model"].predict_proba(X_te[v2["features"]])[:, 1]
    flagged = p1 >= s1["threshold"]

    print(f"Test set: {len(y_te)} patients, {y_te.mean()*100:.1f}% pneumonia "
          f"(calling everyone 'pneumonia' would score {y_te.mean()*100:.1f}% accuracy)\n")
    print(f"{'':28s}{'ROC AUC':>9s}{'Accuracy':>10s}")
    print(f"{'Stage 1 (unchanged)':28s}{roc_auc_score(y_te, p1)*100:9.1f}"
          f"{accuracy_score(y_te, flagged)*100:10.1f}")
    print(f"{'Stage 2 current':28s}{roc_auc_score(y_te, po)*100:9.1f}"
          f"{accuracy_score(y_te, po >= old['threshold'])*100:10.1f}")
    print(f"{'Stage 2 v2':28s}{roc_auc_score(y_te, p2)*100:9.1f}"
          f"{accuracy_score(y_te, p2 >= v2['threshold'])*100:10.1f}")
    print(f"{'Two-stage, current':28s}{roc_auc_score(y_te, flagged * po)*100:9.1f}"
          f"{accuracy_score(y_te, flagged & (po >= old['threshold']))*100:10.1f}")
    print(f"{'Two-stage, with v2':28s}{roc_auc_score(y_te, flagged * p2)*100:9.1f}"
          f"{accuracy_score(y_te, flagged & (p2 >= v2['threshold']))*100:10.1f}")


if __name__ == "__main__":
    main()
