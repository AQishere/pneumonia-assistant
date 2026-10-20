"""Checks on the model's behaviour that run in code, not in the prompt.

- alerts_first: a reply must state every critical alert before any risk band.
- find_stated_readings: readings the doctor typed, so the agent loop can make
  sure each one was sent to the server for validation rather than ignored.
"""

import re

_TYPOGRAPHY = {"₂": "2", "‑": "-", "‐": "-", "–": "-", "—": "-",
               " ": " ", " ": " "}
_BAND_WORD = re.compile(r"\b(low|pending|moderate|watch|high)\b")


def fold(text: str) -> str:
    """Lower-case, typography folded to ASCII, markdown emphasis removed, spaces collapsed."""
    for a, b in _TYPOGRAPHY.items():
        text = text.replace(a, b)
    text = re.sub(r"[*_`#>]", "", text.lower())
    text = re.sub(r"\s+%", "%", text)
    return re.sub(r"\s+", " ", text).strip()


def alerts_first(reply: str, result: dict) -> bool:
    """True if the reply states the critical notice and every alert before any band word."""
    if not result.get("lead_text"):
        return True
    text = fold(reply)
    band = _BAND_WORD.search(text)
    limit = band.start() if band else len(text)
    parts = [result["critical_notice"]] + [a["message"] for a in result.get("alerts") or []]
    return all(0 <= text.find(fold(p)) < limit for p in parts)


# Names a doctor might use for each vital (matched on folded text).
_VITAL_NAMES = {
    "temperature": r"temp|temperature",
    "spo2": r"spo2|sp02|sats?|o2 sats?|saturation|oxygen saturation",
    "heart_rate": r"heart rate|hr|pulse",
    "respiratory_rate": r"respiratory rate|resp rate|rr|breathing rate",
    "sbp": r"sbp|systolic(?: bp| blood pressure)?|bp|blood pressure",
}
_FILLER = r"(?:\s*(?:is|was|of|at|now|today|=|:|-))*\s*"
_NUMBER = r"(\d+(?:\.\d+)?)"
_PATTERNS = [(vital, re.compile(rf"\b(?:{names})\b{_FILLER}{_NUMBER}"))
             for vital, names in _VITAL_NAMES.items()]
_DEGREES = re.compile(rf"{_NUMBER}\s*°\s*[fc]\b")


def find_stated_readings(text: str) -> list[tuple[str, float]]:
    """(vital, value) pairs the doctor stated, for example "temperature is 10" or "BP 120/80"."""
    folded = fold(text)
    found = []
    for vital, pattern in _PATTERNS:
        found += [(vital, float(m.group(1))) for m in pattern.finditer(folded)]
    found += [("temperature", float(m.group(1))) for m in _DEGREES.finditer(folded)]
    return list(dict.fromkeys(found))     # dedupe, keep order


def nudge_for(unsent: list[tuple[str, float]]) -> str:
    given = ", ".join(f"{vital} {value:g}" for vital, value in unsent)
    return ("(Automatic check, not from the doctor.) The doctor's last message gave: "
            f"{given}, but you did not send it with add_readings. Send exactly those values with "
            "add_readings now so the server can check them, then reply to the doctor.")
