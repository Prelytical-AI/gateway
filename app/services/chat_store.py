from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ChatStore:
    """In-memory chat history for the gateway (single-user POC)."""

    def __init__(self, max_messages: int = 40) -> None:
        self.max_messages = max_messages
        self._messages: List[Dict[str, Any]] = []

    def clear(self) -> None:
        self._messages.clear()

    def list_messages(self) -> List[Dict[str, Any]]:
        return [dict(m) for m in self._messages]

    def add_user_message(
        self,
        content: str,
        *,
        attachments: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        msg = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": content.strip(),
            "created_at": _now(),
            "attachments": attachments or [],
        }
        self._messages.append(msg)
        self._trim()
        return dict(msg)

    def add_assistant_message(
        self,
        content: str,
        *,
        action: str = "reply",
        artifact: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        msg = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": content.strip(),
            "created_at": _now(),
            "action": action,
            "artifact": artifact or {},
        }
        self._messages.append(msg)
        self._trim()
        return dict(msg)

    def recent_for_model(self, limit: int = 12) -> List[Dict[str, str]]:
        """Compact history for LLM routing / replies."""
        out: List[Dict[str, str]] = []
        for msg in self._messages[-limit:]:
            role = msg["role"]
            text = msg["content"]
            if msg.get("attachments"):
                names = ", ".join(a.get("filename", "file") for a in msg["attachments"])
                text = f"{text}\n[Attached: {names}]" if text else f"[Attached: {names}]"
            action = msg.get("action")
            if role == "assistant" and action and action != "reply":
                text = f"{text}\n(completed: {action})"
            out.append({"role": role, "content": text[:4000]})
        return out

    def _trim(self) -> None:
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages :]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
