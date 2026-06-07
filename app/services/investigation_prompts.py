from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.prompt_builder import compact_schema_metadata


PLAN_SYSTEM = """You are a senior analytics investigator planning read-only SQL Server queries.

Return ONLY valid JSON (no markdown fences) with this shape:
{
  "investigation_title": "short title",
  "approach_summary": "2-3 sentences on tables and strategy",
  "queries": [
    {
      "purpose": "what this query proves",
      "focus_tables": ["schema.table"],
      "question_for_sql": "precise natural language for SQL generation"
    }
  ],
  "stop_after_queries": 3
}

Rules:
- Use only schema objects provided.
- Start with landscape/discovery queries (counts, distinct values, top aggregates) before row detail.
- Plan 2-4 queries max unless the user question is very narrow.
- Never plan writes, PII exposure, or cross-database access."""


NEXT_QUERY_SYSTEM = """You are continuing a multi-step SQL investigation on SQL Server.

Return ONLY valid JSON:
{
  "continue": true,
  "purpose": "why run this next query",
  "question_for_sql": "precise NL for SQL generation",
  "is_final": false
}

If enough evidence exists, return:
{"continue": false, "reason": "why stopping"}"""


SYNTHESIS_SYSTEM = """You are writing an executive investigation report from SQL query results.

Return ONLY valid JSON:
{
  "title": "report title",
  "executive_summary": "3-5 sentences grounded in query results",
  "key_findings": ["bullet 1", "bullet 2"],
  "tables_used": ["schema.table"],
  "indicators_validated": ["field or metric names confirmed in data"],
  "caveats": ["limitations, row caps, missing joins"],
  "recommended_next_steps": ["action 1"]
}

Be factual. Do not invent numbers not present in the step results."""


SQL_INVESTIGATION_SYSTEM = """You are a SQL Server analyst inside a private, read-only analytics gateway.

Rules:
- Generate exactly one SQL Server SELECT statement.
- Use only the provided schemas, views, and columns.
- Prefer aggregates first; use row-level SELECT only when needed for examples (always with TOP).
- Do not query raw sensitive/PII columns.
- No INSERT, UPDATE, DELETE, MERGE, DROP, ALTER, TRUNCATE, CREATE, EXEC.
- Include TOP when results could be large.
- Return only SQL, no markdown, no explanation."""


def build_plan_prompt(
    *,
    user_question: str,
    mode: str,
    opportunity: Dict[str, Any] | None,
    brief_title: str,
    schema_metadata: Dict[str, Any],
    max_schema_objects: int,
) -> tuple[str, str]:
    compact = compact_schema_metadata(schema_metadata, max_objects=max_schema_objects)
    opp_block = ""
    if opportunity:
        opp_block = f"""
Brief opportunity context:
- Title: {opportunity.get("title", "")}
- Description: {opportunity.get("description", "")}
- Indicators: {json.dumps(opportunity.get("indicators") or [])}
- Example insights: {json.dumps(opportunity.get("example_insights") or [])}
- Required data: {opportunity.get("required_data", "")}
"""
    user = f"""Investigation mode: {mode}
Brief: {brief_title or "none"}
User request:
{user_question}
{opp_block}
Allowed schema metadata:
{json.dumps(compact, indent=2)}

Plan the investigation queries to answer the user request with real data."""
    return PLAN_SYSTEM, user


def build_next_query_prompt(
    *,
    user_question: str,
    steps: List[Dict[str, Any]],
    schema_metadata: Dict[str, Any],
    max_schema_objects: int,
) -> tuple[str, str]:
    compact = compact_schema_metadata(schema_metadata, max_objects=max_schema_objects)
    prior = []
    for step in steps:
        prior.append(
            {
                "purpose": step.get("purpose"),
                "sql": step.get("sql"),
                "row_count": step.get("row_count"),
                "columns": step.get("columns"),
                "sample_rows": (step.get("rows") or [])[:5],
                "error": step.get("error"),
            }
        )
    user = f"""Original user request:
{user_question}

Steps completed so far:
{json.dumps(prior, indent=2, default=str)}

Schema:
{json.dumps(compact, indent=2)}

Decide the next query or stop."""
    return NEXT_QUERY_SYSTEM, user


def build_investigation_sql_prompt(
    *,
    question_for_sql: str,
    schema_metadata: Dict[str, Any],
    max_rows: int,
    max_schema_objects: int,
    prior_steps: List[Dict[str, Any]],
) -> tuple[str, str]:
    compact = compact_schema_metadata(schema_metadata, max_objects=max_schema_objects)
    prior_sql = "\n".join(
        f"-- Step {i + 1}: {s.get('purpose', '')}\n{s.get('sql', '')}"
        for i, s in enumerate(prior_steps)
        if s.get("sql")
    )
    user = f"""Investigation sub-question:
{question_for_sql}

Prior queries in this investigation:
{prior_sql or "(none yet)"}

Allowed schema metadata:
{json.dumps(compact, indent=2)}

Constraints:
- SQL Server dialect, read-only SELECT only
- Schema-qualified names (e.g. ai.vw_demo_sales_summary)
- TOP {max_rows} when many rows possible
- Prefer aggregates; row samples only with TOP

Return one SQL statement."""
    return SQL_INVESTIGATION_SYSTEM, user


def build_synthesis_prompt(
    *,
    user_question: str,
    mode: str,
    opportunity: Dict[str, Any] | None,
    steps: List[Dict[str, Any]],
) -> tuple[str, str]:
    step_payload = []
    for step in steps:
        step_payload.append(
            {
                "purpose": step.get("purpose"),
                "sql": step.get("sql"),
                "row_count": step.get("row_count"),
                "columns": step.get("columns"),
                "rows": (step.get("rows") or [])[:15],
                "error": step.get("error"),
            }
        )
    opp_json = json.dumps(opportunity or {}, indent=2)
    user = f"""Mode: {mode}
User request: {user_question}
Brief opportunity (if any): {opp_json}

Query steps and results:
{json.dumps(step_payload, indent=2, default=str)}

Write the investigation report JSON."""
    return SYNTHESIS_SYSTEM, user
