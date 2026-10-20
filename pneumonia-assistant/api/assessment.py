"""One assessment: windows -> alerts -> Stage 1 -> maybe Stage 2 -> fixed text.

Pure logic (no web, no database), so the API route and the seed script share it.
Input checks run stage by stage:
  1. Safety alerts always run on the last 24 h, whatever else is missing.
  2. Stage 1 inputs missing -> "missing", no score, nothing to store.
  3. Stage 1 Low -> Low; Stage 2 gaps don't matter.
  4. Stage 1 flags but Stage 2 inputs missing -> Pending (stage 1).
  5. Otherwise Stage 2 runs -> Moderate, or for a positive Stage 2 result:
       - score >= IMMEDIATE_HIGH                      -> High straight away
       - previous assessment 4-36 h ago also positive  -> High (confirmed)
       - otherwise                                    -> Watch (still flagged; reassess to confirm)
     This persistence rule cuts false alarms from one-off results without dropping any
     flagged patient. Its settings are starting points: validate them on real device data.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from api import features, features_v2, safety, templates
from api.predictor import Predictor
from api.validation import VITALS

STAGE1_WINDOW = timedelta(hours=24)
STAGE2_WINDOW = timedelta(days=7)
WINDOWS = {"stage1": "24h", "stage2": "7d", "alerts": "24h", "hypoxemia": "7d"}

# Persistence rule for positive Stage 2 results.
IMMEDIATE_HIGH = 0.70                  # this confident: High without waiting for a repeat
CONFIRM_MIN_GAP = timedelta(hours=4)   # a repeat this soon has no new data, so it can't confirm
CONFIRM_WINDOW = timedelta(hours=36)   # a previous positive older than this no longer counts


@dataclass
class Outcome:
    response: dict
    record: dict | None   # assessment document to store; None when no model ran


def group_readings(readings: list[dict], since: datetime, until: datetime) -> dict[str, list[float]]:
    """{vital: [values]} for readings with since <= taken_at <= until, oldest first."""
    out = {v: [] for v in VITALS}
    for r in sorted(readings, key=lambda r: r["taken_at"]):
        if since <= r["taken_at"] <= until and r["vital"] in out:
            out[r["vital"]].append(float(r["value"]))
    return out


def display_score(p: float | None, threshold: float) -> float | None:
    """Round to 3 decimals without ever rounding across the threshold."""
    if p is None:
        return None
    r = round(p, 3)
    if p < threshold <= r:
        r = math.floor(p * 1000) / 1000
    return r


def _subset(feats: dict, names: list[str]) -> dict:
    return {n: feats[n] for n in names}


def persistence(p_stage2: float, threshold: float, history: list[dict], now: datetime) -> tuple[str, dict]:
    """Band and persistence details for a positive Stage 2 result (p_stage2 >= threshold).

    history: stored assessment records (any order). Only the most recent Stage 2 record
    between CONFIRM_WINDOW and CONFIRM_MIN_GAP ago is considered.
    """
    if p_stage2 >= IMMEDIATE_HIGH:
        return "High", {"status": "immediate",
                        "reason": f"Stage 2 risk score at or above {IMMEDIATE_HIGH}; no repeat needed."}
    eligible = [h for h in history
                if h.get("stage") == 2 and now - CONFIRM_WINDOW <= h["created_at"] <= now - CONFIRM_MIN_GAP]
    previous = max(eligible, key=lambda h: h["created_at"], default=None)
    if previous is not None and previous.get("stage2_positive", previous.get("band") in ("Watch", "High")):
        return "High", {"status": "confirmed", "confirmed_by": previous["created_at"],
                        "reason": "Stage 2 was also positive at the previous assessment."}
    return "Watch", {"status": "first_positive",
                     "reassess_after": now + CONFIRM_MIN_GAP, "reassess_before": now + CONFIRM_WINDOW,
                     "reason": "First positive Stage 2 result; a repeat assessment 4 to 36 hours later "
                               "confirms it."}


def assess(readings: list[dict], history: dict, respiratory_distress: int | None,
           hypoxemia_flag: int | None, predictor: Predictor, now: datetime,
           previous: list[dict] | None = None, symptoms: dict | None = None,
           labs: dict | None = None) -> Outcome:
    """history: the patient's profile (conditions, age, sex). previous: stored assessment records,
    for persistence. symptoms: today's cough/fever/weakness answers. labs: latest lab results.
    symptoms and labs are only used by Stage 2 v2."""
    symptoms = symptoms or {}
    r24 = group_readings(readings, now - STAGE1_WINDOW, now)
    r7 = group_readings(readings, now - STAGE2_WINDOW, now)

    alerts = safety.alerts(r24)
    hypoxemia = safety.derive_hypoxemia(r7, hypoxemia_flag)
    response = {
        "stage": None,
        "band": None,
        "risk_score_stage1": None,
        "risk_score_stage2": None,
        "alerts": alerts,
        "critical_notice": templates.CRITICAL_NOTICE if alerts else None,
        "lead_text": templates.lead_text(alerts),
        "hypoxemia_derived": hypoxemia,
        "windows": dict(WINDOWS),
        "recommendation": None,
        "data_quality": [],
        "missing": [],
        "persistence": None,
        "model_version": predictor.model_version,
        "score_note": templates.SCORE_NOTE,
        "disclaimer": templates.DISCLAIMER,
        "assessed_at": now,
    }

    missing1 = features.missing_stage1(r24, respiratory_distress)
    if missing1:
        response.update(missing=missing1, note=templates.STAGE1_MISSING_NOTE)
        return Outcome(response, None)

    f1 = features.build_features(r24, {"respiratory_distress": respiratory_distress})
    v2 = predictor.stage2_version == "stage2-v2"
    f2 = None
    if v2:
        missing2 = features.missing_stage2_v2(r7, history, symptoms, labs)
        if not missing2:
            f2 = features_v2.from_app_inputs(features.build_features(r7, {}), history, symptoms, labs,
                                             respiratory_distress, hypoxemia)
    else:
        missing2 = features.missing_stage2(r7, history)
        if not missing2:
            f2 = features.build_features(r7, {
                "respiratory_distress": respiratory_distress,
                "hypoxemia": hypoxemia,
                **{k: history[k] for k in features.HISTORY_FLAGS},
            })

    result = predictor.run(f1, f2)
    band, stage = result["band"], result["stage"]
    stage2_positive = stage == 2 and result["p_stage2"] >= predictor.threshold_stage2
    persistence_info = None
    if stage2_positive:
        band, persistence_info = persistence(result["p_stage2"], predictor.threshold_stage2,
                                             previous or [], now)
    quality = features.data_quality(r24, "24h", 1)
    if stage == 2:
        quality += features.data_quality(r7, "7d", 2)

    response.update(
        stage=stage,
        band=band,
        risk_score_stage1=display_score(result["p_stage1"], predictor.threshold_stage1),
        risk_score_stage2=display_score(result["p_stage2"], predictor.threshold_stage2),
        band_meaning=templates.BAND_MEANING[band],
        recommendation=templates.RECOMMENDATIONS[band],
        data_quality=quality,
        missing=missing2 if band == "Pending" else [],
        persistence=persistence_info,
    )

    features_stage1 = _subset(f1, predictor.stage1["features"])
    features_stage2 = _subset(f2, predictor.stage2["features"]) if stage == 2 else None
    record = {
        "created_at": now,
        "window": "7d" if stage == 2 else "24h",
        "windows": dict(WINDOWS),
        "stage": stage,
        "band": band,
        "p_stage1": result["p_stage1"],
        "p_stage2": result["p_stage2"],
        "stage2_positive": stage2_positive,
        "persistence_status": persistence_info["status"] if persistence_info else None,
        "alerts": alerts,
        "missing": response["missing"],
        "flags_used": {
            "respiratory_distress": respiratory_distress,
            "hypoxemia": hypoxemia,
            **{k: history.get(k) for k in (features.CONDITIONS if v2 else features.HISTORY_FLAGS)},
            **({k: symptoms.get(k) for k in features.SYMPTOMS} if v2 else {}),
        },
        "labs_used": ({k: labs[k] for k in (*features.LAB_FIELDS, "taken_at") if k in labs}
                      if v2 and labs and stage == 2 else None),
        "features_stage1": features_stage1,
        "features_stage2": features_stage2,
        "model_version": predictor.model_version,
    }
    return Outcome(response, record)
