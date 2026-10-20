"""Request bodies. Values are only type-checked here; range and unit checks
live in validation.py so they come back as structured, machine-readable errors."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Vital = Literal["heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"]
Binary = Literal[0, 1]
Sex = Literal["female", "male", "other", "prefer_not_to_say"]


class ReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vital: Vital
    value: float
    unit: str | None = None
    taken_at: datetime | None = None          # defaults to now; naive times are read as UTC
    entered_by: Literal["patient", "doctor", "device"] = "patient"


class ReadingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readings: list[ReadingIn] = Field(min_length=1, max_length=200)


class _Conditions(BaseModel):
    """Long-term conditions (1 = yes, 0 = no). Optional here; required at signup."""
    model_config = ConfigDict(extra="forbid")

    copd: Binary | None = None
    heart_failure: Binary | None = None
    renal: Binary | None = None
    asthma: Binary | None = None
    diabetes: Binary | None = None
    hypertension: Binary | None = None


class FlagsIn(_Conditions):
    """Condition answers. A field left out (or null) is left unchanged."""

    @model_validator(mode="after")
    def at_least_one(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("Provide at least one condition (0 or 1).")
        return self


class PatientIn(BaseModel):
    """Signup. Every condition is a required yes/no answer, so the agent never has to ask."""
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$",
                            description="The Firebase Auth uid of the patient's account.")
    display_name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=120)
    sex: Sex
    copd: Binary
    heart_failure: Binary
    renal: Binary
    asthma: Binary
    diabetes: Binary
    hypertension: Binary
    doctor_ids: list[str] = Field(default_factory=list, max_length=20)


class PatientPatch(_Conditions):
    """Profile edits. Fields left out are unchanged; conditions can be added or removed later."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    age: int | None = Field(default=None, ge=0, le=120)
    sex: Sex | None = None
    doctor_ids: list[str] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def at_least_one(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("Provide at least one field to update.")
        return self


class LabsIn(BaseModel):
    """One set of lab results: WBC in 10^9/L, neutrophils and lymphocytes in %, CRP in mg/L."""
    model_config = ConfigDict(extra="forbid")

    wbc: float
    neutrophils: float
    lymphocytes: float
    crp: float
    taken_at: datetime | None = None          # defaults to now


class AssessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Optional so a missing answer comes back in "missing" rather than as a 422.
    respiratory_distress: Binary | None = None
    hypoxemia: Binary | None = None
    cough: Binary | None = None
    fever: Binary | None = None
    weakness: Binary | None = None


class DemoLabsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wbc: float
    neutrophils: float
    lymphocytes: float
    crp: float


class DemoRunIn(BaseModel):
    """A made-up patient for the Demo Test page: run the models on it, store nothing.

    Readings are spread evenly over the last 24 hours, so they count for Stage 1 and Stage 2."""
    model_config = ConfigDict(extra="forbid")

    readings: dict[Vital, list[float]] = Field(description="Values per vital, oldest first.")
    age: int = Field(ge=0, le=120)
    sex: Sex
    copd: Binary = 0
    heart_failure: Binary = 0
    renal: Binary = 0
    asthma: Binary = 0
    diabetes: Binary = 0
    hypertension: Binary = 0
    respiratory_distress: Binary | None = None
    hypoxemia: Binary | None = None
    cough: Binary | None = None
    fever: Binary | None = None
    weakness: Binary | None = None
    labs: DemoLabsIn | None = None

    @model_validator(mode="after")
    def reading_counts(self):
        if any(len(v) > 50 for v in self.readings.values()):
            raise ValueError("At most 50 readings per vital.")
        return self
