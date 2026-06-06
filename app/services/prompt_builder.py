from __future__ import annotations

import json
from typing import Any, Dict, List


SQL_SYSTEM_PROMPT = """You are a SQL Server analyst inside a private, read-only analytics gateway.

Rules:
- Generate exactly one SQL Server SELECT statement.
- Use only the provided schemas, views, and columns.
- Prefer aggregated answers.
- Do not query raw sensitive data.
- Do not use INSERT, UPDATE, DELETE, MERGE, DROP, ALTER, TRUNCATE, CREATE, EXEC, xp_cmdshell, or stored procedures.
- Do not use cross-database queries.
- Do not use schemas that are not explicitly provided.
- Include TOP if the query could return many rows.
- Return only SQL, no markdown, no explanation."""

SUMMARY_SYSTEM_PROMPT = """You are a business analyst summarizing SQL query results for executives.
Be concise, factual, and grounded only in the provided rows.
Mention when results may be limited by TOP/row caps.
Do not invent numbers not present in the results."""


def build_sql_generation_prompt(
    question: str,
    schema_metadata: Dict[str, Any],
    max_rows: int,
) -> tuple[str, str]:
    schema_json = json.dumps(schema_metadata, indent=2)
    user_prompt = f"""User question:
{question}

Allowed schema metadata (use only these objects and columns):
{schema_json}

Constraints:
- SQL Server dialect
- Read-only SELECT only
- Use schema-qualified names like ai.vw_demo_sales_summary
- Include TOP {max_rows} when the query could return many rows
- Prefer aggregates for summary questions

Examples of allowed query style:
SELECT TOP 10 region, SUM(revenue) AS total_revenue
FROM ai.vw_demo_sales_summary
GROUP BY region
ORDER BY total_revenue DESC;

SELECT TOP 5 month_start, region, revenue
FROM ai.vw_demo_sales_summary
ORDER BY revenue DESC;

Return only one SQL statement."""

    return SQL_SYSTEM_PROMPT, user_prompt


def build_summarization_prompt(
    question: str,
    sql: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    row_count: int,
    max_rows: int,
    truncated: bool = False,
) -> tuple[str, str]:
    preview_rows = rows[:20]
    user_prompt = f"""Original question:
{question}

Executed SQL:
{sql}

Result columns:
{json.dumps(columns)}

Row count returned: {row_count}
Max row cap: {max_rows}
Results truncated by cap: {truncated}

Result rows (sample):
{json.dumps(preview_rows, indent=2)}

Write a concise business answer."""

    return SUMMARY_SYSTEM_PROMPT, user_prompt


def build_blocked_answer(blocked_reason: str) -> str:
    return (
        "I cannot run that request because it violates the SQL safety rules. "
        f"Reason: {blocked_reason}"
    )
