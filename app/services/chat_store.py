from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.gateway_db import connect_gateway_db, ensure_gateway_schema


class ChatStore:
    """SQLite-backed chat history for the gateway (single-user POC)."""

    def __init__(self, db_path: str | Path, max_messages: int = 40) -> None:
        self.db_path = Path(db_path)
        self.max_messages = max_messages
        ensure_gateway_schema(self.db_path)

    def clear(self) -> None:
        with connect_gateway_db(self.db_path) as conn:
            conn.execute("DELETE FROM chat_messages")
            conn.commit()

    def list_messages(self) -> List[Dict[str, Any]]:
        with connect_gateway_db(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, created_at, action, attachments_json, artifact_json
                FROM chat_messages
                ORDER BY created_at ASC
                """
            ).fetchall()
        return [_row_to_message(row) for row in rows]

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
        self._insert(msg)
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
        self._insert(msg)
        return dict(msg)

    def update_message(self, message_id: str, *, content: str) -> None:
        with connect_gateway_db(self.db_path) as conn:
            conn.execute(
                "UPDATE chat_messages SET content = ? WHERE id = ?",
                (content.strip(), message_id),
            )
            conn.commit()

    def recent_for_model(self, limit: int = 12) -> List[Dict[str, str]]:
        messages = self.list_messages()[-limit:]
        out: List[Dict[str, str]] = []
        for msg in messages:
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

    def _insert(self, msg: Dict[str, Any]) -> None:
        attachments_json = json.dumps(msg.get("attachments") or [])
        artifact_json = json.dumps(msg.get("artifact") or {}) if msg.get("artifact") is not None else None
        with connect_gateway_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (
                  id, role, content, created_at, action, attachments_json, artifact_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg["id"],
                    msg["role"],
                    msg["content"],
                    msg["created_at"],
                    msg.get("action"),
                    attachments_json,
                    artifact_json if msg["role"] == "assistant" else None,
                ),
            )
            conn.commit()
            self._trim(conn)

    def _trim(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT COUNT(*) AS c FROM chat_messages").fetchone()
        count = int(row["c"]) if row else 0
        excess = count - self.max_messages
        if excess <= 0:
            return
        conn.execute(
            """
            DELETE FROM chat_messages
            WHERE id IN (
              SELECT id FROM chat_messages
              ORDER BY created_at ASC
              LIMIT ?
            )
            """,
            (excess,),
        )
        conn.commit()


def _row_to_message(row: Any) -> Dict[str, Any]:
    msg: Dict[str, Any] = {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
    }
    if row["attachments_json"]:
        msg["attachments"] = json.loads(row["attachments_json"])
    if row["action"]:
        msg["action"] = row["action"]
    if row["artifact_json"]:
        msg["artifact"] = json.loads(row["artifact_json"])
    return msg


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
