from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.brief_import import parse_brief_content
from app.services.gateway_db import connect_gateway_db, ensure_gateway_schema


class BriefSessionStore:
    """SQLite-backed store for the active executive brief (single-user POC)."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        ensure_gateway_schema(self.db_path)
        self._payload: Optional[Dict[str, Any]] = self._load()

    def clear(self) -> None:
        self._payload = None
        self._save()

    def set_from_generation(
        self,
        *,
        title: str,
        output: Dict[str, Any],
        html_report: str,
        database_name: str,
    ) -> Dict[str, Any]:
        opportunities = output.get("top_signal_opportunities") or []
        self._payload = {
            "title": title,
            "database_name": database_name,
            "executive_summary": output.get("executive_summary", ""),
            "html_report": html_report,
            "output": output,
            "opportunities": opportunities,
            "source": "generated",
        }
        self._save()
        return self.summary()

    def import_content(
        self,
        *,
        html: Optional[str] = None,
        json_text: Optional[str] = None,
        title: Optional[str] = None,
        database_name: str = "",
    ) -> Dict[str, Any]:
        parsed = parse_brief_content(html=html, json_text=json_text)
        self._payload = {
            "title": title or parsed.get("title") or "Imported Executive Brief",
            "database_name": database_name or parsed.get("database_name") or "",
            "executive_summary": parsed.get("executive_summary", ""),
            "html_report": html or parsed.get("html_report", ""),
            "output": parsed.get("output", {}),
            "opportunities": parsed.get("opportunities", []),
            "source": "imported",
        }
        self._save()
        return self.summary()

    def is_loaded(self) -> bool:
        return self._payload is not None

    def summary(self) -> Dict[str, Any]:
        if not self._payload:
            return {"loaded": False, "opportunities": []}
        opps = self._payload.get("opportunities") or []
        return {
            "loaded": True,
            "title": self._payload.get("title"),
            "database_name": self._payload.get("database_name"),
            "source": self._payload.get("source"),
            "executive_summary": self._payload.get("executive_summary", "")[:500],
            "opportunity_count": len(opps),
            "opportunities": [
                {
                    "index": i,
                    "title": o.get("title"),
                    "overall_score": o.get("overall_score"),
                    "indicator_count": len(o.get("indicators") or []),
                }
                for i, o in enumerate(opps, 1)
            ],
        }

    def get_opportunity(self, index: int) -> Dict[str, Any]:
        if not self._payload:
            raise ValueError("No brief loaded. Generate or import an executive brief first.")
        opps: List[Dict[str, Any]] = self._payload.get("opportunities") or []
        if index < 1 or index > len(opps):
            raise ValueError(f"Opportunity index must be between 1 and {len(opps)}.")
        return dict(opps[index - 1])

    def get_context(self) -> Dict[str, Any]:
        if not self._payload:
            return {}
        return dict(self._payload)

    def _load(self) -> Optional[Dict[str, Any]]:
        with connect_gateway_db(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM brief_session WHERE id = 1"
            ).fetchone()
        if not row or not row["payload_json"]:
            return None
        return json.loads(row["payload_json"])

    def _save(self) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(self._payload) if self._payload else None
        with connect_gateway_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO brief_session (id, payload_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  payload_json = excluded.payload_json,
                  updated_at = excluded.updated_at
                """,
                (payload_json, updated_at),
            )
            conn.commit()
