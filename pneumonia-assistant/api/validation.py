"""Range and unit checks for vital-sign readings.

Values are never auto-corrected: a suspicious value comes back as a structured
error (with a suggestion where one exists) and the doctor must confirm it.
"""

import math
from datetime import datetime, timedelta

VITALS = ("heart_rate", "respiratory_rate", "sbp", "spo2", "temperature")

# Accepted ranges, in training units.
RANGES = {
    "heart_rate": (20, 250),
    "respiratory_rate": (4, 60),
    "sbp": (50, 250),
    "spo2": (50, 100),
    "temperature": (90, 110),
}

# Training unit for each vital, plus the spellings accepted for it (compared
# lower-case with spaces removed).
UNITS = {
    "heart_rate": ("bpm", {"bpm", "beats/min", "/min"}),
    "respiratory_rate": ("breaths/min", {"breaths/min", "/min", "rpm"}),
    "sbp": ("mmHg", {"mmhg"}),
    "spo2": ("%", {"%", "percent"}),
    "temperature": ("°F", {"f", "°f", "degf", "fahrenheit"}),
}
CELSIUS_UNITS = {"c", "°c", "degc", "celsius"}
LIKELY_CELSIUS_RANGE = (30, 45)

# Readings stamped further ahead than this are rejected as clock errors.
FUTURE_TOLERANCE = timedelta(minutes=5)


def celsius_to_fahrenheit(value: float) -> float:
    return round(value * 9 / 5 + 32, 1)


def _error(field, value, code, message, **extra) -> dict:
    return {"field": field, "value": value, "code": code, "message": message, **extra}


def _fmt(value: float) -> str:
    return f"{value:g}"


def check_reading(vital: str, value, unit: str | None = None) -> dict | None:
    """Return a structured error for one reading, or None if it is acceptable."""
    if vital not in RANGES:
        return _error(vital, value, "UNKNOWN_VITAL",
                      f"Unknown vital '{vital}'. Expected one of: {', '.join(VITALS)}.")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return _error(vital, value, "NOT_A_NUMBER", f"{vital} value must be a finite number.")

    lo, hi = RANGES[vital]
    training_unit, accepted = UNITS[vital]

    if unit is not None:
        u = unit.strip().lower().replace(" ", "")
        if vital == "temperature" and u in CELSIUS_UNITS:
            converted = celsius_to_fahrenheit(value)
            if lo <= converted <= hi:
                return _error(vital, value, "WRONG_UNIT",
                              f"Temperature must be entered in °F. {_fmt(value)} °C is "
                              f"{_fmt(converted)} °F. Ask the doctor to confirm, then resend in °F.",
                              suggested_value=converted, suggested_unit="°F")
            return _error(vital, value, "WRONG_UNIT",
                          f"Temperature must be entered in °F, and {_fmt(value)} °C is outside "
                          "the accepted range. Ask the doctor to check the value.")
        if u not in accepted:
            return _error(vital, value, "WRONG_UNIT",
                          f"{vital} must be entered in {training_unit}, not '{unit}'.",
                          expected_unit=training_unit)

    if vital == "temperature" and LIKELY_CELSIUS_RANGE[0] <= value <= LIKELY_CELSIUS_RANGE[1]:
        converted = celsius_to_fahrenheit(value)
        return _error(vital, value, "LIKELY_CELSIUS",
                      f"Temperature {_fmt(value)} looks like Celsius. Did you mean {_fmt(converted)} °F? "
                      "Nothing was stored; confirm with the doctor and resend in °F.",
                      suggested_value=converted, suggested_unit="°F")

    if not lo <= value <= hi:
        return _error(vital, value, "OUT_OF_RANGE",
                      f"{vital} {_fmt(value)} is outside the accepted range "
                      f"{lo} to {hi} {training_unit}. Ask the doctor to check the value.",
                      accepted_range=[lo, hi], unit=training_unit)
    return None


def check_taken_at(taken_at: datetime, now: datetime) -> dict | None:
    if taken_at > now + FUTURE_TOLERANCE:
        return _error("taken_at", taken_at.isoformat(), "FUTURE_TIMESTAMP",
                      "Reading time is in the future. Check the time it was taken.")
    return None


# Lab results, in the units of the training data: WBC 10^9/L (= K/uL), differentials %, CRP mg/L.
LAB_RANGES = {
    "wbc": (0.1, 100, "x10^9/L"),
    "neutrophils": (0, 100, "%"),
    "lymphocytes": (0, 100, "%"),
    "crp": (0, 500, "mg/L"),
}


def check_labs(labs: dict) -> list[dict]:
    """Structured errors for one set of lab results (never corrected automatically)."""
    errors = []
    for field, (lo, hi, unit) in LAB_RANGES.items():
        value = labs.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            errors.append(_error(field, value, "NOT_A_NUMBER", f"{field} must be a number in {unit}."))
        elif not lo <= value <= hi:
            errors.append(_error(field, value, "OUT_OF_RANGE",
                                 f"{field} {_fmt(value)} is outside the accepted range {lo} to {hi} {unit}. "
                                 "Check the value and its unit.", accepted_range=[lo, hi], unit=unit))
    n, l = labs.get("neutrophils"), labs.get("lymphocytes")
    if not errors and n + l > 100:
        errors.append(_error("neutrophils", n, "INCONSISTENT",
                             f"Neutrophils ({_fmt(n)}%) and lymphocytes ({_fmt(l)}%) add up to more than 100%."))
    return errors


def validate_readings(readings: list[dict]) -> list[dict]:
    """Check a batch of {vital, value, unit} readings; each error carries its index."""
    errors = []
    for i, r in enumerate(readings):
        err = check_reading(r.get("vital"), r.get("value"), r.get("unit"))
        if err:
            errors.append({"index": i, **err})
    return errors
