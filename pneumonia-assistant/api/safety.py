"""Critical-value alerts and the derived hypoxemia flag.

`alerts` is called with the last 24 h of readings only: it describes the
patient's current state. `derive_hypoxemia` is called with the Stage 2 window
(7 days), so it stays consistent with Stage 2's spo2_min.
"""

LOW_SPO2 = 90
HIGH_RESPIRATORY_RATE = 30
LOW_SBP = 90


def _fmt(value: float) -> str:
    return f"{value:g}"


def alerts(readings_24h: dict[str, list[float]]) -> list[dict]:
    out = []
    spo2 = readings_24h.get("spo2") or []
    if spo2 and min(spo2) < LOW_SPO2:
        v = float(min(spo2))
        out.append({"code": "LOW_SPO2",
                    "message": f"Blood oxygen (SpO2) dropped to {_fmt(v)}% (below {LOW_SPO2}%)", "value": v})
    rr = readings_24h.get("respiratory_rate") or []
    if rr and max(rr) > HIGH_RESPIRATORY_RATE:
        v = float(max(rr))
        out.append({"code": "HIGH_RESPIRATORY_RATE",
                    "message": f"Breathing rate reached {_fmt(v)} breaths per minute "
                               f"(above {HIGH_RESPIRATORY_RATE})", "value": v})
    sbp = readings_24h.get("sbp") or []
    if sbp and min(sbp) < LOW_SBP:
        v = float(min(sbp))
        out.append({"code": "LOW_SBP",
                    "message": f"Blood pressure (top number) dropped to {_fmt(v)} mmHg (below {LOW_SBP})",
                    "value": v})
    return out


def derive_hypoxemia(readings_7d: dict[str, list[float]], doctor_flag: int | None) -> int:
    """1 if any SpO2 in the window is below 90, or the doctor set it to 1."""
    if doctor_flag == 1:
        return 1
    return int(any(v < LOW_SPO2 for v in readings_7d.get("spo2") or []))
