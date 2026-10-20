"""Patient, reading and assessment storage.

Firestore layout:
    patients/{patient_id}                      profile: display_name, age, sex,
                                               copd, heart_failure, renal (null = not answered),
                                               doctor_ids, created_at
    patients/{patient_id}/readings/{hour}      one document per patient per UTC hour,
                                               e.g. "2026-10-17T14": {hour_start, readings: [...]}
    patients/{patient_id}/assessments/{id}     every model run
    patients/{patient_id}/labs/{id}            uploaded lab results: wbc, neutrophils, lymphocytes,
                                               crp, taken_at
    users/{uid}                                role ("patient" | "doctor"), email, display_name
                                               (logins themselves are Firebase Authentication)

Readings are grouped by hour so a device sending every minute costs one
document write per hour, not one per reading. The repository still hands the
rest of the app a flat list of readings, so nothing else depends on the layout.

FirestoreRepository is the real backend. MemoryRepository has the same
interface for tests and for running without Firebase credentials. Both pass
every write through ensure_plain(), so numpy types never reach Firestore.
"""

import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from api.features import CONDITIONS

_PLAIN = (type(None), bool, int, float, str)
PROFILE_FIELDS = ("display_name", "age", "sex", "doctor_ids", *CONDITIONS)


def ensure_plain(obj, path: str = "doc"):
    """Raise TypeError unless obj is built only from plain Python types.

    Uses exact type checks: numpy.float64 subclasses float and would slip
    through an isinstance check.
    """
    if type(obj) in _PLAIN or isinstance(obj, datetime):
        return obj
    if type(obj) is dict:
        for k, v in obj.items():
            if type(k) is not str:
                raise TypeError(f"{path}: non-string key {k!r}")
            ensure_plain(v, f"{path}.{k}")
        return obj
    if type(obj) is list:
        for i, v in enumerate(obj):
            ensure_plain(v, f"{path}[{i}]")
        return obj
    raise TypeError(f"{path}: {type(obj).__module__}.{type(obj).__name__} is not a plain type")


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:20]


def hour_start(dt: datetime) -> datetime:
    return _utc(dt).replace(minute=0, second=0, microsecond=0)


def hour_key(dt: datetime) -> str:
    """Document id of the hourly bucket a reading belongs to, e.g. "2026-10-17T14"."""
    return hour_start(dt).strftime("%Y-%m-%dT%H")


def group_by_hour(readings: list[dict]) -> dict[str, list[dict]]:
    """Readings (each given a reading_id) grouped by hourly bucket."""
    buckets: dict[str, list[dict]] = {}
    for r in readings:
        entry = ensure_plain({"reading_id": _new_id(), **r, "taken_at": _utc(r["taken_at"])})
        buckets.setdefault(hour_key(entry["taken_at"]), []).append(entry)
    return buckets


def _profile_doc(display_name: str, flags: dict, created_at: datetime, age=None, sex=None,
                 doctor_ids=None) -> dict:
    return ensure_plain({"display_name": display_name, "age": age, "sex": sex,
                         "doctor_ids": list(doctor_ids or []),
                         **{k: flags.get(k) for k in CONDITIONS},
                         "created_at": _utc(created_at)})


