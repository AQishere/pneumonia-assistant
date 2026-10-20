"""Phase 4, offline: tool validation, tool -> API calls, and the agent loop with a fake LLM client.

Live conversations against the LLM are in tests/agent_scenarios.md / run_agent_scenarios.py.
"""

import json
from types import SimpleNamespace

import openai
import httpx
import pytest
from fastapi.testclient import TestClient

from agent.chat import Agent, AgentError
from agent.tools import TOOLS, ScopedExecutor, ToolExecutor
from api import templates
from api.db import MemoryRepository
from api.main import create_app
from seed_demo_data import seed
from tests.conftest import NOW

KEY = "test-key"


@pytest.fixture
def executor(predictor):
    repo = MemoryRepository()
    seed(repo, predictor, NOW)
    app = create_app(repo=repo, predictor=predictor, api_key=KEY, clock=lambda: NOW)
    return ToolExecutor(TestClient(app, headers={"X-API-Key": KEY}))


# --- Tool layer --------------------------------------------------------------

def test_every_tool_schema_has_a_validator():
    from agent.tools import ARG_MODELS
    assert [t["function"]["name"] for t in TOOLS] == list(ARG_MODELS)
    assert all(t["type"] == "function" for t in TOOLS)


def test_get_patient_and_assess(executor):
    assert executor.execute("get_patient", '{"patient_id": "demo-healthy"}')["history_flags"]["heart_failure"] is None
    r = executor.execute("assess_patient", '{"patient_id": "demo-sick", "respiratory_distress": 1, '
                                           '"cough": 1, "fever": 1, "weakness": 1}')
    assert r["band"] == "High"


@pytest.mark.parametrize("name,args,code", [
    ("assess_patient", '{"patient_id": "demo-sick"', "BAD_ARGUMENTS"),                     # broken JSON
    ("assess_patient", '{"patient_id": "demo-sick"}', "BAD_ARGUMENTS"),                    # distress omitted
    ("assess_patient", '{"patient_id": "demo-sick", "respiratory_distress": "maybe"}', "BAD_ARGUMENTS"),
    ("add_readings", '{"patient_id": "demo-sick", "readings": []}', "BAD_ARGUMENTS"),
    ("add_readings", '{"patient_id": "demo-sick", "readings": [{"vital": "glucose", "value": 5}]}', "BAD_ARGUMENTS"),
    ("get_patient", '{"patient_id": "../../etc"}', "BAD_ARGUMENTS"),
    ("get_patient", '{"patient_id": "demo-sick", "extra": 1}', "BAD_ARGUMENTS"),
    ("get_patient", '["demo-sick"]', "BAD_ARGUMENTS"),
    ("update_history_flags", '{"patient_id": "demo-sick"}', "BAD_ARGUMENTS"),
    ("delete_patient", '{"patient_id": "demo-sick"}', "UNKNOWN_TOOL"),
])
def test_malformed_calls_never_reach_the_api(predictor, name, args, code):
    calls = []
    transport = httpx.MockTransport(lambda req: calls.append(req) or httpx.Response(200, json={}))
    ex = ToolExecutor(httpx.Client(transport=transport, base_url="http://api"))
    result = ex.execute(name, args)
    assert result["error"] is True and result["code"] == code
    assert calls == []


def test_missing_distress_hint_tells_agent_to_ask(executor):
    r = executor.execute("assess_patient", '{"patient_id": "demo-sick"}')
    assert "never assume" in r["message"]


def test_validation_errors_come_back_as_tool_errors(executor):
    r = executor.execute("add_readings", json.dumps({"patient_id": "demo-healthy", "readings": [
        {"vital": "temperature", "value": 38.5}]}))
    assert r["error"] is True and r["status"] == 422 and r["stored"] == 0
    assert r["errors"][0]["code"] == "LIKELY_CELSIUS" and r["errors"][0]["suggested_value"] == 101.3


def test_flags_and_not_found(executor):
    r = executor.execute("update_history_flags", '{"patient_id": "demo-borderline", "renal": 0}')
    assert r["history_flags"]["renal"] == 0
    assert executor.execute("get_patient", '{"patient_id": "nobody"}')["code"] == "NOT_FOUND"


def test_scoped_executor_locks_the_agent_to_one_patient(executor):
    scoped = ScopedExecutor(executor, "demo-healthy")
    other = scoped.execute("get_patient", '{"patient_id": "demo-sick"}')
    assert other["code"] == "WRONG_PATIENT"
    own = scoped.execute("get_patient", "{}")            # patient_id filled in automatically
    assert own["patient_id"] == "demo-healthy"


