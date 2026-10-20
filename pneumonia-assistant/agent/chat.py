"""Agent loop (OpenAI-style tool calling) and a terminal chat.

    python -m agent.chat                 # chat with the assistant
    python -m agent.chat --list-models   # show the provider's current model ids

The LLM is Gemini, reached through its OpenAI-compatible endpoint with the
OpenAI Python SDK (used only as a client library; nothing is sent to OpenAI):
    LLM_PROVIDER=gemini   GEMINI_API_KEY=...   LLM_MODEL=gemini-3.8-flash
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import openai
from dotenv import load_dotenv

from agent.guards import alerts_first, find_stated_readings, nudge_for
from agent.tools import TOOLS, ReadingProvenance, ToolExecutor

SYSTEM_PROMPT = (Path(__file__).resolve().parent / "system_prompt.txt").read_text(encoding="utf-8")

PROVIDERS = {
    # provider: (API key variable, base URL)
    "gemini": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/"),
}

MAX_TOOL_ROUNDS = 8      # model calls per doctor message
RETRIES = 4              # for rate limits (429) and temporary overload (5xx)
TOOL_FORMAT_RETRIES = 2  # the provider rejected a malformed tool call the model produced


class AgentError(Exception):
    """A failure to show the doctor as a plain message."""


class Agent:
    def __init__(self, client, model: str, executor: ToolExecutor,
                 system_prompt: str = SYSTEM_PROMPT, sleep=time.sleep, on_tool_call=None,
                 reasoning_effort: str | None = None):
        self.client = client
        self.model = model
        self.executor = executor
        self.sleep = sleep
        self.on_tool_call = on_tool_call          # optional callback(name, args_json, result)
        self.reasoning_effort = reasoning_effort
        self.provenance = ReadingProvenance()
        self.nudges = 0                # times the loop had to remind the model to send a reading
        self.alerts_prepended = 0      # times the code put the alerts at the front of a reply
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]

    def _complete(self):
        extra = {"reasoning_effort": self.reasoning_effort} if self.reasoning_effort else {}
        format_failures = 0
        for attempt in range(RETRIES + 1):
            try:
                return self.client.chat.completions.create(
                    model=self.model, messages=self.messages, tools=TOOLS, tool_choice="auto", **extra)
            except (openai.RateLimitError, openai.InternalServerError) as e:
                if _is_daily_quota(e):
                    # Waiting seconds won't help: the quota resets in hours.
                    raise AgentError("The language service's daily request limit has been reached "
                                     "(free tier). It resets within 24 hours; enabling billing on the "
                                     "API key removes this limit.") from e
                if attempt == RETRIES:
                    raise AgentError("The language service is busy (rate limit or overload). "
                                     "Please wait a minute and try again.") from e
                self.sleep(_retry_after(e, default=2 ** attempt))
            except openai.BadRequestError as e:
                text = str(e)
                if ("tool_use_failed" in text or "MALFORMED_FUNCTION_CALL" in text) \
                        and format_failures < TOOL_FORMAT_RETRIES:
                    format_failures += 1
                    continue
                raise AgentError("The language service rejected the request. Please rephrase and try again.") from e
            except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
                raise AgentError("The LLM API key is missing or invalid. Check the API key in .env.") from e
            except openai.NotFoundError as e:
                raise AgentError(f"Model '{self.model}' was not found. Set LLM_MODEL in .env to a "
                                 "current model that supports tool use.") from e
            except openai.APIConnectionError as e:
                raise AgentError("Could not reach the language service. Check the internet connection.") from e
            except openai.APIError as e:
                raise AgentError("The language service returned an error. Please try again.") from e
        raise AgentError("The language service is busy. Please try again.")

    def send(self, text: str) -> str:
        """One doctor message in, one assistant reply out (running any tools in between)."""
        self.messages.append({"role": "user", "content": text})
        self.provenance.note_doctor_message(text)
        stated = find_stated_readings(text)
        attempted: list[tuple[str, float]] = []   # readings sent to add_readings this turn
        safety = None                              # latest patient/assessment result this turn
        nudged = False
        for _ in range(MAX_TOOL_ROUNDS):
            msg = self._complete().choices[0].message
            if not msg.tool_calls:
                reply = msg.content or ""
                unsent = [s for s in stated if not any(
                    v == s[0] and abs(x - s[1]) < 1e-6 for v, x in attempted)]
                if unsent and not nudged:
                    # The model skipped a reading the doctor gave: remind it once, discard this draft.
                    nudged = True
                    self.nudges += 1
                    self.messages.append({"role": "user", "content": nudge_for(unsent)})
                    continue
                if safety and not alerts_first(reply, safety):
                    reply = f"{safety['lead_text']}\n\n{reply}"
                    self.alerts_prepended += 1
                self.messages.append({"role": "assistant", "content": reply})
                return reply
            assistant = {"role": "assistant", "tool_calls": [_tool_call_dict(tc) for tc in msg.tool_calls]}
            if msg.content:
                assistant["content"] = msg.content
            self.messages.append(assistant)
            for tc in msg.tool_calls:
                name = tc.function.name
                if name == "add_readings":
                    attempted += _readings_in(tc.function.arguments)
                result = (self.provenance.check(name, tc.function.arguments)
                          or self.executor.execute(name, tc.function.arguments))
                self.provenance.note_tool_result(result)
                if name in ("get_patient", "assess_patient") and not result.get("error"):
                    safety = result
                if self.on_tool_call:
                    self.on_tool_call(name, tc.function.arguments, result)
                self.messages.append({"role": "tool", "tool_call_id": tc.id,
                                      "content": json.dumps(result, default=str)})
        raise AgentError("I couldn't finish that request. Please try again or rephrase it.")


def _tool_call_dict(tc) -> dict:
    """The tool call exactly as the provider returned it, extra fields included.

    Gemini 3 models attach a thought signature to tool calls; sending the call back
    unchanged keeps multi-step tool use working.
    """
    if hasattr(tc, "model_dump"):
        return tc.model_dump(exclude_none=True)
    return {"id": tc.id, "type": "function",
            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}


def _readings_in(arguments: str | None) -> list[tuple[str, float]]:
    """(vital, value) pairs from an add_readings call, ignoring anything malformed."""
    try:
        readings = json.loads(arguments or "{}").get("readings") or []
        return [(r["vital"], float(r["value"])) for r in readings
                if isinstance(r, dict) and "vital" in r and "value" in r]
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return []


def _is_daily_quota(err: openai.APIStatusError) -> bool:
    """A per-day quota (Gemini: ...PerDay... quotaId, or a retry delay of hours), not a brief limit."""
    text = str(getattr(err, "body", "")) + str(err)
    if "PerDay" in text:
        return True
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", text)
    return bool(match) and float(match.group(1)) > 300


def _retry_after(err: openai.APIStatusError, default: float) -> float:
    """Seconds to wait: the retry-after header, Gemini's retryDelay in the body, or a backoff."""
    try:
        header = err.response.headers.get("retry-after")
        if header:
            return min(float(header), 30.0)
    except (TypeError, ValueError, AttributeError):
        pass
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", str(getattr(err, "body", "")) + str(err))
    return min(float(match.group(1)), 30.0) if match else default


