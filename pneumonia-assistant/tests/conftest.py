from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from api.predictor import Predictor

# Cleaned data lives next to the notebook, outside the app; tests only.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)

# The notebook's test patients (cell 12).
SICK = {"heart_rate": [105, 118, 124, 112], "respiratory_rate": [26, 32, 35, 30],
        "sbp": [100, 92, 88, 95], "spo2": [91, 87, 85, 89],
        "temperature": [100.2, 101.8, 102.4, 101.0]}
HEALTHY = {"heart_rate": [72, 78, 75, 80], "respiratory_rate": [14, 16, 15, 17],
           "sbp": [125, 130, 122, 128], "spo2": [98, 97, 99, 98],
           "temperature": [98.2, 98.6, 98.4, 98.5]}
NO_HISTORY = {"copd": 0, "heart_failure": 0, "renal": 0}


def as_readings(values: dict, hours_ago: float = 1.0, now: datetime = NOW) -> list[dict]:
    """Turn {vital: [values]} into stored-reading dicts, all `hours_ago` before now."""
    out = []
    for vital, vals in values.items():
        for i, v in enumerate(vals):
            out.append({"vital": vital, "value": float(v), "entered_by": "seed",
                        "taken_at": now - timedelta(hours=hours_ago, minutes=10 * i)})
    return out


@pytest.fixture(scope="session")
def predictor():
    return Predictor()
