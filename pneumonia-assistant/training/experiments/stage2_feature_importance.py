"""Which features drive Stage 2 v2? Three views, on the same train/test split as training.

    python -m training.experiments.stage2_feature_importance

1. Permutation importance of the deployed model (models/stage2_v2.joblib): mean drop in
   test ROC AUC when one feature is shuffled. This is the model the app actually uses.
2. Random forest (Gini / mean decrease in impurity) importance: a random forest trained on
   the Stage 2 training data. A stand-in model, not the deployed one; Gini importance also
   favours continuous features with many split points.
3. CatBoost's own importance (PredictionValuesChange) for the CatBoost half of the ensemble.

Writes models/stage2_v2_importance.csv.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

from training.train_stage2_v2 import SEED, load_split

MODELS = Path(__file__).resolve().parents[2] / "models"


def main():
    bundle = joblib.load(MODELS / "stage2_v2.joblib")
    model, features = bundle["model"], bundle["features"]
    X_tr, X_te, y_tr, y_te = load_split()
    X_tr, X_te = X_tr[features], X_te[features]
    print(f"Train {len(X_tr)}, test {len(X_te)}, features {len(features)}")
    print(f"Deployed model test AUC: {roc_auc_score(y_te, model.predict_proba(X_te)[:, 1]):.3f}")

    perm = permutation_importance(model, X_te, y_te, scoring="roc_auc", n_repeats=20,
                                  random_state=SEED, n_jobs=-1)

    rf = Pipeline([("impute", SimpleImputer(strategy="median")),
                   ("rf", RandomForestClassifier(n_estimators=500, min_samples_leaf=5, class_weight="balanced",
                                                 random_state=SEED, n_jobs=-1))]).fit(X_tr, y_tr)
    print(f"Random forest test AUC:  {roc_auc_score(y_te, rf.predict_proba(X_te)[:, 1]):.3f}")

    catboost = model.named_estimators_["catboost"]

    table = pd.DataFrame({
        "perm_auc_drop": perm.importances_mean,
        "perm_std": perm.importances_std,
        "rf_gini": rf.named_steps["rf"].feature_importances_,
        "catboost": catboost.get_feature_importance() / 100,
    }, index=features).sort_values("perm_auc_drop", ascending=False)
    for col in ("perm_auc_drop", "rf_gini", "catboost"):
        table[f"{col}_rank"] = table[col].rank(ascending=False).astype(int)

    table.to_csv(MODELS / "stage2_v2_importance.csv", float_format="%.5f")
    with pd.option_context("display.width", 140, "display.max_rows", 60):
        print(table.round(4).to_string())
    print(f"\nSaved {MODELS / 'stage2_v2_importance.csv'}")


if __name__ == "__main__":
    main()