def test_api_unreachable_is_a_plain_error():
    def refuse(req):
        raise httpx.ConnectError("refused", request=req)
    ex = ToolExecutor(httpx.Client(transport=httpx.MockTransport(refuse), base_url="http://api"))
    assert ex.execute("get_patient", '{"patient_id": "demo-sick"}')["code"] == "API_UNREACHABLE"


# --- Agent loop with a scripted fake client ------------------------------------

def tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, type="function",
                           function=SimpleNamespace(name=name, arguments=arguments))


def reply(content=None, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls, role="assistant")
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class FakeClient:
    """Plays back a script of responses (or exceptions) for chat.completions.create."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs["messages"], default=str)))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _status_error(cls, status, message="error"):
    resp = httpx.Response(status, request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
                          headers={"retry-after": "1"})
    return cls(message, response=resp, body=None)


def test_tool_round_trip_and_message_format(executor):
    client = FakeClient([
        reply(tool_calls=[tool_call("c1", "assess_patient",
                                    '{"patient_id": "demo-healthy", "respiratory_distress": 0}')]),
        reply("Low risk (Stage 1). Continue routine monitoring."),
    ])
    agent = Agent(client, "test-model", executor)
    assert agent.send("Assess demo-healthy, no distress").startswith("Low")
    second = client.requests[1]
    assert second[-2]["tool_calls"][0]["function"]["name"] == "assess_patient"
    tool_msg = second[-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
    assert json.loads(tool_msg["content"])["band"] == "Low"


def test_malformed_arguments_are_returned_to_model_then_retried(executor):
    """Scenario 14: Pydantic rejects the call, the API isn't called, the model retries."""
    client = FakeClient([
        reply(tool_calls=[tool_call("c1", "assess_patient", '{"patient_id": "demo-sick", "respiratory_distress": "yes"}')]),
        reply(tool_calls=[tool_call("c2", "assess_patient", '{"patient_id": "demo-sick", "respiratory_distress": 1, '
                                                            '"cough": 1, "fever": 1, "weakness": 1}')]),
        reply("High."),
    ])
    agent = Agent(client, "test-model", executor)
    agent.send("Assess demo-sick, distress yes")
    first_result = json.loads(client.requests[1][-1]["content"])
    second_result = json.loads(client.requests[2][-1]["content"])
    assert first_result["code"] == "BAD_ARGUMENTS"
    assert second_result["band"] == "High"


def test_rate_limit_is_retried_with_a_wait(executor):
    waits = []
    client = FakeClient([_status_error(openai.RateLimitError, 429), _status_error(openai.RateLimitError, 429),
                         reply("Done.")])
    agent = Agent(client, "test-model", executor, sleep=waits.append)
    assert agent.send("hello") == "Done."
    assert waits == [1.0, 1.0]


def test_rate_limit_gives_up_with_plain_message(executor):
    client = FakeClient([_status_error(openai.RateLimitError, 429)] * 5)
    agent = Agent(client, "test-model", executor, sleep=lambda s: None)
    with pytest.raises(AgentError, match="rate limit"):
        agent.send("hello")


def test_overload_503_is_retried(executor):
    waits = []
    client = FakeClient([_status_error(openai.InternalServerError, 503), reply("Done.")])
    assert Agent(client, "test-model", executor, sleep=waits.append).send("hello") == "Done."
    assert waits == [1.0]


def test_gemini_retry_delay_in_body_is_used(executor):
    resp = httpx.Response(429, request=httpx.Request("POST", "https://generativelanguage.googleapis.com"))
    err = openai.RateLimitError("RESOURCE_EXHAUSTED", response=resp,
                                body={"error": {"details": [{"retryDelay": "7s"}]}})
    waits = []
    Agent(FakeClient([err, reply("OK")]), "test-model", executor, sleep=waits.append).send("hello")
    assert waits == [7.0]


