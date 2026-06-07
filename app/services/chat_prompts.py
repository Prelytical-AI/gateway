from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

ROUTER_SYSTEM = """You route messages for Prelytical, an on-prem read-only SQL analytics assistant.

Return ONLY valid JSON (no markdown):
{
  "action": "brief" | "investigate" | "ask" | "reply",
  "reasoning": "one short sentence",
  "task": "the substantive task to execute (rewrite clearly)",
  "opportunity_index": null or integer,
  "brief_title": "optional title if action is brief",
  "brief_objective": "optional objective if action is brief"
}

Action guide:
- brief: executive / data readiness brief from schema metadata only (no row-level proof yet)
- investigate: multi-step deep dive — chase a brief opportunity, explore where data lives, row-level analysis, HTML report
- ask: one straightforward SQL question with a direct answer
- reply: meta questions, clarifications, greetings — no SQL execution

Use conversation context. Examples:
- "generate the executive brief" -> brief
- "look at item 2 from the brief and actually run it" -> investigate, opportunity_index=2
- "client asks about churn — find it in the data" -> investigate
- "which region has highest revenue?" -> ask
- "what can you do?" -> reply

Prefer investigate over ask when the user wants exploration, multiple tables, or proof on real data."""


def build_router_prompt(
    *,
    message: str,
    history: List[Dict[str, str]],
    brief_loaded: bool,
    brief_summary: Dict[str, Any],
    database_name: str,
    has_brief_attachment: bool,
) -> tuple[str, str]:
    context = {
        "database": database_name,
        "brief_loaded": brief_loaded,
        "brief": brief_summary if brief_loaded else None,
        "attachment_is_brief": has_brief_attachment,
    }
    hist = json.dumps(history[-10:], indent=2)
    user = f"""Session context:
{json.dumps(context, indent=2)}

Conversation (recent):
{hist}

Latest user message:
{message}

Route this message."""
    return ROUTER_SYSTEM, user


REPLY_SYSTEM = """You are Prelytical, an on-prem analytics assistant connected to a read-only SQL Server.

You can:
- Generate executive data readiness briefs (metadata only)
- Run multi-step investigations on real data with HTML reports
- Answer single business questions with SQL

Be concise and practical. If the user should just ask you to do something ("generate the brief", "look at item 2"), tell them you'll handle it when they say so — don't over-explain UI steps.

Ground answers in the session context provided. Do not invent database objects."""


def build_reply_prompt(
    *,
    message: str,
    history: List[Dict[str, str]],
    brief_summary: Dict[str, Any],
    database_name: str,
) -> tuple[str, str]:
    user = f"""Database: {database_name}
Brief session: {json.dumps(brief_summary, indent=2)}

Recent conversation:
{json.dumps(history[-8:], indent=2)}

User: {message}"""
    return REPLY_SYSTEM, user