def make_client():
    """OpenAI SDK client for LLM_PROVIDER (default gemini). Retries are handled by Agent."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider not in PROVIDERS:
        raise AgentError(f"Unknown LLM_PROVIDER '{provider}'. Use one of: {', '.join(PROVIDERS)}.")
    key_var, base_url = PROVIDERS[provider]
    if not os.getenv(key_var):
        raise AgentError(f"Set {key_var} in .env (see .env.example).")
    return openai.OpenAI(api_key=os.environ[key_var], base_url=base_url, max_retries=0)


def build_agent(on_tool_call=None) -> Agent:
    load_dotenv()
    missing = [k for k in ("LLM_MODEL", "API_KEY") if not os.getenv(k)]
    if missing:
        raise AgentError(f"Set {', '.join(missing)} in .env (see .env.example).")
    executor = ToolExecutor.from_url(os.getenv("API_URL", "http://127.0.0.1:8000"), os.environ["API_KEY"])
    return Agent(make_client(), os.environ["LLM_MODEL"], executor, on_tool_call=on_tool_call,
                 reasoning_effort=os.getenv("LLM_REASONING_EFFORT") or None)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pneumonia risk assistant (terminal chat).")
    parser.add_argument("--list-models", action="store_true", help="List the provider's model ids and exit.")
    parser.add_argument("--show-tools", action="store_true", help="Print each tool call and result.")
    args = parser.parse_args(argv)

    if args.list_models:
        load_dotenv()
        try:
            for m in sorted(make_client().models.list(), key=lambda m: m.id):
                print(m.id)
        except (AgentError, openai.APIError) as e:
            sys.exit(str(e))
        return

    def show(name, arguments, result):
        print(f"  [tool] {name}({arguments}) -> {json.dumps(result, default=str)[:300]}")

    try:
        agent = build_agent(on_tool_call=show if args.show_tools else None)
    except AgentError as e:
        sys.exit(str(e))
    print("Pneumonia risk assistant. Decision support only. Not a diagnosis. Type 'quit' to exit.")
    while True:
        try:
            text = input("\ndoctor> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue
        try:
            print(f"\nassistant> {agent.send(text)}")
        except AgentError as e:
            print(f"\nassistant> {e}")


if __name__ == "__main__":
    main()
