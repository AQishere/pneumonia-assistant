"""FastAPI server: validation, safety alerts, features, Stage 1 / Stage 2, storage, chat.

Run with:
    uvicorn api.main:create_app --factory --port 8000

Callers authenticate with either X-API-Key (devices, scripts) or a Firebase ID
token (web app users); see api/auth.py for who may see what.
"""

import os
import secrets
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from api import features_v2, safety, templates, validation
from api.assessment import STAGE1_WINDOW, STAGE2_WINDOW, assess, display_score, group_readings
from api.auth import SERVICE, Caller, can_access, firebase_verifier
from api.chat_service import Conversations
from api.db import repository_from_env
from api.features import (CONDITIONS, LAB_FIELDS, VITAL_NAMES, build_features, counts, missing_stage1,
                          missing_stage2_v2)
from api.predictor import LazyPredictor, Predictor
from api.schemas import AssessIn, DemoRunIn, FlagsIn, LabsIn, PatientIn, PatientPatch, ReadingsIn


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class DoctorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=100)


class LinkDoctorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    patient_id: str | None = None          # patients: always their own; doctors/services: required
    conversation_id: str | None = None


def default_agent_factory(tool_client):
    """Gemini agent for one patient, using the API in-process with the service key."""
    from agent.chat import Agent, make_client
    from agent.tools import ScopedExecutor, ToolExecutor

    def make(patient_id: str, on_tool_call):
        model = os.getenv("LLM_MODEL")
        if not model:
            raise RuntimeError("LLM_MODEL is not set.")
        executor = ScopedExecutor(ToolExecutor(tool_client()), patient_id)
        agent = Agent(make_client(), model, executor, on_tool_call=on_tool_call,
                      reasoning_effort=os.getenv("LLM_REASONING_EFFORT") or None)
        agent.messages.append({"role": "system", "content":
                               f"The user's patient_id is '{patient_id}'. Use it for every tool call."})
        return agent

    return make