class MemoryRepository:
    backend = "memory"

    def __init__(self):
        self._patients: dict[str, dict] = {}
        self._readings: dict[str, dict[str, list[dict]]] = {}   # patient -> hour -> readings
        self._assessments: dict[str, list[dict]] = {}
        self._labs: dict[str, list[dict]] = {}
        self._users: dict[str, dict] = {}

    def ping(self) -> bool:
        return True

    def get_user(self, uid: str) -> dict | None:
        u = self._users.get(uid)
        return deepcopy(u) if u is not None else None

    def set_user(self, uid: str, doc: dict):
        self._users[uid] = deepcopy(ensure_plain(dict(doc)))

    def find_user_by_email(self, email: str) -> tuple[str, dict] | None:
        for uid, u in self._users.items():
            if u.get("email", "").lower() == email.lower():
                return uid, deepcopy(u)
        return None

    def list_patients(self, doctor_id: str | None = None) -> list[dict]:
        return [{"patient_id": pid, **deepcopy(p)} for pid, p in sorted(self._patients.items())
                if doctor_id is None or doctor_id in p.get("doctor_ids", [])]

    def get_patient(self, patient_id: str) -> dict | None:
        p = self._patients.get(patient_id)
        return deepcopy(p) if p is not None else None

    def create_patient(self, patient_id: str, display_name: str, flags: dict, created_at: datetime,
                       age=None, sex=None, doctor_ids=None):
        self._patients[patient_id] = deepcopy(
            _profile_doc(display_name, flags, created_at, age, sex, doctor_ids))
        self._readings[patient_id] = {}
        self._assessments[patient_id] = []
        self._labs[patient_id] = []

    def delete_patient(self, patient_id: str):
        for store in (self._patients, self._readings, self._assessments, self._labs):
            store.pop(patient_id, None)

    def add_labs(self, patient_id: str, labs: dict) -> str:
        doc = ensure_plain({**labs, "taken_at": _utc(labs["taken_at"])})
        lid = _new_id()
        self._labs.setdefault(patient_id, []).append({"lab_id": lid, **deepcopy(doc)})
        return lid

    def latest_labs(self, patient_id: str, since: datetime) -> dict | None:
        rows = [r for r in self._labs.get(patient_id, []) if r["taken_at"] >= _utc(since)]
        return deepcopy(max(rows, key=lambda r: r["taken_at"])) if rows else None

    def update_patient(self, patient_id: str, fields: dict):
        self._patients[patient_id].update(deepcopy(ensure_plain(dict(fields))))

    def add_readings(self, patient_id: str, readings: list[dict]) -> list[str]:
        ids = []
        for key, entries in group_by_hour(readings).items():
            self._readings[patient_id].setdefault(key, []).extend(deepcopy(entries))
            ids += [e["reading_id"] for e in entries]
        return ids

    def get_readings(self, patient_id: str, since: datetime) -> list[dict]:
        since = _utc(since)
        first = hour_key(since)
        rows = [deepcopy(r) for key, entries in self._readings.get(patient_id, {}).items()
                if key >= first for r in entries if r["taken_at"] >= since]
        return sorted(rows, key=lambda r: r["taken_at"])

    def add_assessment(self, patient_id: str, record: dict) -> str:
        doc = ensure_plain({**record, "created_at": _utc(record["created_at"])})
        aid = _new_id()
        self._assessments[patient_id].append({"assessment_id": aid, **deepcopy(doc)})
        return aid

    def list_assessments(self, patient_id: str, limit: int = 30) -> list[dict]:
        rows = sorted(self._assessments.get(patient_id, []), key=lambda a: a["created_at"], reverse=True)
        return [deepcopy(a) for a in rows[:limit]]


def firebase_certificate(credentials_path: str | None = None):
    """Service-account credentials: FIREBASE_CREDENTIALS_JSON (the file's contents, for hosts
    without secret files, e.g. Vercel), else the file at credentials_path, else None (ADC)."""
    from firebase_admin import credentials

    raw = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if raw:
        return credentials.Certificate(json.loads(raw))
    return credentials.Certificate(credentials_path) if credentials_path else None


