from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Parenthesis
from sqlparse.tokens import Keyword, DML

from app.core.config import Settings, settings as default_settings


FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "REVOKE",
    "DENY",
    "BACKUP",
    "RESTORE",
    "BULK",
    "OPENROWSET",
    "OPENDATASOURCE",
    "XP_CMDSHELL",
    "SP_CONFIGURE",
}

FORBIDDEN_PATTERNS = [
    re.compile(r"\bxp_cmdshell\b", re.IGNORECASE),
    re.compile(r"\bsp_configure\b", re.IGNORECASE),
    re.compile(r"\bopenrowset\b", re.IGNORECASE),
    re.compile(r"\bopendatasource\b", re.IGNORECASE),
    re.compile(r"\bbulk\s+insert\b", re.IGNORECASE),
    re.compile(r"\binto\s+outfile\b", re.IGNORECASE),
    re.compile(r"\b;\s*(select|with|insert|update|delete|drop|exec)\b", re.IGNORECASE),
]

THREE_PART_NAME = re.compile(
    r"\b([A-Za-z_][\w$]*)\.([A-Za-z_][\w$]*)\.([A-Za-z_][\w$]*)\b"
)
TWO_PART_NAME = re.compile(r"\b([A-Za-z_][\w$]*)\.([A-Za-z_][\w$]*)\b")

SELECT_TOP_PATTERN = re.compile(r"^\s*select\s+(?:distinct\s+)?top\s+\d+\b", re.IGNORECASE)
SELECT_STAR_PATTERN = re.compile(r"^\s*select\s+\*\s+from\b", re.IGNORECASE)
SELECT_COLUMNS_PATTERN = re.compile(r"^\s*select\s+(?!top\b)(.+?)\s+from\b", re.IGNORECASE | re.DOTALL)
WITH_CTE_PATTERN = re.compile(r"^\s*with\b", re.IGNORECASE)


@dataclass
class ValidationResult:
    valid: bool
    normalized_sql: str
    blocked_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "normalized_sql": self.normalized_sql,
            "blocked_reason": self.blocked_reason,
            "warnings": self.warnings,
        }


def validate_sql(sql: str, config: Optional[Settings] = None) -> ValidationResult:
    cfg = config or default_settings
    warnings: List[str] = []

    if not sql or not sql.strip():
        return ValidationResult(
            valid=False,
            normalized_sql="",
            blocked_reason="SQL is empty.",
        )

    cleaned = sql.strip().rstrip(";").strip()
    statements = [s.strip() for s in sqlparse.split(cleaned) if s.strip()]
    if len(statements) != 1:
        return ValidationResult(
            valid=False,
            normalized_sql=cleaned,
            blocked_reason="Only a single SQL statement is allowed.",
        )

    normalized = statements[0]
    upper = normalized.upper()

    if cfg.guardrails_require_select_only:
        if not (upper.lstrip().startswith("SELECT") or upper.lstrip().startswith("WITH")):
            return ValidationResult(
                valid=False,
                normalized_sql=normalized,
                blocked_reason="Only SELECT statements (or WITH ... SELECT) are allowed.",
            )

    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(normalized):
            return ValidationResult(
                valid=False,
                normalized_sql=normalized,
                blocked_reason=f"Blocked pattern detected: {pattern.pattern}",
            )

    parsed = sqlparse.parse(normalized)[0]
    for token in parsed.flatten():
        if token.ttype is Keyword and token.value.upper() in FORBIDDEN_KEYWORDS:
            return ValidationResult(
                valid=False,
                normalized_sql=normalized,
                blocked_reason=f"Forbidden keyword not allowed: {token.value.upper()}",
            )
        if token.ttype is DML and token.value.upper() != "SELECT":
            return ValidationResult(
                valid=False,
                normalized_sql=normalized,
                blocked_reason=f"Only SELECT is allowed, found {token.value.upper()}.",
            )

    if re.search(r"/\*.*?(DROP|DELETE|EXEC|XP_CMDSHELL).*?\*/", normalized, re.IGNORECASE | re.DOTALL):
        return ValidationResult(
            valid=False,
            normalized_sql=normalized,
            blocked_reason="Suspicious content found in SQL comments.",
        )

    if _has_cross_database_reference(normalized, cfg):
        return ValidationResult(
            valid=False,
            normalized_sql=normalized,
            blocked_reason="Cross-database references are not allowed.",
        )

    schema_refs = _extract_schema_references(normalized)
    if cfg.guardrails_require_allowed_schema:
        allowed = set(cfg.allowed_schemas)
        blocked = set(cfg.blocked_schemas)
        for schema in schema_refs:
            schema_lower = schema.lower()
            if schema_lower in blocked:
                return ValidationResult(
                    valid=False,
                    normalized_sql=normalized,
                    blocked_reason=f"Schema '{schema}' is not allowed.",
                )
            if schema_lower not in allowed:
                return ValidationResult(
                    valid=False,
                    normalized_sql=normalized,
                    blocked_reason=(
                        f"Schema '{schema}' is not in allowed schemas: "
                        f"{', '.join(cfg.allowed_schemas)}."
                    ),
                )

    if cfg.guardrails_block_pii_columns:
        pii_hit = _find_blocked_column(normalized, cfg.blocked_column_patterns)
        if pii_hit:
            return ValidationResult(
                valid=False,
                normalized_sql=normalized,
                blocked_reason=f"Blocked sensitive column pattern detected: {pii_hit}",
            )

    if cfg.guardrails_append_top_limit and not WITH_CTE_PATTERN.match(normalized):
        top_result = _append_top_limit(normalized, cfg.sqlserver_max_rows)
        if top_result.blocked_reason:
            return ValidationResult(
                valid=False,
                normalized_sql=normalized,
                blocked_reason=top_result.blocked_reason,
                warnings=top_result.warnings,
            )
        normalized = top_result.normalized_sql
        warnings.extend(top_result.warnings)

    return ValidationResult(
        valid=True,
        normalized_sql=normalized,
        blocked_reason=None,
        warnings=warnings,
    )


