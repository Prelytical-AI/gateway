from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.core.config import Settings, settings as default_settings

logger = logging.getLogger(__name__)


def _import_pyodbc():
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError(
            "pyodbc is not available. Install ODBC Driver for SQL Server and pyodbc."
        ) from exc
    return pyodbc


class SQLServerService:
    def __init__(self, config: Optional[Settings] = None) -> None:
        self.config = config or default_settings

    def test_connection(self) -> tuple[bool, str]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 AS ok")
                row = cursor.fetchone()
                if row and row[0] == 1:
                    return True, "Connection successful."
                return False, "Unexpected response from SQL Server."
        except Exception as exc:
            logger.exception("SQL connection test failed")
            return False, str(exc)

    def get_allowed_schema_metadata(self) -> Dict[str, Any]:
        allowed = self.config.allowed_schemas
        if not allowed:
            return {"schemas": []}

        placeholders = ",".join("?" for _ in allowed)
        query = f"""
            SELECT
                s.name AS schema_name,
                o.name AS object_name,
                o.type_desc AS object_type,
                c.name AS column_name,
                t.name AS data_type,
                c.is_nullable
            FROM sys.schemas s
            INNER JOIN sys.objects o ON o.schema_id = s.schema_id
            INNER JOIN sys.columns c ON c.object_id = o.object_id
            INNER JOIN sys.types t ON t.user_type_id = c.user_type_id
            WHERE s.name IN ({placeholders})
              AND o.type IN ('V', 'U')
            ORDER BY s.name, o.name, c.column_id
        """

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, allowed)
            rows = cursor.fetchall()

        schema_map: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            schema_name = row.schema_name
            object_name = row.object_name
            object_type = "VIEW" if "VIEW" in row.object_type else "TABLE"
            key = f"{schema_name}.{object_name}"
            if key not in schema_map:
                schema_map[key] = {
                    "schema": schema_name,
                    "name": object_name,
                    "type": object_type,
                    "columns": [],
                }
            schema_map[key]["columns"].append(
                {
                    "name": row.column_name,
                    "type": row.data_type.lower(),
                    "nullable": bool(row.is_nullable),
                }
            )

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for obj in schema_map.values():
            grouped.setdefault(obj["schema"], []).append(
                {
                    "name": obj["name"],
                    "type": obj["type"],
                    "columns": obj["columns"],
                }
            )

        return {
            "schemas": [
                {"schema": schema, "objects": objects}
                for schema, objects in sorted(grouped.items())
            ]
        }

    def execute_readonly_query(self, sql: str) -> Dict[str, Any]:
        with self._connect() as conn:
            conn.timeout = self.config.sqlserver_query_timeout_seconds
            cursor = conn.cursor()
            cursor.execute(sql)

            if cursor.description is None:
                return {"columns": [], "rows": [], "row_count": 0}

            columns = [col[0] for col in cursor.description]
            fetched = cursor.fetchmany(self.config.sqlserver_max_rows + 1)
            truncated = len(fetched) > self.config.sqlserver_max_rows
            if truncated:
                fetched = fetched[: self.config.sqlserver_max_rows]

            rows = [
                {columns[i]: _json_safe_value(row[i]) for i in range(len(columns))}
                for row in fetched
            ]
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
            }

    def _connect(self):
        pyodbc = _import_pyodbc()
        return pyodbc.connect(
            self.config.connection_string(),
            timeout=self.config.sqlserver_connection_timeout_seconds,
        )


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