class FirestoreRepository:
    backend = "firestore"

    def __init__(self, credentials_path: str | None = None, project_id: str | None = None):
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = firebase_certificate(credentials_path)
            options = {"projectId": project_id} if project_id else None
            firebase_admin.initialize_app(cred, options)
        self._db = firestore.client()

    def _patient(self, patient_id: str):
        return self._db.collection("patients").document(patient_id)

    def ping(self) -> bool:
        try:
            next(iter(self._db.collection("patients").limit(1).stream()), None)
            return True
        except Exception:
            return False

    def get_user(self, uid: str) -> dict | None:
        snap = self._db.collection("users").document(uid).get()
        return snap.to_dict() if snap.exists else None

    def set_user(self, uid: str, doc: dict):
        self._db.collection("users").document(uid).set(ensure_plain(dict(doc)))

    def find_user_by_email(self, email: str) -> tuple[str, dict] | None:
        from google.cloud.firestore_v1.base_query import FieldFilter

        q = self._db.collection("users").where(filter=FieldFilter("email", "==", email.lower())).limit(1)
        docs = list(q.stream())
        return (docs[0].id, docs[0].to_dict()) if docs else None

    def list_patients(self, doctor_id: str | None = None) -> list[dict]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        q = self._db.collection("patients")
        if doctor_id is not None:
            q = q.where(filter=FieldFilter("doctor_ids", "array_contains", doctor_id))
        return [{"patient_id": d.id, **d.to_dict()} for d in q.stream()]

    def get_patient(self, patient_id: str) -> dict | None:
        snap = self._patient(patient_id).get()
        return snap.to_dict() if snap.exists else None

    def create_patient(self, patient_id: str, display_name: str, flags: dict, created_at: datetime,
                       age=None, sex=None, doctor_ids=None):
        self._patient(patient_id).set(_profile_doc(display_name, flags, created_at, age, sex, doctor_ids))

    def delete_patient(self, patient_id: str):
        ref = self._patient(patient_id)
        for sub in ("readings", "assessments", "labs"):
            for d in ref.collection(sub).stream():
                d.reference.delete()
        ref.delete()

    def add_labs(self, patient_id: str, labs: dict) -> str:
        ref = self._patient(patient_id).collection("labs").document()
        ref.set(ensure_plain({**labs, "taken_at": _utc(labs["taken_at"])}))
        return ref.id

    def latest_labs(self, patient_id: str, since: datetime) -> dict | None:
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        q = (self._patient(patient_id).collection("labs")
             .where(filter=FieldFilter("taken_at", ">=", _utc(since)))
             .order_by("taken_at", direction=firestore.Query.DESCENDING).limit(1))
        docs = list(q.stream())
        return {"lab_id": docs[0].id, **docs[0].to_dict()} if docs else None

    def update_patient(self, patient_id: str, fields: dict):
        self._patient(patient_id).update(ensure_plain(dict(fields)))

    def add_readings(self, patient_id: str, readings: list[dict]) -> list[str]:
        from google.cloud import firestore

        col = self._patient(patient_id).collection("readings")
        buckets = list(group_by_hour(readings).items())
        ids = []
        # One write per hourly bucket; a Firestore batch holds at most 500 writes.
        for start in range(0, len(buckets), 400):
            batch = self._db.batch()
            for key, entries in buckets[start:start + 400]:
                batch.set(col.document(key),
                          {"hour_start": entries[0]["taken_at"].replace(minute=0, second=0, microsecond=0),
                           "readings": firestore.ArrayUnion(entries)},
                          merge=True)
                ids += [e["reading_id"] for e in entries]
            batch.commit()
        return ids

    def get_readings(self, patient_id: str, since: datetime) -> list[dict]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        since = _utc(since)
        q = (self._patient(patient_id).collection("readings")
             .where(filter=FieldFilter("hour_start", ">=", hour_start(since))))
        rows = [r for d in q.stream() for r in d.to_dict().get("readings", []) if r["taken_at"] >= since]
        return sorted(rows, key=lambda r: r["taken_at"])

    def add_assessment(self, patient_id: str, record: dict) -> str:
        ref = self._patient(patient_id).collection("assessments").document()
        ref.set(ensure_plain({**record, "created_at": _utc(record["created_at"])}))
        return ref.id

    def list_assessments(self, patient_id: str, limit: int = 30) -> list[dict]:
        from google.cloud import firestore

        q = (self._patient(patient_id).collection("assessments")
             .order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit))
        return [{"assessment_id": d.id, **d.to_dict()} for d in q.stream()]


def repository_from_env():
    backend = os.getenv("DB_BACKEND", "firestore").lower()
    if backend == "memory":
        return MemoryRepository()
    if backend == "firestore":
        return FirestoreRepository(os.getenv("FIREBASE_CREDENTIALS") or None,
                                   os.getenv("FIREBASE_PROJECT_ID") or None)
    raise ValueError(f"Unknown DB_BACKEND '{backend}' (expected 'firestore' or 'memory')")
