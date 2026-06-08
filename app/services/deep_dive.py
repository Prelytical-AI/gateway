from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from app.core.config import Settings, settings as default_settings
from app.services.audit import AuditService
from app.services.brief_session import BriefSessionStore
from app.services.deep_dive_renderer import render_investigation_html
from app.services.guardrails import validate_sql
from app.services.investigation_prompts import (
    build_investigation_sql_prompt,
    build_next_query_prompt,
    build_plan_prompt,
    build_synthesis_prompt,
)
from app.services.model_client import ModelClient
from app.services.sqlserver import SQLServerService

logger = logging.getLogger(__name__)

OPPORTUNITY_PATTERNS = [
    re.compile(r"\b(?:item|opportunity|opp|#)\s*(\d+)\b", re.IGNORECASE),
    re.compile(r"\bnumber\s+(\d+)\s+(?:from|in|of)\s+the\s+brief\b", re.IGNORECASE),
    re.compile(r"\bbrief\s+(?:item|opportunity)\s*#?\s*(\d+)\b", re.IGNORECASE),
    re.compile(r"\blook\s+at\s+(?:item\s+)?(\d+)\b", re.IGNORECASE),
]


class InvestigationService:
    def __init__(
        self,
        *,
        sql_service: Optional[SQLServerService] = None,
        model_client: Optional[ModelClient] = None,
        audit: Optional[AuditService] = None,
        brief_session: Optional[BriefSessionStore] = None,
        config: Optional[Settings] = None,
    ) -> None:
        self.config = config or default_settings
        self.sql_service = sql_service or SQLServerService()
        self.model_client = model_client or ModelClient(self.config)
        self.audit = audit or AuditService()
        self.brief_session = brief_session

    def run(
        self,
        *,
        question: str,
        opportunity_index: Optional[int] = None,
        brief_session: BriefSessionStore,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        gen = self.run_events(
            question=question,
            opportunity_index=opportunity_index,
            brief_session=brief_session,
        )
        result: Optional[Dict[str, Any]] = None
        while True:
            try:
                event = next(gen)
                if on_progress and event.get("type") == "progress":
                    on_progress(event.get("message", ""))
            except StopIteration as stopped:
                result = stopped.value
                break
        if result is None:
            raise RuntimeError("Investigation did not return a result.")
        return result

    def run_events(
        self,
        *,
        question: str,
        opportunity_index: Optional[int] = None,
        brief_session: BriefSessionStore,
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        def progress(msg: str) -> Dict[str, Any]:
            return {"type": "progress", "message": msg}

        question = question.strip()
        if not question:
            raise ValueError("Question is required.")

        yield progress("Starting investigation…")
        mode, opp_index = self._resolve_mode(question, opportunity_index, brief_session)
        opportunity: Optional[Dict[str, Any]] = None
        brief_ctx = brief_session.get_context() if brief_session.is_loaded() else {}
        brief_title = brief_ctx.get("title") or ""

        if mode == "opportunity":
            opportunity = brief_session.get_opportunity(opp_index)
            audit_question = f"[opportunity {opp_index}] {question}"
        else:
            audit_question = question

        self.audit.log_event(
            "investigation_started",
            question=audit_question,
            metadata={"mode": mode, "opportunity_index": opp_index},
        )

        schema_metadata = self.sql_service.get_allowed_schema_metadata()
        yield progress("Planning investigation queries…")
        plan = self._create_plan(
            question=question,
            mode=mode,
            opportunity=opportunity,
            brief_title=brief_title,
            schema_metadata=schema_metadata,
        )

        steps: List[Dict[str, Any]] = []
        planned_queries = plan.get("queries") or []
        max_queries = min(
            self.config.deep_dive_max_queries,
            int(plan.get("stop_after_queries") or self.config.deep_dive_max_queries),
        )

        for i, planned in enumerate(planned_queries[:max_queries]):
            purpose = planned.get("purpose") or f"Query {i + 1}"
            yield progress(f"Running query {i + 1} of {max_queries}: {purpose}")
            step = self._run_planned_query(planned, schema_metadata, steps)
            steps.append(step)
            if step.get("error") and i == 0:
                break

        while len(steps) < max_queries and self._should_continue(question, schema_metadata, steps):
            yield progress("Planning follow-up query…")
            next_spec = self._plan_next_query(question, schema_metadata, steps)
            if not next_spec.get("continue"):
                break
            planned = {
                "purpose": next_spec.get("purpose") or "Follow-up query",
                "question_for_sql": next_spec.get("question_for_sql") or question,
            }
            yield progress(f"Running follow-up: {planned['purpose']}")
            step = self._run_planned_query(planned, schema_metadata, steps)
            steps.append(step)
            if next_spec.get("is_final"):
                break

        yield progress("Synthesizing findings…")
        synthesis = self._synthesize(
            question=question,
            mode=mode,
            opportunity=opportunity,
            steps=steps,
        )

        report_title = synthesis.get("title") or plan.get("investigation_title") or "Data Investigation"
        yield progress("Building HTML report…")
        html_report = render_investigation_html(
            title=report_title,
            database_name=self.config.sqlserver_database,
            user_question=question,
            mode=mode,
            synthesis=synthesis,
            steps=steps,
            brief_title=brief_title,
            opportunity=opportunity,
        )

        self.audit.log_event(
            "investigation_completed",
            question=audit_question,
            metadata={
                "mode": mode,
                "step_count": len(steps),
                "successful_steps": sum(1 for s in steps if not s.get("error")),
            },
        )

        return {
            "mode": mode,
            "opportunity_index": opp_index if mode == "opportunity" else None,
            "question": question,
            "title": report_title,
            "approach_summary": plan.get("approach_summary", ""),
            "executive_summary": synthesis.get("executive_summary", ""),
            "key_findings": synthesis.get("key_findings", []),
            "steps": steps,
            "html_report": html_report,
            "query_count": len(steps),
        }

    def _resolve_mode(
        self,
        question: str,
        opportunity_index: Optional[int],
        brief_session: BriefSessionStore,
    ) -> Tuple[str, int]:
        if opportunity_index is not None:
            if not brief_session.is_loaded():
                raise ValueError("No brief loaded. Generate or import a brief first.")
            return "opportunity", opportunity_index

        if brief_session.is_loaded():
            for pattern in OPPORTUNITY_PATTERNS:
                match = pattern.search(question)
                if match:
                    return "opportunity", int(match.group(1))

        return "explore", 0

    def _create_plan(
        self,
        *,
        question: str,
        mode: str,
        opportunity: Optional[Dict[str, Any]],
        brief_title: str,
        schema_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        system, user = build_plan_prompt(
            user_question=question,
            mode=mode,
            opportunity=opportunity,
            brief_title=brief_title,
            schema_metadata=schema_metadata,
            max_schema_objects=self.config.model_max_schema_objects,
        )
        raw = self.model_client.chat(
            system=system,
            user=user,
            temperature=0.2,
            timeout_seconds=self.config.deep_dive_timeout_seconds,
        )
        plan = extract_json_object(raw)
        if not plan.get("queries"):
            plan["queries"] = [
                {
                    "purpose": "Initial landscape scan",
                    "question_for_sql": question,
                }
            ]
        return plan

    def _plan_next_query(
        self,
        question: str,
        schema_metadata: Dict[str, Any],
        steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if len(steps) >= self.config.deep_dive_max_queries:
            return {"continue": False, "reason": "Max queries reached"}
        system, user = build_next_query_prompt(
            user_question=question,
            steps=steps,
            schema_metadata=schema_metadata,
            max_schema_objects=self.config.model_max_schema_objects,
        )
        raw = self.model_client.chat(system=system, user=user, temperature=0.1)
        return extract_json_object(raw)

    def _should_continue(
        self,
        question: str,
        schema_metadata: Dict[str, Any],
        steps: List[Dict[str, Any]],
    ) -> bool:
        if len(steps) >= self.config.deep_dive_max_queries:
            return False
        if not steps:
            return True
        last = steps[-1]
        if last.get("error"):
            return len(steps) < 2
        if last.get("row_count", 0) == 0 and len(steps) < self.config.deep_dive_max_queries:
            return True
        return len(steps) < max(2, self.config.deep_dive_max_queries - 1)

    def _run_planned_query(
        self,
        planned: Dict[str, Any],
        schema_metadata: Dict[str, Any],
        prior_steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        purpose = planned.get("purpose") or "Query"
        question_for_sql = planned.get("question_for_sql") or purpose
        last_error: Optional[str] = None

        for attempt in range(2):
            system, user = build_investigation_sql_prompt(
                question_for_sql=question_for_sql,
                schema_metadata=schema_metadata,
                max_rows=self.config.sqlserver_max_rows,
                max_schema_objects=self.config.model_max_schema_objects,
                prior_steps=prior_steps,
            )
            if last_error:
                user += (
                    f"\n\nPrevious SQL failed validation or execution:\n{last_error}\n"
                    "Fix the query. Use schema-qualified table names (dbo.Table, ai.view)."
                )
            generated = self.model_client.generate_sql(system, user)
            validation = validate_sql(generated)

            step: Dict[str, Any] = {
                "purpose": purpose,
                "question_for_sql": question_for_sql,
                "sql": validation.normalized_sql or generated,
                "valid": validation.valid,
                "row_count": 0,
                "columns": [],
                "rows": [],
            }

            if not validation.valid:
                last_error = validation.blocked_reason or "SQL validation failed"
                step["error"] = last_error
                if attempt == 0:
                    continue
                self.audit.log_event(
                    "sql_validation_blocked",
                    generated_sql=generated,
                    blocked_reason=step["error"],
                    metadata={"investigation_step": purpose},
                )
                return step

            try:
                result = self.sql_service.execute_readonly_query(validation.normalized_sql)
                step.update(
                    {
                        "sql": validation.normalized_sql,
                        "row_count": result["row_count"],
                        "columns": result["columns"],
                        "rows": result["rows"],
                        "truncated": result.get("truncated", False),
                    }
                )
                self.audit.log_event(
                    "sql_executed",
                    generated_sql=validation.normalized_sql,
                    row_count=result["row_count"],
                    metadata={"investigation_step": purpose},
                )
                return step
            except Exception as exc:
                logger.exception("Investigation query failed")
                last_error = str(exc)
                step["error"] = last_error
                if attempt == 0:
                    continue
                self.audit.log_event(
                    "error",
                    generated_sql=validation.normalized_sql,
                    metadata={"investigation_step": purpose, "error": str(exc)},
                )
                return step

        return step

    def _synthesize(
        self,
        *,
        question: str,
        mode: str,
        opportunity: Optional[Dict[str, Any]],
        steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        system, user = build_synthesis_prompt(
            user_question=question,
            mode=mode,
            opportunity=opportunity,
            steps=steps,
        )
        raw = self.model_client.chat(
            system=system,
            user=user,
            temperature=0.2,
            timeout_seconds=self.config.deep_dive_timeout_seconds,
        )
        synthesis = extract_json_object(raw)
        ok_steps = [s for s in steps if not s.get("error")]
        if not ok_steps:
            errors = [s.get("error") for s in steps if s.get("error")]
            synthesis = {
                "title": synthesis.get("title") or "Investigation — queries did not return data",
                "executive_summary": (
                    "No query returned data. All investigation steps failed — see errors below. "
                    "Do not treat any narrative above as validated findings."
                ),
                "key_findings": [f"Query failed: {e}" for e in errors[:5]],
                "tables_used": synthesis.get("tables_used") or [],
                "indicators_validated": [],
                "caveats": ["Investigation could not validate brief indicators against live data."],
                "recommended_next_steps": [
                    "Retry after guardrail/SQL fix, or simplify to a single-table aggregate query.",
                ],
            }
        elif not synthesis.get("executive_summary"):
            synthesis["executive_summary"] = (
                f"Completed {len(ok_steps)} of {len(steps)} planned queries against "
                f"{self.config.sqlserver_database}."
            )
        return synthesis


def extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {}