def create_app(repo=None, predictor: Predictor | None = None, api_key: str | None = None,
               clock=_utc_now, token_verifier=None, agent_factory=None) -> FastAPI:
    load_dotenv()
    api_key = api_key or os.getenv("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY is not set. Add it to .env (see .env.example).")
    predictor = predictor or LazyPredictor()
    if repo is None:
        repo = repository_from_env()
        if repo.backend == "memory" and os.getenv("SEED_DEMO", "1") == "1":
            from seed_demo_data import seed
            seed(repo, predictor)
    verifier = {"fn": token_verifier}

    app = FastAPI(title="Pneumonia Risk Assistant API",
                  description="Decision support only. Not a diagnosis.")
    origins = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"],
                       allow_headers=["Authorization", "Content-Type"])

    @app.exception_handler(RequestValidationError)
    async def bad_request(_: Request, exc: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"),
                   "code": "INVALID_REQUEST", "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": True, "errors": errors})

    # --- Who is calling --------------------------------------------------------------------
    def get_caller(x_api_key: str | None = Header(default=None),
                   authorization: str | None = Header(default=None)) -> Caller:
        if x_api_key and secrets.compare_digest(x_api_key, api_key):
            return SERVICE
        if authorization and authorization.lower().startswith("bearer "):
            if verifier["fn"] is None:
                verifier["fn"] = firebase_verifier()
            try:
                claims = verifier["fn"](authorization[7:].strip())
            except Exception:
                raise HTTPException(status_code=401, detail="Invalid or expired sign-in. Please sign in again.")
            user = repo.get_user(claims["uid"]) or {}
            return Caller(kind="user", uid=claims["uid"], email=claims.get("email"), role=user.get("role"))
        raise HTTPException(status_code=401, detail="Sign in required (Firebase token or X-API-Key).")

    def patient_for(caller: Caller, patient_id: str) -> dict:
        patient = repo.get_patient(patient_id)
        if not can_access(caller, patient_id, patient):
            raise HTTPException(status_code=403, detail="You don't have access to this patient.")
        if patient is None:
            raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
        return patient

    def profile(patient_id: str, patient: dict) -> dict:
        return {"patient_id": patient_id,
                **{k: patient.get(k) for k in ("display_name", "age", "sex", "doctor_ids")},
                "history_flags": {k: patient.get(k) for k in CONDITIONS},
                "created_at": patient.get("created_at")}

    router = APIRouter(dependencies=[Depends(get_caller)])

    @app.get("/ping")
    def ping():
        """Cheap wake-up call: no database, no models."""
        return {"status": "ok"}

    @app.get("/health")
    def health():
        return {"status": "ok",
                "model_version": predictor.model_version,
                "thresholds": {"stage1": predictor.threshold_stage1, "stage2": predictor.threshold_stage2},
                "database": {"backend": repo.backend, "reachable": repo.ping()}}

    # --- Accounts --------------------------------------------------------------------------
    @router.get("/me")
    def me(caller: Caller = Depends(get_caller)):
        if caller.kind == "service":
            return {"kind": "service"}
        patient = repo.get_patient(caller.uid) if caller.role == "patient" else None
        return {"kind": "user", "uid": caller.uid, "email": caller.email, "role": caller.role,
                "profile": profile(caller.uid, patient) if patient else None}

    @router.post("/doctors", status_code=201)
    def register_doctor(body: DoctorIn, caller: Caller = Depends(get_caller)):
        if caller.kind != "user":
            raise HTTPException(status_code=400, detail="Doctors register with their own sign-in.")
        if caller.role == "patient":
            raise HTTPException(status_code=409, detail="This account is already a patient account.")
        repo.set_user(caller.uid, {"role": "doctor", "email": caller.email, "display_name": body.display_name})
        return {"uid": caller.uid, "role": "doctor", "display_name": body.display_name}

    @router.get("/patients")
    def list_patients(caller: Caller = Depends(get_caller)):
        if caller.kind == "service":
            rows = repo.list_patients()
        elif caller.role == "doctor":
            rows = repo.list_patients(doctor_id=caller.uid)
        elif caller.role == "patient":
            p = repo.get_patient(caller.uid)
            rows = [{"patient_id": caller.uid, **p}] if p else []
        else:
            rows = []
        return {"patients": [{"patient_id": p["patient_id"], "display_name": p["display_name"]} for p in rows]}

    @router.post("/patients", status_code=201)
    def create_patient(body: PatientIn, caller: Caller = Depends(get_caller)):
        if caller.kind == "user":
            if body.patient_id != caller.uid:
                raise HTTPException(status_code=403, detail="patient_id must be your own account id.")
            if caller.role == "doctor":
                raise HTTPException(status_code=409, detail="This account is a doctor account.")
            if body.doctor_ids:
                raise HTTPException(status_code=400, detail="Link doctors by email after signing up.")
        if repo.get_patient(body.patient_id) is not None:
            raise HTTPException(status_code=409, detail=f"Patient '{body.patient_id}' already exists.")
        repo.create_patient(body.patient_id, body.display_name,
                            {k: getattr(body, k) for k in CONDITIONS}, clock(),
                            age=body.age, sex=body.sex, doctor_ids=body.doctor_ids)
        if caller.kind == "user":
            repo.set_user(caller.uid, {"role": "patient", "email": caller.email,
                                       "display_name": body.display_name})
        return profile(body.patient_id, repo.get_patient(body.patient_id))

    @router.patch("/patients/{patient_id}")
    def update_profile(patient_id: str, body: PatientPatch, caller: Caller = Depends(get_caller)):
        patient_for(caller, patient_id)
        changes = body.model_dump(exclude_none=True)
        if caller.kind == "user" and "doctor_ids" in changes:
            raise HTTPException(status_code=400, detail="Use /patients/{id}/doctors to link or unlink doctors.")
        repo.update_patient(patient_id, changes)
        return profile(patient_id, repo.get_patient(patient_id))

    @router.post("/patients/{patient_id}/doctors")
    def link_doctor(patient_id: str, body: LinkDoctorIn, caller: Caller = Depends(get_caller)):
        patient = patient_for(caller, patient_id)
        if caller.role == "doctor":
            raise HTTPException(status_code=403, detail="Only the patient can link a doctor.")
        found = repo.find_user_by_email(body.email.strip().lower())
        if found is None or found[1].get("role") != "doctor":
            raise HTTPException(status_code=404, detail="No doctor account with that email.")
        ids = list(dict.fromkeys([*(patient.get("doctor_ids") or []), found[0]]))
        repo.update_patient(patient_id, {"doctor_ids": ids})
        return {"patient_id": patient_id, "doctor_ids": ids,
                "linked": {"uid": found[0], "display_name": found[1].get("display_name")}}

    @router.delete("/patients/{patient_id}/doctors/{doctor_uid}")
    def unlink_doctor(patient_id: str, doctor_uid: str, caller: Caller = Depends(get_caller)):
        patient = patient_for(caller, patient_id)
        if caller.role == "doctor" and caller.uid != doctor_uid:
            raise HTTPException(status_code=403, detail="Doctors can only unlink themselves.")
        ids = [d for d in (patient.get("doctor_ids") or []) if d != doctor_uid]
        repo.update_patient(patient_id, {"doctor_ids": ids})
        return {"patient_id": patient_id, "doctor_ids": ids}

    # --- Patient data ------------------------------------------------------------------------
    @router.get("/patients/{patient_id}")
    def get_patient(patient_id: str, caller: Caller = Depends(get_caller)):
        patient = patient_for(caller, patient_id)
        now = clock()
        readings = repo.get_readings(patient_id, now - STAGE2_WINDOW)
        history = {k: patient.get(k) for k in CONDITIONS}
        r24 = group_readings(readings, now - STAGE1_WINDOW, now)
        # Critical values surface on the first lookup, even if no assessment is run.
        alerts = safety.alerts(r24)
        missing = [m["item"] for m in missing_stage1(r24, 0)]   # vitals only; breathing is asked separately
        if missing:
            next_step = ("Stage 1 cannot run yet: the device sent no reading in the last 24 h for: "
                         + ", ".join(VITAL_NAMES[v] for v in missing) + ". Tell the user, suggest checking "
                         "that the device is worn and charged, and offer to record a reading they take "
                         "themselves. Do not assess yet.")
        else:
            next_step = ("All device readings are on record; do not ask for vital signs. If the user has "
                         "not said, ask whether they are short of breath and whether they have a cough, "
                         "feel feverish, or feel unusually weak or tired; then call assess_patient.")
        labs = repo.latest_labs(patient_id, now - STAGE2_WINDOW)
        latest = [{"vital": r["vital"], "value": r["value"], "taken_at": r["taken_at"]}
                  for r in sorted(readings, key=lambda r: r["taken_at"])]
        latest_by_vital = {r["vital"]: r for r in latest}
        return {
            "patient_id": patient_id,
            "display_name": patient["display_name"],
            "age": patient.get("age"),
            "sex": patient.get("sex"),
            "alerts": alerts,
            "critical_notice": templates.CRITICAL_NOTICE if alerts else None,
            "lead_text": templates.lead_text(alerts),
            "stage1_ready": not missing,
            "missing_for_stage1": missing,
            "next_step": next_step,
            "history_flags": history,
            "history_flags_not_on_record": [k for k, v in history.items() if v is None],
            "labs": ({k: labs.get(k) for k in (*LAB_FIELDS, "taken_at")} if labs else None),
            "latest_readings": latest_by_vital,
            "reading_counts": {
                "24h": counts(r24),
                "7d": counts(group_readings(readings, now - STAGE2_WINDOW, now)),
            },
        }

    @router.post("/patients/{patient_id}/readings")
    def add_readings(patient_id: str, body: ReadingsIn, caller: Caller = Depends(get_caller)):
        patient_for(caller, patient_id)
        now = clock()
        errors, docs = [], []
        for i, r in enumerate(body.readings):
            taken_at = _as_utc(r.taken_at) if r.taken_at else now
            for err in (validation.check_reading(r.vital, r.value, r.unit),
                        validation.check_taken_at(taken_at, now)):
                if err:
                    errors.append({"index": i, **err})
            # Only services (the device pipeline) may mark readings as device readings.
            entered_by = r.entered_by if caller.kind == "service" else (caller.role or "patient")
            docs.append({"vital": r.vital, "value": float(r.value), "taken_at": taken_at,
                         "entered_by": entered_by})
        if errors:
            # All or nothing: one bad value means nothing is stored.
            return JSONResponse(status_code=422, content={"error": True, "stored": 0, "errors": errors})
        ids = repo.add_readings(patient_id, docs)
        return {"stored": len(ids),
                "readings": [{"reading_id": rid, "vital": d["vital"], "value": d["value"],
                              "taken_at": d["taken_at"]} for rid, d in zip(ids, docs)]}

    @router.put("/patients/{patient_id}/flags")
    def update_flags(patient_id: str, body: FlagsIn, caller: Caller = Depends(get_caller)):
        patient_for(caller, patient_id)
        repo.update_patient(patient_id, body.model_dump(exclude_none=True))
        patient = repo.get_patient(patient_id)
        return {"patient_id": patient_id, "history_flags": {k: patient.get(k) for k in CONDITIONS}}

    @router.post("/patients/{patient_id}/labs", status_code=201)
    def add_labs(patient_id: str, body: LabsIn, caller: Caller = Depends(get_caller)):
        patient_for(caller, patient_id)
        now = clock()
        labs = body.model_dump(exclude={"taken_at"})
        taken_at = _as_utc(body.taken_at) if body.taken_at else now
        errors = validation.check_labs(labs)
        if err := validation.check_taken_at(taken_at, now):
            errors.append(err)
        if errors:
            return JSONResponse(status_code=422, content={"error": True, "stored": 0, "errors": errors})
        lab_id = repo.add_labs(patient_id, {**labs, "taken_at": taken_at, "entered_by": caller.role or "service"})
        return {"lab_id": lab_id, **labs, "taken_at": taken_at}

    @router.post("/patients/{patient_id}/assess")
    def assess_patient(patient_id: str, body: AssessIn, caller: Caller = Depends(get_caller)):
        patient = patient_for(caller, patient_id)
        now = clock()
        readings = repo.get_readings(patient_id, now - STAGE2_WINDOW)
        outcome = assess(readings, patient, body.respiratory_distress, body.hypoxemia, predictor, now,
                         previous=repo.list_assessments(patient_id, 10),
                         symptoms={"cough": body.cough, "fever": body.fever, "weakness": body.weakness},
                         labs=repo.latest_labs(patient_id, now - STAGE2_WINDOW))
        response = {"patient_id": patient_id, **outcome.response, "assessment_id": None}
        if outcome.record:
            response["assessment_id"] = repo.add_assessment(patient_id, outcome.record)
        return response

    @router.post("/demo/run")
    def demo_run(body: DemoRunIn):
        """Run alerts, Stage 1 and Stage 2 on manually entered data. Nothing is stored and no LLM is called."""
        now = clock()
        errors, readings = [], []
        for vital, values in body.readings.items():
            for i, value in enumerate(values):
                if err := validation.check_reading(vital, value):
                    errors.append({"index": i, **err})
                # Spread evenly over the last 24 h, oldest first, so both model windows include them.
                taken_at = now - STAGE1_WINDOW * (len(values) - i) / (len(values) + 1)
                readings.append({"vital": vital, "value": float(value), "taken_at": taken_at})
        labs = body.labs.model_dump() if body.labs else None
        if labs:
            errors += validation.check_labs(labs)
        if errors:
            return JSONResponse(status_code=422, content={"error": True, "errors": errors})
        patient = body.model_dump(include={"age", "sex", *CONDITIONS})
        outcome = assess(readings, patient, body.respiratory_distress, body.hypoxemia, predictor, now,
                         symptoms={"cough": body.cough, "fever": body.fever, "weakness": body.weakness},
                         labs={**labs, "taken_at": now} if labs else None)
        record = outcome.record or {}
        p2, f2, shadow = record.get("p_stage2"), record.get("features_stage2"), False
        r7 = group_readings(readings, now - STAGE2_WINDOW, now)
        if (p2 is None and body.respiratory_distress is not None and predictor.stage2_version == "stage2-v2"
                and not missing_stage2_v2(r7, patient, {"weakness": body.weakness}, labs)):
            # Stage 1 cleared the patient, so Stage 2 did not run: score it anyway for the demo bar only.
            # The band and advice above are the real result and are not affected.
            f2 = features_v2.from_app_inputs(build_features(r7, {}), patient, {"weakness": body.weakness}, labs,
                                             body.respiratory_distress, safety.derive_hypoxemia(r7, body.hypoxemia))
            p2, shadow = predictor._score(predictor.stage2, f2), True
            f2 = {k: f2[k] for k in predictor.stage2["features"]}
        amber =[round(predictor.threshold_stage2 - 0.10, 2), round(predictor.threshold_stage2 + 0.10, 2)]
        return {**outcome.response,
                "demo": {"p_stage1": record.get("p_stage1"), "p_stage2": p2,
                         "stage2_shadow": shadow,   # True: Stage 2 scored for display only, not used in the band
                         # Stage 2 risk score as a percentage for the demo bar (a score, not a calibrated
                         # probability), and its zone: green below the amber zone, amber up to and including
                         # its top, red above.
                         "pneumonia_percentage": round(p2 * 100, 1) if p2 is not None else None,
                         "risk_zone": (None if p2 is None else "green" if p2 < amber[0]
                                       else "amber" if p2 <= amber[1] else "red"),
                         "threshold_stage1": predictor.threshold_stage1,
                         "threshold_stage2": predictor.threshold_stage2,
                         # Amber zone: Stage 2 scores this close to the threshold are uncertain (a chest
                         # X-ray would decide). Demo page only; the app's bands are unchanged.
                         "amber_zone": amber,
                         "features_stage1": record.get("features_stage1"),
                         "features_stage2": f2}}

    @router.get("/patients/{patient_id}/assessments")
    def list_assessments(patient_id: str, limit: int = Query(30, ge=1, le=100),
                         caller: Caller = Depends(get_caller)):
        patient_for(caller, patient_id)
        rows = repo.list_assessments(patient_id, limit)
        return {"patient_id": patient_id, "assessments": [{
            "assessment_id": a["assessment_id"],
            "created_at": a["created_at"],
            "stage": a["stage"],
            "band": a["band"],
            "risk_score_stage1": display_score(a["p_stage1"], predictor.threshold_stage1),
            "risk_score_stage2": display_score(a["p_stage2"], predictor.threshold_stage2),
            "alerts": a["alerts"],
            "window": a["window"],
            "flags_used": a["flags_used"],
        } for a in rows]}

    @router.get("/patients/{patient_id}/readings")
    def list_readings(patient_id: str, days: int = Query(7, ge=1, le=30),
                      caller: Caller = Depends(get_caller)):
        from datetime import timedelta
        patient_for(caller, patient_id)
        rows = repo.get_readings(patient_id, clock() - timedelta(days=days))
        return {"patient_id": patient_id, "readings": [
            {"vital": r["vital"], "value": r["value"], "taken_at": r["taken_at"],
             "entered_by": r.get("entered_by")} for r in rows]}

    # --- Chat ----------------------------------------------------------------------------
    tool_client = {"c": None}

    def internal_client():
        if tool_client["c"] is None:
            from fastapi.testclient import TestClient
            tool_client["c"] = TestClient(app, base_url="http://internal", headers={"X-API-Key": api_key})
        return tool_client["c"]

    conversations = Conversations((agent_factory or default_agent_factory)(internal_client))

    @router.post("/chat")
    def chat(body: ChatIn, caller: Caller = Depends(get_caller)):
        from agent.chat import AgentError

        if caller.kind == "user" and caller.role is None:
            raise HTTPException(status_code=403, detail="Complete your profile before using the assistant.")
        if caller.role == "patient":
            patient_id = caller.uid
        elif body.patient_id:
            patient_id = body.patient_id
        else:
            raise HTTPException(status_code=400, detail="patient_id is required.")
        patient_for(caller, patient_id)
        try:
            cid, conv = conversations.get_or_create(body.conversation_id, caller.uid, patient_id)
        except Exception as e:      # LLM not configured
            raise HTTPException(status_code=503, detail=f"The assistant is not available: {e}")
        try:
            reply, error = conv.agent.send(body.message), False
        except AgentError as e:
            reply, error = str(e), True
        return {"conversation_id": cid, "reply": reply, "error": error,
                "latest_result": conv.latest_result}

    app.include_router(router)
    return app
