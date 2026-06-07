from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

CREATE_CHAT_TABLE = """
CREATE TABLE IF NOT EXISTS chat_messages (
  id TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  action TEXT,
  attachments_json TEXT,
  artifact_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);
"""

CREATE_BRIEF_TABLE = """
CREATE TABLE IF NOT EXISTS brief_session (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  payload_json TEXT,
  updated_at TEXT NOT NULL
);
"""


def ensure_gateway_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect_gateway_db(db_path) as conn:
        conn.executescript(CREATE_CHAT_TABLE + CREATE_BRIEF_TABLE)
        conn.commit()


@contextmanager
def connect_gateway_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
