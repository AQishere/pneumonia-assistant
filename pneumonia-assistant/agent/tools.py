"""Agent tools: JSON schemas for the model, Pydantic checks, HTTP calls to the API.

Tool schemas are not reliably enforced by every provider, and models sometimes
send malformed arguments. Every call is parsed and validated here first; a bad
call never reaches the API and comes back to the model as an error it can fix.
"""

import json
import math
import re
from datetime import datetime
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

PatientId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Binary = Literal[0, 1]
VITALS = ["heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetPatientArgs(_Args):
    patient_id: PatientId


class ReadingArg(_Args):
    vital: Literal["heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"]
    value: float
    unit: str | None = None
    taken_at: datetime | None = None


class AddReadingsArgs(_Args):
    patient_id: PatientId
    readings: list[ReadingArg] = Field(min_length=1, max_length=50)


class UpdateHistoryFlagsArgs(_Args):
    patient_id: PatientId
    copd: Binary | None = None
    heart_failure: Binary | None = None
    renal: Binary | None = None
    asthma: Binary | None = None
    diabetes: Binary | None = None
    hypertension: Binary | None = None


class AssessPatientArgs(_Args):
    patient_id: PatientId
    respiratory_distress: Binary          # required: the agent must ask, never assume
    hypoxemia: Binary | None = None
    cough: Binary | None = None           # symptoms the user reports; asked when Stage 2 needs them
    fever: Binary | None = None
    weakness: Binary | None = None


class GetAssessmentHistoryArgs(_Args):
    patient_id: PatientId
    limit: int = Field(default=10, ge=1, le=100)


_PATIENT_ID = {"type": "string", "description": "Patient id, for example demo-sick."}
_BINARY = {"type": "integer", "enum": [0, 1]}

TOOLS = [
    {"type": "function", "function": {
        "name": "get_patient",
        "description": "Get the user's record: current critical alerts, whether the device readings are "
                       "complete, conditions on record, latest lab results and readings. Call this first.",
        "parameters": {"type": "object", "properties": {"patient_id": _PATIENT_ID},
                       "required": ["patient_id"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "add_readings",
        "description": "Store a vital-sign reading the user measured themselves and told you. The server "
                       "validates every value; if any is rejected nothing is stored and you get the errors back.",
        "parameters": {"type": "object", "properties": {
            "patient_id": _PATIENT_ID,
            "readings": {"type": "array", "minItems": 1, "items": {
                "type": "object",
                "properties": {
                    "vital": {"type": "string", "enum": VITALS},
                    "value": {"type": "number"},
                    "unit": {"type": "string",
                             "description": "Unit the user gave: bpm, breaths/min, mmHg, %, °F (or °C)."},
                    "taken_at": {"type": "string",
                                 "description": "ISO 8601 time; leave out for a reading taken now."},
                },
                "required": ["vital", "value"], "additionalProperties": False}},
        }, "required": ["patient_id", "readings"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "update_history_flags",
        "description": "Record the user's answer about a long-term condition: COPD, heart failure, kidney "
                       "disease (renal), asthma, diabetes or high blood pressure (hypertension). "
                       "1 = yes, 0 = no. Send only the conditions the user answered.",
        "parameters": {"type": "object", "properties": {
            "patient_id": _PATIENT_ID, "copd": _BINARY, "heart_failure": _BINARY, "renal": _BINARY,
            "asthma": _BINARY, "diabetes": _BINARY, "hypertension": _BINARY,
        }, "required": ["patient_id"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "assess_patient",
        "description": "Run the risk check on the stored readings. Requires the user's answer to "
                       "'are you short of breath, even at rest?' (respiratory_distress: 1 = yes, 0 = no). "
                       "Include cough, fever and weakness when the user has answered them.",
        "parameters": {"type": "object", "properties": {
            "patient_id": _PATIENT_ID,
            "respiratory_distress": _BINARY,
            "cough": {**_BINARY, "description": "Does the user have a cough? Only if they said."},
            "fever": {**_BINARY, "description": "Does the user feel feverish? Only if they said."},
            "weakness": {**_BINARY, "description": "Unusually weak or tired? Only if they said."},
            "hypoxemia": {**_BINARY, "description": "Leave out unless a clinician stated it."},
        }, "required": ["patient_id", "respiratory_distress"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "get_assessment_history",
        "description": "Recent assessments for a patient, newest first (band and risk scores per run).",
        "parameters": {"type": "object", "properties": {
            "patient_id": _PATIENT_ID,
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        }, "required": ["patient_id"], "additionalProperties": False},
    }},
]

ARG_MODELS = {
    "get_patient": GetPatientArgs,
    "add_readings": AddReadingsArgs,
    "update_history_flags": UpdateHistoryFlagsArgs,
    "assess_patient": AssessPatientArgs,
    "get_assessment_history": GetAssessmentHistoryArgs,
}


def _error(code: str, message: str, **extra) -> dict:
    return {"error": True, "code": code, "message": message, **extra}


# A number on its own, not part of a word ("SpO2" does not yield 2).
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


class ReadingProvenance:
    """Code-level rule: a reading can only be stored if the doctor typed that value.

    The one exception is a correction the server suggested (for example 38.5 °C
    -> 101.3 °F), and only after the doctor has replied to it. Models sometimes
    invent plausible readings; the API can't tell a made-up 95 from a real one,
    so the check has to happen here, before the call.
    """

    def __init__(self):
        self.doctor_values: set[float] = set()
        self.suggested: set[float] = set()     # allowed once the doctor has replied
        self._pending: set[float] = set()      # suggested, doctor not asked yet

    def note_doctor_message(self, text: str):
        self.doctor_values |= {float(m) for m in _NUMBER.findall(text)}
        self.suggested |= self._pending
        self._pending = set()

    def note_tool_result(self, result: dict):
        for err in result.get("errors") or []:
            if isinstance(err, dict) and err.get("suggested_value") is not None:
                self._pending.add(float(err["suggested_value"]))

    def _known(self, value) -> bool:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return True        # not a number: leave it to argument validation
        return any(math.isclose(v, k, abs_tol=1e-6) for k in self.doctor_values | self.suggested)

    def check(self, name: str, arguments: str | None) -> dict | None:
        """An error for add_readings calls carrying values the doctor never gave; else None."""
        if name != "add_readings":
            return None
        try:
            readings = json.loads(arguments or "{}").get("readings")
        except (json.JSONDecodeError, AttributeError):
            return None        # malformed: argument validation reports it
        if not isinstance(readings, list):
            return None
        invented = [{"vital": r.get("vital"), "value": r.get("value")}
                    for r in readings if isinstance(r, dict) and not self._known(r.get("value"))]
        if not invented:
            return None
        return _error("VALUE_NOT_FROM_DOCTOR",
                      "These values do not appear in anything the user said, so nothing was stored. "
                      "Never invent or estimate a reading. If a reading is missing, ask the user for it; "
                      "if the readings are already on record, call assess_patient instead.",
                      values=invented)


class ScopedExecutor:
    """Wraps a ToolExecutor so every call is locked to one patient (the signed-in user)."""

    def __init__(self, inner: "ToolExecutor", patient_id: str):
        self.inner = inner
        self.patient_id = patient_id

    def execute(self, name: str, arguments: str | None) -> dict:
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return self.inner.execute(name, arguments)      # reports the bad JSON
        if isinstance(args, dict) and args.get("patient_id") not in (None, self.patient_id):
            return _error("WRONG_PATIENT", f"You can only use this user's own record "
                                           f"(patient_id '{self.patient_id}'). Nothing was done.")
        if isinstance(args, dict):
            args["patient_id"] = self.patient_id
            arguments = json.dumps(args)
        return self.inner.execute(name, arguments)


class ToolExecutor:
    """Parses, validates and runs tool calls against the FastAPI server."""

    def __init__(self, http: httpx.Client):
        self.http = http

    @classmethod
    def from_url(cls, base_url: str, api_key: str, timeout: float = 15.0) -> "ToolExecutor":
        return cls(httpx.Client(base_url=base_url, headers={"X-API-Key": api_key}, timeout=timeout))

    def execute(self, name: str, arguments: str | None) -> dict:
        """Run one tool call. Always returns a JSON-serialisable dict; errors have "error": true."""
        model = ARG_MODELS.get(name)
        if model is None:
            return _error("UNKNOWN_TOOL", f"There is no tool named '{name}'.", tools=list(ARG_MODELS))
        try:
            raw = json.loads(arguments or "{}")
        except json.JSONDecodeError as e:
            return _error("BAD_ARGUMENTS", f"Arguments are not valid JSON: {e}. Call the tool again.")
        if not isinstance(raw, dict):
            return _error("BAD_ARGUMENTS", "Arguments must be a JSON object. Call the tool again.")
        try:
            args = model.model_validate(raw)
        except ValidationError as e:
            details = [{"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
                       for err in e.errors(include_url=False)]
            hint = ""
            if name == "assess_patient" and any(d["field"] == "respiratory_distress" for d in details):
                hint = (" Ask the user whether they are short of breath, even at rest (yes/no); "
                        "never assume it.")
            return _error("BAD_ARGUMENTS", "Tool arguments failed validation; the API was not called." + hint,
                          details=details)
        return self._call(name, args)

    def _call(self, name: str, args: BaseModel) -> dict:
        pid = args.patient_id
        try:
            if name == "get_patient":
                r = self.http.get(f"/patients/{pid}")
            elif name == "add_readings":
                body = args.model_dump(mode="json", exclude_none=True, exclude={"patient_id"})
                r = self.http.post(f"/patients/{pid}/readings", json=body)
            elif name == "update_history_flags":
                body = args.model_dump(exclude_none=True, exclude={"patient_id"})
                if not body:
                    return _error("BAD_ARGUMENTS", "Send at least one condition answer.")
                r = self.http.put(f"/patients/{pid}/flags", json=body)
            elif name == "assess_patient":
                body = args.model_dump(exclude_none=True, exclude={"patient_id"})
                r = self.http.post(f"/patients/{pid}/assess", json=body)
            else:  # get_assessment_history
                r = self.http.get(f"/patients/{pid}/assessments", params={"limit": args.limit})
        except httpx.HTTPError as e:
            return _error("API_UNREACHABLE", f"Could not reach the assessment server ({type(e).__name__}).")

        try:
            body = r.json()
        except ValueError:
            body = {"detail": r.text}
        if r.status_code == 200:
            return body
        if r.status_code == 422:
            return {"error": True, "code": "VALIDATION_ERROR", "status": 422, **body}
        if r.status_code == 404:
            return _error("NOT_FOUND", body.get("detail", "Not found."), status=404)
        return _error("API_ERROR", body.get("detail", "Unexpected server error."), status=r.status_code)
