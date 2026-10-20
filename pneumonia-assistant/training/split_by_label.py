"""Write the Stage 2 v2 training patients to two CSVs, by label.

    python -m training.split_by_label

Training split only (the test set stays untouched), cleaned and with the model's
features, as used by train_stage2_v2 and train_stage2_cost. Writes
stage2_train_pneumonia.csv and stage2_train_non_pneumonia.csv in data/, next to the
dataset. MIMIC-derived: keep these files local.
"""

from training.train_stage2_v2 import DATA, load_split

X_tr, _, y_tr, _ = load_split()
data = X_tr.assign(pneumonia_label=y_tr)
for name, label in [("stage2_train_pneumonia.csv", 1), ("stage2_train_non_pneumonia.csv", 0)]:
    part = data[data.pneumonia_label == label]
    part.to_csv(DATA.parent / name, index=False)
    print(f"{name}: {len(part)} patients")
