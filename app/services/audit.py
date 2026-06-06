from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import Settings, settings as default_settings


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  question TEXT,
  generated_sql TEXT,
  normalized_sql TEXT,
  valid INTEGER,
  blocked_reason TEXT,
  row_count INTEGER,
  model_name TEXT,
  metadata_json TEXT
);
"""


class AuditService:
    def __init__(self, config: Optional[Settings] = None) -> None:
        self.config = config or default_settings
        self.db_path = Path(self.config.audit_db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def log_event(
        self,
        event_type: str,
        *,
        question: Optional[str] = None,
        generated_sql: Optional[str] = None,
        normalized_sql: Optional[str] = None,
        valid: Optional[bool] = None,
        blocked_reason: Optional[str] = None,
        row_count: Optional[int] = None,
        model_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_events (
                  created_at, event_type, question, generated_sql, normalized_sql,
                  valid, blocked_reason, row_count, model_name, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    event_type,
                    question,
                    generated_sql,
                    normalized_sql,
                    1 if valid else (0 if valid is False else None),
                    blocked_reason,
                    row_count,
                    model_name,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, event_type, question, generated_sql, normalized_sql,
                       valid, blocked_reason, row_count, model_name, metadata_json
                FROM audit_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        events: List[Dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "event_type": row["event_type"],
                    "question": row["question"],
                    "generated_sql": row["generated_sql"],
                    "normalized_sql": row["normalized_sql"],
                    "valid": bool(row["valid"]) if row["valid"] is not None else None,
                    "blocked_reason": row["blocked_reason"],
                    "row_count": row["row_count"],
                    "model_name": row["model_name"],
                    "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else None,
                }
            )
        return events