def _append_top_limit(sql: str, max_rows: int) -> ValidationResult:
    if SELECT_TOP_PATTERN.match(sql):
        return ValidationResult(valid=True, normalized_sql=sql)

    if WITH_CTE_PATTERN.match(sql):
        return ValidationResult(
            valid=False,
            normalized_sql=sql,
            blocked_reason=(
                "CTE queries must include TOP in the final SELECT or use a simpler query."
            ),
        )

    if SELECT_STAR_PATTERN.match(sql):
        normalized = SELECT_STAR_PATTERN.sub(f"SELECT TOP {max_rows} * FROM", sql, count=1)
        return ValidationResult(
            valid=True,
            normalized_sql=normalized,
            warnings=[f"Appended TOP {max_rows} to SELECT * query."],
        )

    match = SELECT_COLUMNS_PATTERN.match(sql)
    if match:
        columns = match.group(1).strip()
        normalized = SELECT_COLUMNS_PATTERN.sub(f"SELECT TOP {max_rows} {columns} FROM", sql, count=1)
        return ValidationResult(
            valid=True,
            normalized_sql=normalized,
            warnings=[f"Appended TOP {max_rows} to SELECT query."],
        )

    return ValidationResult(valid=True, normalized_sql=sql)


def _extract_schema_references(sql: str) -> List[str]:
    schemas: set[str] = set()
    three_part_spans: List[tuple[int, int]] = []

    for match in THREE_PART_NAME.finditer(sql):
        schemas.add(match.group(2))
        three_part_spans.append(match.span())

    for match in TWO_PART_NAME.finditer(sql):
        start, _ = match.span()
        if any(start >= span[0] and start < span[1] for span in three_part_spans):
            continue
        schemas.add(match.group(1))

    return sorted(schemas)


def _has_cross_database_reference(sql: str, cfg: Settings) -> bool:
    allowed_db = cfg.sqlserver_database.lower()
    for match in THREE_PART_NAME.finditer(sql):
        db_name = match.group(1).lower()
        if db_name != allowed_db:
            return True
    bracketed = re.findall(
        r"\[([^\]]+)\]\.\[([^\]]+)\]\.\[([^\]]+)\]",
        sql,
        re.IGNORECASE,
    )
    for db_name, _, _ in bracketed:
        if db_name.lower() != allowed_db:
            return True
    return False


def _find_blocked_column(sql: str, patterns: List[str]) -> Optional[str]:
    identifiers = _extract_identifiers(sql)
    for ident in identifiers:
        ident_lower = ident.lower()
        for pattern in patterns:
            if pattern in ident_lower:
                return pattern
    return None


def _extract_identifiers(sql: str) -> List[str]:
    parsed = sqlparse.parse(sql)[0]
    names: List[str] = []

    def walk(token):
        if isinstance(token, IdentifierList):
            for child in token.tokens:
                walk(child)
        elif isinstance(token, Identifier):
            names.append(token.get_real_name() or token.value)
        elif isinstance(token, Parenthesis):
            return
        elif hasattr(token, "tokens"):
            for child in token.tokens:
                walk(child)

    walk(parsed)
    return names
