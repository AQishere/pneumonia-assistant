"""Loads the two trained pipelines and runs Stage 1 -> Stage 2.

Outputs are risk scores, not probabilities: the models were trained with class
weighting. Moderate and High are only ever returned when Stage 2 actually ran.
"""

import hashlib
import os
from pathlib import Path

import joblib
import pandas as pd

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
# Stage 2 v2 (labs, symptoms, full profile) is the default; stage2.joblib is the original model.
DEFAULT_STAGE2 = os.getenv("STAGE2_MODEL", "stage2_v2.joblib")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


class Predictor:
    def __init__(self, models_dir: Path = MODELS_DIR, stage2_file: str = DEFAULT_STAGE2):
        models_dir = Path(models_dir)
        self.stage1 = joblib.load(models_dir / "stage1.joblib")
        self.stage2 = joblib.load(models_dir / stage2_file)
        self.stage2_version = self.stage2.get("version", "stage2-v1")
        self.model_version = (f"stage1:{_file_hash(models_dir / 'stage1.joblib')}, "
                              f"{self.stage2_version}:{_file_hash(models_dir / stage2_file)}")

    @property
    def threshold_stage1(self) -> float:
        return float(self.stage1["threshold"])

    @property
    def threshold_stage2(self) -> float:
        return float(self.stage2["threshold"])

    @staticmethod
    def _score(bundle: dict, features: dict) -> float:
        cols = bundle["features"]
        absent = [c for c in cols if features.get(c) is None]
        if absent:
            # Never fill a feature in: the caller must report it as missing instead.
            raise ValueError(f"Missing features: {absent}")
        row = pd.DataFrame([{c: features[c] for c in cols}])
        return float(bundle["model"].predict_proba(row)[0, 1])

    def run(self, features_stage1: dict, features_stage2: dict | None = None) -> dict:
        """features_stage2 is None when Stage 2 inputs are missing."""
        p1 = self._score(self.stage1, features_stage1)
        out = {"stage": 1, "p_stage1": p1, "p_stage2": None, "model_version": self.model_version}
        if p1 < self.threshold_stage1:
            return {**out, "band": "Low"}
        if features_stage2 is None:
            return {**out, "band": "Pending"}
        p2 = self._score(self.stage2, features_stage2)
        band = "High" if p2 >= self.threshold_stage2 else "Moderate"
        return {**out, "stage": 2, "p_stage2": p2, "band": band}
