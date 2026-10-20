"""Chat conversations for the web app: one agent per conversation, locked to one patient.

Conversations live in memory and expire after CONVERSATION_TTL of inactivity (a
restart starts fresh conversations; assessments themselves are stored in the DB).
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

CONVERSATION_TTL = timedelta(hours=2)


@dataclass
class Conversation:
    owner_uid: str | None
    patient_id: str
    agent: object
    last_used: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latest_result: dict | None = None


class Conversations:
    def __init__(self, make_agent):
        """make_agent(patient_id, on_tool_call) -> Agent scoped to that patient."""
        self._make_agent = make_agent
        self._items: dict[str, Conversation] = {}
        self._lock = threading.Lock()

    def _expire(self, now):
        for cid in [c for c, conv in self._items.items() if now - conv.last_used > CONVERSATION_TTL]:
            del self._items[cid]

    def get_or_create(self, conversation_id: str | None, owner_uid: str | None,
                      patient_id: str) -> tuple[str, Conversation]:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._expire(now)
            conv = self._items.get(conversation_id or "")
            if conv is not None and conv.owner_uid == owner_uid and conv.patient_id == patient_id:
                conv.last_used = now
                return conversation_id, conv
            cid = uuid.uuid4().hex
            conv = Conversation(owner_uid, patient_id, agent=None)

            def remember(name, _arguments, result):
                if name == "assess_patient" and not result.get("error"):
                    conv.latest_result = result

            conv.agent = self._make_agent(patient_id, remember)
            self._items[cid] = conv
            return cid, conv