def test_daily_quota_fails_fast_with_a_clear_message(executor):
    """The real Gemini free-tier error: 20 requests/day, retry in ~20 h. Don't sleep and retry."""
    resp = httpx.Response(429, request=httpx.Request("POST", "https://generativelanguage.googleapis.com"))
    err = openai.RateLimitError("RESOURCE_EXHAUSTED", response=resp, body=[{"error": {"details": [
        {"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},
        {"retryDelay": "73948s"}]}}])
    waits = []
    with pytest.raises(AgentError, match="daily request limit"):
        Agent(FakeClient([err]), "test-model", executor, sleep=waits.append).send("hello")
    assert waits == []


def test_tool_calls_are_sent_back_with_extra_fields(executor):
    """Gemini thought signatures ride on the tool call; they must survive the round trip."""
    class SignedCall(SimpleNamespace):
        def model_dump(self, exclude_none=True):
            return {"id": self.id, "type": "function",
                    "function": {"name": self.function.name, "arguments": self.function.arguments},
                    "extra_content": {"google": {"thought_signature": "sig-123"}}}

    call = SignedCall(id="c1", type="function", function=SimpleNamespace(
        name="get_patient", arguments='{"patient_id": "demo-healthy"}'))
    client = FakeClient([reply(tool_calls=[call]), reply("Done.")])
    Agent(client, "test-model", executor).send("Look up demo-healthy")
    sent = client.requests[1][-2]["tool_calls"][0]
    assert sent["extra_content"]["google"]["thought_signature"] == "sig-123"


def test_tool_use_failed_is_retried(executor):
    client = FakeClient([_status_error(openai.BadRequestError, 400, "tool_use_failed"), reply("OK")])
    assert Agent(client, "test-model", executor).send("hello") == "OK"


def test_auth_error_is_a_plain_message(executor):
    client = FakeClient([_status_error(openai.AuthenticationError, 401)])
    with pytest.raises(AgentError, match="API key"):
        Agent(client, "test-model", executor).send("hello")


def _spo2_count(executor, pid):
    return executor.execute("get_patient", json.dumps({"patient_id": pid}))["reading_counts"]["24h"]["spo2"]


def test_invented_reading_is_blocked_before_the_api(executor):
    """Replays the gpt-oss-20b failure: it stored an SpO2 of 95 the doctor never gave."""
    before = _spo2_count(executor, "demo-sick")
    client = FakeClient([
        reply(tool_calls=[tool_call("c1", "add_readings",
                                    '{"patient_id": "demo-sick", "readings": [{"vital": "spo2", "value": 95}]}')]),
        reply("OK"),
    ])
    Agent(client, "test-model", executor).send("Assess demo-sick, distress yes")
    result = json.loads(client.requests[1][-1]["content"])
    assert result["code"] == "VALUE_NOT_FROM_DOCTOR"
    assert result["values"] == [{"vital": "spo2", "value": 95}]
    assert _spo2_count(executor, "demo-sick") == before


def test_value_the_doctor_typed_is_stored(executor):
    before = _spo2_count(executor, "demo-sick")
    client = FakeClient([
        reply(tool_calls=[tool_call("c1", "add_readings",
                                    '{"patient_id": "demo-sick", "readings": [{"vital": "spo2", "value": 93, "unit": "%"}]}')]),
        reply("Stored."),
    ])
    Agent(client, "test-model", executor).send("SpO2 is 93% for demo-sick")
    assert json.loads(client.requests[1][-1]["content"])["stored"] == 1
    assert _spo2_count(executor, "demo-sick") == before + 1


def test_suggested_conversion_needs_the_doctors_reply_first(executor):
    add_101 = '{"patient_id": "demo-healthy", "readings": [{"vital": "temperature", "value": 101.3}]}'
    client = FakeClient([
        reply(tool_calls=[tool_call("c1", "add_readings",
                                    '{"patient_id": "demo-healthy", "readings": [{"vital": "temperature", "value": 38.5}]}')]),
        reply(tool_calls=[tool_call("c2", "add_readings", add_101)]),   # converts without asking
        reply("Did you mean 101.3 °F?"),
        reply(tool_calls=[tool_call("c3", "add_readings", add_101)]),   # after the doctor says yes
        reply("Stored 101.3 °F."),
    ])
    agent = Agent(client, "test-model", executor)
    agent.send("Temperature is 38.5 for demo-healthy")
    assert json.loads(client.requests[1][-1]["content"])["errors"][0]["code"] == "LIKELY_CELSIUS"
    assert json.loads(client.requests[2][-1]["content"])["code"] == "VALUE_NOT_FROM_DOCTOR"
    agent.send("yes")
    assert json.loads(client.requests[4][-1]["content"])["stored"] == 1


def test_numbers_inside_words_do_not_count():
    from agent.tools import ReadingProvenance
    p = ReadingProvenance()
    p.note_doctor_message("Check SpO2 and BP 120/80 for demo-sick")
    assert p._known(120) and p._known(80)
    assert not p._known(2)


# --- Alerts first (code-enforced) -----------------------------------------------

ASSESS_LOW_SPO2 = '{"patient_id": "demo-low-spo2", "respiratory_distress": 0}'

# gpt-oss-20b's actual reply in scenario 10: notice first, but the SpO2 alert after the band.
REPLY_ALERT_AFTER_BAND = (f"**Important:** {templates.CRITICAL_NOTICE}\n"
                          "**Result:** Low.\n**What to do:** Keep wearing your device.\n"
                          "*Reading:* blood oxygen (SpO₂) 84% (below 90%).")


def test_alert_after_band_gets_alerts_put_first(executor):
    client = FakeClient([reply(tool_calls=[tool_call("c1", "assess_patient", ASSESS_LOW_SPO2)]),
                         reply(REPLY_ALERT_AFTER_BAND)])
    agent = Agent(client, "test-model", executor)
    out = agent.send("Assess demo-low-spo2, no distress")
    assert out.startswith(f"{templates.CRITICAL_NOTICE} Blood oxygen (SpO2) dropped to 84% (below 90%).")
    assert agent.alerts_prepended == 1


def test_correct_reply_is_left_alone(executor):
    # gpt-oss-20b's scenario 2 style: bold, bullets, SpO₂, spaces before % -- still alerts first.
    good = (f"**Important**: *{templates.CRITICAL_NOTICE}*\n"
            "**Alerts**:\n• *Blood oxygen (SpO₂) dropped to 84 % (below 90 %)*\n\n**Result**: Low")
    client = FakeClient([reply(tool_calls=[tool_call("c1", "assess_patient", ASSESS_LOW_SPO2)]),
                         reply(good)])
    agent = Agent(client, "test-model", executor)
    assert agent.send("Assess demo-low-spo2, no distress") == good
    assert agent.alerts_prepended == 0


def test_no_alerts_means_no_prepending(executor):
    client = FakeClient([
        reply(tool_calls=[tool_call("c1", "assess_patient", '{"patient_id": "demo-healthy", "respiratory_distress": 0}')]),
        reply("Band: Low (Stage 1)."),
    ])
    assert Agent(client, "test-model", executor).send("Assess demo-healthy, no distress") == "Band: Low (Stage 1)."


# --- Readings the model skipped ---------------------------------------------------

def test_find_stated_readings():
    from agent.guards import find_stated_readings
    assert find_stated_readings("For demo-healthy: temperature is 10") == [("temperature", 10.0)]
    assert find_stated_readings("temp was 38.5, RR 32, yes distress") == [("temperature", 38.5),
                                                                          ("respiratory_rate", 32.0)]
    assert find_stated_readings("BP 120/80 and SpO₂ 93%") == [("spo2", 93.0), ("sbp", 120.0)]
    assert find_stated_readings("Yes, I meant 101.3 °F") == [("temperature", 101.3)]
    assert find_stated_readings("So there's a 95% chance of pneumonia?") == []
    assert find_stated_readings("Assess demo-sick, distress yes") == []


def test_skipped_reading_gets_one_nudge_then_is_sent(executor):
    """Replays scenario 3: the model ignored "temperature is 10" and asked about distress."""
    add_10 = '{"patient_id": "demo-healthy", "readings": [{"vital": "temperature", "value": 10}]}'
    client = FakeClient([
        reply("Is the patient in respiratory distress?"),                       # ignores the 10
        reply(tool_calls=[tool_call("c1", "add_readings", add_10)]),            # after the nudge
        reply("Temperature 10 is outside the accepted range. Please confirm or correct it."),
    ])
    agent = Agent(client, "test-model", executor)
    out = agent.send("For demo-healthy: temperature is 10")
    assert "confirm" in out and agent.nudges == 1
    nudge = client.requests[1][-1]
    assert nudge["role"] == "user" and "temperature 10" in nudge["content"]
    assert all(m.get("content") != "Is the patient in respiratory distress?" for m in client.requests[2])
    assert json.loads(client.requests[2][-1]["content"])["errors"][0]["code"] == "OUT_OF_RANGE"


def test_nudge_happens_at_most_once(executor):
    client = FakeClient([reply("Distress?"), reply("Distress, yes or no?")])
    agent = Agent(client, "test-model", executor)
    assert agent.send("temperature is 10 for demo-healthy") == "Distress, yes or no?"
    assert agent.nudges == 1


def test_no_nudge_when_reading_was_sent(executor):
    client = FakeClient([
        reply(tool_calls=[tool_call("c1", "add_readings",
                                    '{"patient_id": "demo-healthy", "readings": [{"vital": "temperature", "value": 10}]}')]),
        reply("Please confirm the temperature."),
    ])
    agent = Agent(client, "test-model", executor)
    agent.send("temperature is 10 for demo-healthy")
    assert agent.nudges == 0


def test_tool_loop_is_bounded(executor):
    loop = reply(tool_calls=[tool_call("c", "get_patient", '{"patient_id": "demo-sick"}')])
    client = FakeClient([loop] * 20)
    with pytest.raises(AgentError):
        Agent(client, "test-model", executor).send("loop forever")
