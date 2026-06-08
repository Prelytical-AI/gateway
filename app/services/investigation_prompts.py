from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.prompt_builder import compact_schema_metadata


PLAN_SYSTEM = """You are a senior analytics investigator planning read-only SQL Server queries.

Return ONLY valid JSON (no markdown fences) with this shape:
{
  "investigation_title": "short title",
  "approach_summary": "2-3 sentences on business angle and data strategy for an executive reader",
  "queries": [
    {
      "purpose": "business-facing label e.g. Total revenue overview",
      "focus_tables": ["schema.table"],
      "question_for_sql": "precise natural language for SQL generation"
    }
  ],
  "stop_after_queries": 3
}

Rules:
- Prefer ai.* views when they answer the question — they are pre-joined and reliable.
- Use dbo.* only when needed; keep JOINs to at most 2 tables.
- Start with simple single-table or single-view aggregates before complex joins.
- Plan 2-4 queries max. Each query should stand alone if others fail.
- Never plan writes, PII exposure, or cross-database access."""


NEXT_QUERY_SYSTEM = """You are continuing a multi-step SQL investigation on SQL Server.

Return ONLY valid JSON:
{
  "continue": true,
  "purpose": "business-facing label",
  "question_for_sql": "precise NL for SQL generation",
  "is_final": false
}

If enough evidence exists, return:
{"continue": false, "reason": "why stopping"}

Prefer simpler follow-up queries (views, single-table aggregates) over complex joins."""


SYNTHESIS_SYSTEM = """You are writing an executive business report from validated SQL query results.

Return ONLY valid JSON:
{
  "title": "report title",
  "approach_summary": "how we analyzed the data (no SQL jargon)",
  "executive_summary": "3-5 sentences for an executive, grounded in numbers from results",
  "trends_and_patterns": ["observed trend or pattern with specific numbers"],
  "business_implications": ["so what for the business — decision-ready"],
  "key_findings": ["concise finding with evidence"],
  "tables_used": ["schema.table"],
  "caveats": ["honest limits e.g. row caps, partial coverage — no SQL error text"],
  "recommended_next_steps": ["business action"]
}

CRITICAL:
- Write for executives, not engineers. No SQL, no step numbers, no alias talk.
- Use ONLY numbers present in the query results or python_highlights.
- If some planned analyses are missing from results, note coverage gaps in caveats without pasting errors.
- trends_and_patterns and business_implications are required when data exists."""


SQL_INVESTIGATION_SYSTEM = """You are a SQL Server analyst inside a private, read-only analytics gateway.

Rules:
- Generate exactly one SQL Server SELECT statement.
- Use only the provided schemas, views, and columns.
- ALWAYS schema-qualify tables: dbo.Orders, ai.vw_monthly_revenue (never bare table names).
- Define aliases in FROM/JOIN and use the SAME alias everywhere (e.g. dbo.ProductCategories pc → pc.category_name, never c.category_name).
- Prefer ai.* views over multi-table joins when a view fits the question.
- Keep JOINs to at most 2 tables; avoid correlated subqueries in JOIN/WHERE when possible.
- Prefer aggregates; row samples only with TOP.
- No INSERT, UPDATE, DELETE, MERGE, DROP, ALTER, TRUNCATE, CREATE, EXEC.
- Include TOP when results could be large.
- Return only SQL, no markdown."""


SIMPLIFY_SQL_HINT = """
SIMPLIFY MODE — previous query failed:
- Use ONE schema-qualified table or ai.* view only. NO JOINs unless absolutely required.
- Single GROUP BY or simple aggregate (SUM/COUNT/AVG).
- Match column names exactly to schema metadata."""


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
        if step.get("error"):
            continue
        prior.append(
            {
                "purpose": step.get("purpose"),
                "row_count": step.get("row_count"),
                "columns": step.get("columns"),
                "sample_rows": (step.get("rows") or [])[:5],
            }
        )
    user = f"""Original user request:
{user_question}

Successful steps so far:
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
    simplify: bool = False,
    last_error: str = "",
) -> tuple[str, str]:
    compact = compact_schema_metadata(schema_metadata, max_objects=max_schema_objects)
    user = f"""Investigation sub-question:
{question_for_sql}

Allowed schema metadata:
{json.dumps(compact, indent=2)}

Constraints:
- SQL Server dialect, read-only SELECT only
- Schema-qualified names (dbo.Orders, ai.vw_monthly_revenue)
- TOP {max_rows} when many rows possible
- Prefer ai views; keep JOINs minimal

Return one SQL statement."""
    if last_error:
        user += f"\n\nPrevious attempt failed:\n{last_error}\nFix the query."
    if simplify:
        user += SIMPLIFY_SQL_HINT
    return SQL_INVESTIGATION_SYSTEM, user


def build_synthesis_prompt(
    *,
    user_question: str,
    mode: str,
    opportunity: Dict[str, Any] | None,
    steps: List[Dict[str, Any]],
    approach_summary: str,
    python_highlights: List[Dict[str, Any]],
) -> tuple[str, str]:
    step_payload = []
    for step in steps:
        if step.get("error") or not step.get("rows"):
            continue
        step_payload.append(
            {
                "purpose": step.get("purpose"),
                "row_count": step.get("row_count"),
                "columns": step.get("columns"),
                "rows": (step.get("rows") or [])[:20],
            }
        )
    opp_json = json.dumps(opportunity or {}, indent=2)
    user = f"""Mode: {mode}
User request: {user_question}
Brief opportunity (if any): {opp_json}
Analysis approach: {approach_summary}

Python-derived highlights:
{json.dumps(python_highlights, indent=2, default=str)}

Query results (successful only):
{json.dumps(step_payload, indent=2, default=str)}

Write the executive business report JSON."""
    return SYNTHESIS_SYSTEM, user
