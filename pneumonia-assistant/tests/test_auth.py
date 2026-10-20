"""Sign-in, roles and the chat endpoint (fake token verifier and fake agent: no Firebase, no LLM)."""

import json

import pytest
from fastapi.testclient import TestClient

from agent.tools import ScopedExecutor, ToolExecutor
from api.db import MemoryRepository
from api.main import create_app
from seed_demo_data import seed
from tests.conftest import NOW

KEY = "test-key"
SIGNUP = {"display_name": "Alex", "age": 40, "sex": "male", "copd": 0, "heart_failure": 0, "renal": 0,
          "asthma": 0, "diabetes": 0, "hypertension": 0}


def fake_verify(token: str) -> dict:
    """Tokens look like 'tok-<uid>'; anything else is rejected like an expired token."""
    if not token.startswith("tok-"):
        raise ValueError("bad token")
    uid = token[4:]
    return {"uid": uid, "email": f"{uid}@example.com"}


def fake_agent_factory(tool_client):
    """An 'agent' that assesses the patient through the real internal API, scoped like the real one."""
    class FakeAgent:
        def __init__(self, patient_id, on_tool_call):
            self.executor = ScopedExecutor(ToolExecutor(tool_client()), patient_id)
            self.on_tool_call = on_tool_call

        def send(self, text):
            args = json.dumps({"respiratory_distress": 0})
            result = self.executor.execute("assess_patient", args)
            self.on_tool_call("assess_patient", args, result)
            return f"echo: {text} -> {result.get('band')}"

    return lambda patient_id, on_tool_call: FakeAgent(patient_id, on_tool_call)


@pytest.fixture
def app(predictor):
    repo = MemoryRepository()
    seed(repo, predictor, NOW)
    return create_app(repo=repo, predictor=predictor, api_key=KEY, clock=lambda: NOW,
                      token_verifier=fake_verify, agent_factory=fake_agent_factory)


def user(app, uid):
    return TestClient(app, headers={"Authorization": f"Bearer tok-{uid}"})


def test_invalid_token_is_401(app):
    assert TestClient(app, headers={"Authorization": "Bearer nope"}).get("/me").status_code == 401


def test_patient_signs_up_and_sees_only_their_own_record(app):
    alex = user(app, "alex")
    assert alex.get("/me").json()["role"] is None                       # signed in, no profile yet
    assert alex.post("/patients", json={**SIGNUP, "patient_id": "someone-else"}).status_code == 403
    assert alex.post("/patients", json={**SIGNUP, "patient_id": "alex"}).status_code == 201
    me = alex.get("/me").json()
    assert me["role"] == "patient" and me["profile"]["display_name"] == "Alex"
    assert [p["patient_id"] for p in alex.get("/patients").json()["patients"]] == ["alex"]
    assert alex.get("/patients/alex").status_code == 200
    assert alex.get("/patients/demo-sick").status_code == 403
    assert alex.post("/patients/demo-sick/assess", json={"respiratory_distress": 1}).status_code == 403


def test_users_cannot_mark_readings_as_device_readings(app):
    alex = user(app, "alex")
    alex.post("/patients", json={**SIGNUP, "patient_id": "alex"})
    alex.post("/patients/alex/readings", json={"readings": [{"vital": "spo2", "value": 97, "entered_by": "device"}]})
    readings = alex.get("/patients/alex/readings").json()["readings"]
    assert [r["entered_by"] for r in readings] == ["patient"]


def test_doctor_sees_only_linked_patients(app):
    alex, dr = user(app, "alex"), user(app, "dr-lee")
    alex.post("/patients", json={**SIGNUP, "patient_id": "alex"})
    assert dr.post("/doctors", json={"display_name": "Dr Lee"}).status_code == 201
    assert dr.get("/patients").json()["patients"] == []
    assert dr.get("/patients/alex").status_code == 403

    linked = alex.post("/patients/alex/doctors", json={"email": "DR-LEE@example.com"})
    assert linked.status_code == 200 and linked.json()["doctor_ids"] == ["dr-lee"]
    assert [p["patient_id"] for p in dr.get("/patients").json()["patients"]] == ["alex"]
    assert dr.get("/patients/alex").status_code == 200
    assert dr.get("/patients/demo-sick").status_code == 403
    assert dr.post("/patients/alex/doctors", json={"email": "x@example.com"}).status_code == 403

    assert alex.delete("/patients/alex/doctors/dr-lee").json()["doctor_ids"] == []
    assert dr.get("/patients/alex").status_code == 403


def test_linking_requires_a_doctor_account(app):
    alex = user(app, "alex")
    alex.post("/patients", json={**SIGNUP, "patient_id": "alex"})
    user(app, "bob").post("/patients", json={**SIGNUP, "patient_id": "bob"})
    assert alex.post("/patients/alex/doctors", json={"email": "bob@example.com"}).status_code == 404


def test_patients_cannot_set_doctor_ids_directly(app):
    alex = user(app, "alex")
    assert alex.post("/patients", json={**SIGNUP, "patient_id": "alex", "doctor_ids": ["x"]}).status_code == 400
    alex.post("/patients", json={**SIGNUP, "patient_id": "alex"})
    assert alex.patch("/patients/alex", json={"doctor_ids": ["x"]}).status_code == 400


def test_chat_runs_the_agent_on_the_signed_in_patient_only(app):
    alex = user(app, "alex")
    alex.post("/patients", json={**SIGNUP, "patient_id": "alex"})
    r = alex.post("/chat", json={"message": "How am I?", "patient_id": "demo-sick"}).json()
    # The patient_id in the request is ignored for patients: the agent only sees their own record.
    assert r["reply"].startswith("echo: How am I?")
    assert r["latest_result"]["patient_id"] == "alex"
    again = alex.post("/chat", json={"message": "and now?", "conversation_id": r["conversation_id"]}).json()
    assert again["conversation_id"] == r["conversation_id"]


def test_chat_needs_a_profile_and_access(app):
    assert user(app, "nobody").post("/chat", json={"message": "hi"}).status_code == 403
    dr = user(app, "dr-lee")
    dr.post("/doctors", json={"display_name": "Dr Lee"})
    assert dr.post("/chat", json={"message": "hi"}).status_code == 400
    assert dr.post("/chat", json={"message": "hi", "patient_id": "demo-sick"}).status_code == 403


def test_service_key_still_works(app):
    svc = TestClient(app, headers={"X-API-Key": KEY})
    assert len(svc.get("/patients").json()["patients"]) >= 9
