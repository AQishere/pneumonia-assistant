"""Who is calling, and what may they see.

Two kinds of caller:
  - service: sends X-API-Key (IoT ingestion, seed script, tests). Full access.
  - user: sends "Authorization: Bearer <Firebase ID token>" from the web app.
      patient -> only their own record (patient_id == their uid)
      doctor  -> only patients who linked them (uid in the patient's doctor_ids)
The API key is never given to browsers; users only ever hold their own Firebase token.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Caller:
    kind: str                    # "service" | "user"
    uid: str | None = None
    email: str | None = None
    role: str | None = None      # "patient" | "doctor" | None (signed in, no account yet)


SERVICE = Caller(kind="service")


def firebase_verifier():
    """Verify Firebase ID tokens with Google's public keys (no API key needed in the browser)."""
    import firebase_admin
    from firebase_admin import auth, credentials

    if not firebase_admin._apps:
        path = os.getenv("FIREBASE_CREDENTIALS") or None
        options = {"projectId": os.getenv("FIREBASE_PROJECT_ID")} if os.getenv("FIREBASE_PROJECT_ID") else None
        firebase_admin.initialize_app(credentials.Certificate(path) if path else None, options)

    def verify(token: str) -> dict:
        decoded = auth.verify_id_token(token)
        return {"uid": decoded["uid"], "email": (decoded.get("email") or "").lower() or None}

    return verify


def can_access(caller: Caller, patient_id: str, patient: dict | None) -> bool:
    if caller.kind == "service":
        return True
    if caller.role == "patient":
        return caller.uid == patient_id
    if caller.role == "doctor":
        return patient is not None and caller.uid in (patient.get("doctor_ids") or [])
    return False
