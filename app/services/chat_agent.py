from __future__ import annotations

import logging
import re
from typing import Any, Dict, Generator, List, Optional

from app.core.config import Settings, settings as default_settings
from app.services.audit import AuditService
from app.services.brief_builder import build_brief_prompt, parse_brief_json
from app.services.brief_export import export_brief_html
from app.services.brief_renderer import normalize_and_render_brief
from app.services.brief_session import BriefSessionStore
from app.services.chat_prompts import build_reply_prompt, build_router_prompt
from app.services.chat_store import ChatStore
from app.services.deep_dive import InvestigationService, extract_json_object
from app.services.guardrails import validate_sql
from app.services.model_client import ModelClient
from app.services.prompt_builder import (
    build_blocked_answer,
    build_sql_generation_prompt,
    build_summarization_prompt,
)
from app.services.sqlserver import SQLServerService

logger = logging.getLogger(__name__)

ProgressEvent = Dict[str, Any]
ChatEvent = Dict[str, Any]

BRIEF_HINTS = re.compile(
    r"\b(executive brief|data readiness|readiness brief|generate.{0,20}brief|metadata.{0,20}brief)\b",
    re.IGNORECASE,
)
INVESTIGATE_HINTS = re.compile(
    r"\b(deep dive|investigat|look at item|item \d|opportunity \d|from the brief|"
    r"find where|data landscape|row.?level|actually (do|run)|prove it|explore)\b",
    re.IGNORECASE,
)

ACTION_LABELS = {
    "brief": "executive brief generation",
    "investigate": "multi-step investigation",
    "ask": "SQL query",
    "reply": "conversation",
    "import": "brief import",
}


class ChatAgent:
    def __init__(
        self,
        *,
        chat_store: ChatStore,
        brief_session: BriefSessionStore,
        sql_service: Optional[SQLServerService] = None,
        model_client: Optional[ModelClient] = None,
        investigation_service: Optional[InvestigationService] = None,
        audit: Optional[AuditService] = None,
        config: Optional[Settings] = None,
    ) -> None:
        self.config = config or default_settings
        self.chat_store = chat_store
        self.brief_session = brief_session
        self.sql_service = sql_service or SQLServerService()
        self.model_client = model_client or ModelClient(self.config)
        self.investigation_service = investigation_service or InvestigationService(
            sql_service=self.sql_service,
            model_client=self.model_client,
            audit=audit or AuditService(),
        )
        self.audit = audit or AuditService()

    def handle_message(
        self,
        message: str,
        attachments: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        result: Optional[Dict[str, Any]] = None
        for event in self.handle_message_events(message, attachments):
            if event.get("type") == "result":
                result = event["data"]
        if result is None:
            raise RuntimeError("Chat handler did not produce a result.")
        return result

    def handle_message_events(
        self,
        message: str,
        attachments: Optional[List[Dict[str, str]]] = None,
    ) -> Generator[ChatEvent, None, None]:
        message = (message or "").strip()
        attachments = attachments or []

        if not message and not attachments:
            raise ValueError("Send a message or attach a file.")

        yield _progress("Saving your message…")
        user_msg = self.chat_store.add_user_message(
            message or "(file attached)",
            attachments=[{"filename": a.get("filename", "file")} for a in attachments],
        )

        import_note = ""
        if attachments:
            yield _progress("Checking attachments…")
            import_note = self._import_attachments(attachments)

        brief_summary = self.brief_session.summary()

        yield _progress("Figuring out what to do…")
        route = self._route(message or "Use the attached brief.", brief_summary, attachments)
        action = route.get("action", "reply")
        task = (route.get("task") or message or "").strip()
        yield _progress(f"Running: {ACTION_LABELS.get(action, action)}")

        if import_note and action == "reply" and not message:
            assistant = self.chat_store.add_assistant_message(import_note, action="import")
            yield _result(self._response(user_msg, assistant))
            return

        try:
            if action == "brief":
                assistant = yield from self._run_brief_events(task, route)
            elif action == "investigate":
                assistant = yield from self._run_investigate_events(task, route)
            elif action == "ask":
                assistant = yield from self._run_ask_events(task)
            else:
                assistant = yield from self._run_reply_events(message, brief_summary)
        except Exception as exc:
            logger.exception("Chat action failed")
            assistant = self.chat_store.add_assistant_message(
                f"Something went wrong: {exc}",
                action="error",
            )
            yield _result(self._response(user_msg, assistant))
            return

        if import_note:
            merged = f"{import_note}\n\n{assistant['content']}" if assistant.get("content") else import_note
            self.chat_store.update_message(assistant["id"], content=merged)
            assistant["content"] = merged

        yield _result(self._response(user_msg, assistant))

    def _import_attachments(self, attachments: List[Dict[str, str]]) -> str:
        notes: List[str] = []
        for att in attachments:
            filename = att.get("filename", "")
            content = att.get("content", "")
            if not content or not _is_brief_content(filename, content):
                continue
            is_json = filename.lower().endswith(".json") or content.lstrip().startswith("{")
            self.brief_session.import_content(
                html=None if is_json else content,
                json_text=content if is_json else None,
                title=filename.rsplit(".", 1)[0] if filename else None,
                database_name=self.config.sqlserver_database,
            )
            summary = self.brief_session.summary()
            notes.append(
                f"Loaded brief \"{summary.get('title')}\" with "
                f"{summary.get('opportunity_count', 0)} opportunities."
            )
            self.audit.log_event(
                "brief_imported",
                metadata={"source": "chat_attachment", "filename": filename},
            )
        return "\n".join(notes)

    def _route(
        self,
        message: str,
        brief_summary: Dict[str, Any],
        attachments: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        has_brief_att = any(
            _is_brief_content(a.get("filename", ""), a.get("content", "")) for a in attachments
        )
        history = self.chat_store.recent_for_model()

        try:
            system, user = build_router_prompt(
                message=message,
                history=history,
                brief_loaded=brief_summary.get("loaded", False),
                brief_summary=brief_summary,
                database_name=self.config.sqlserver_database,
                has_brief_attachment=has_brief_att,
            )
            raw = self.model_client.chat(system=system, user=user, temperature=0.0)
            route = extract_json_object(raw)
            if route.get("action"):
                return route
        except Exception:
            logger.exception("Model routing failed, using heuristics")

        return _heuristic_route(message, brief_summary.get("loaded", False), has_brief_att)

    def _run_brief_events(
        self,
        task: str,
        route: Dict[str, Any],
    ) -> Generator[ChatEvent, None, Dict[str, Any]]:
        yield _progress("Loading schema metadata…")
        title = route.get("brief_title") or "Executive Data Readiness Brief"
        objective = route.get("brief_objective") or task or (
            "Assess what this database is well positioned to answer for executives."
        )
        schema_metadata = self.sql_service.get_allowed_schema_metadata()
        system_prompt, user_prompt = build_brief_prompt(
            title=title,
            objective=objective,
            business_context=None,
            audience="Executives and analytics leaders",
            schema_metadata=schema_metadata,
            database_name=self.config.sqlserver_database,
        )
        yield _progress("Generating executive brief (may take several minutes on CPU)…")
        raw = self.model_client.generate_brief(system_prompt, user_prompt)
        yield _progress("Parsing and rendering HTML report…")
        parsed = parse_brief_json(raw)
        output = normalize_and_render_brief(
            parsed,
            title=title,
            objective=objective,
            database_name=self.config.sqlserver_database,
            schema_metadata=schema_metadata,
        )
        export_path, export_error = export_brief_html(
            output.get("html_report", ""),
            export_dir=self.config.brief_export_path,
            title=title,
            database_name=self.config.sqlserver_database,
        )
        yield _progress("Saving brief to session…")
        self.brief_session.set_from_generation(
            title=title,
            output=output,
            html_report=output.get("html_report", ""),
            database_name=self.config.sqlserver_database,
        )
        self.audit.log_event("brief_generated", question=objective, metadata={"via": "chat"})

        summary = output.get("executive_summary", "")
        content = (
            f"Executive brief ready. Readiness {output.get('readiness_score')}, "
            f"confidence {output.get('confidence_score')}.\n\n{summary}"
        )
        if export_path:
            content += f"\n\nSaved to: {export_path}"
        elif export_error:
            content += f"\n\nExport note: {export_error}"

        return self.chat_store.add_assistant_message(
            content,
            action="brief",
            artifact={
                "type": "html_report",
                "html_report": output.get("html_report", ""),
                "download_name": "prelytical-executive-brief.html",
                "readiness_score": output.get("readiness_score"),
                "confidence_score": output.get("confidence_score"),
            },
        )

    def _run_investigate_events(
        self,
        task: str,
        route: Dict[str, Any],
    ) -> Generator[ChatEvent, None, Dict[str, Any]]:
        opp_index = route.get("opportunity_index")
        if isinstance(opp_index, float):
            opp_index = int(opp_index)
        if opp_index is not None and not isinstance(opp_index, int):
            opp_index = None

        gen = self.investigation_service.run_events(
            question=task,
            opportunity_index=opp_index,
            brief_session=self.brief_session,
        )
        result: Optional[Dict[str, Any]] = None
        while True:
            try:
                event = next(gen)
                if event.get("type") == "progress":
                    yield event
            except StopIteration as stopped:
                result = stopped.value
                break

        if result is None:
            raise RuntimeError("Investigation did not return a result.")

        findings = result.get("key_findings") or []
        findings_text = "\n".join(f"- {f}" for f in findings[:6])
        content = result.get("executive_summary") or "Investigation complete."
        if findings_text:
            content += f"\n\nKey findings:\n{findings_text}"
        content += f"\n\n({result.get('query_count', 0)} queries executed)"

        return self.chat_store.add_assistant_message(
            content,
            action="investigate",
            artifact={
                "type": "html_report",
                "html_report": result.get("html_report", ""),
                "download_name": "prelytical-investigation-report.html",
                "mode": result.get("mode"),
                "query_count": result.get("query_count"),
                "steps": result.get("steps"),
            },
        )

    def _run_ask_events(self, task: str) -> Generator[ChatEvent, None, Dict[str, Any]]:
        yield _progress("Loading schema…")
        schema_metadata = self.sql_service.get_allowed_schema_metadata()
        system_prompt, user_prompt = build_sql_generation_prompt(
            question=task,
            schema_metadata=schema_metadata,
            max_rows=self.config.sqlserver_max_rows,
            max_schema_objects=self.config.model_max_schema_objects,
        )
        yield _progress("Generating SQL…")
        generated_sql = self.model_client.generate_sql(system_prompt, user_prompt)
        validation = validate_sql(generated_sql)

        if not validation.valid:
            content = build_blocked_answer(validation.blocked_reason or "Validation failed.")
            return self.chat_store.add_assistant_message(
                content,
                action="ask",
                artifact={"type": "sql", "sql": generated_sql, "valid": False},
            )

        yield _progress("Running query…")
        query_result = self.sql_service.execute_readonly_query(validation.normalized_sql)
        if self.config.model_skip_summarization:
            answer = f"Query returned {query_result['row_count']} row(s)."
        else:
            yield _progress("Summarizing results…")
            summary_system, summary_user = build_summarization_prompt(
                question=task,
                sql=validation.normalized_sql,
                columns=query_result["columns"],
                rows=query_result["rows"],
                row_count=query_result["row_count"],
                max_rows=self.config.sqlserver_max_rows,
                truncated=bool(query_result.get("truncated")),
            )
            answer = self.model_client.summarize_results(summary_system, summary_user)

        return self.chat_store.add_assistant_message(
            answer,
            action="ask",
            artifact={
                "type": "table",
                "sql": validation.normalized_sql,
                "valid": True,
                "columns": query_result["columns"],
                "rows": query_result["rows"],
                "row_count": query_result["row_count"],
            },
        )

    def _run_reply_events(
        self,
        message: str,
        brief_summary: Dict[str, Any],
    ) -> Generator[ChatEvent, None, Dict[str, Any]]:
        yield _progress("Thinking…")
        history = self.chat_store.recent_for_model()
        system, user = build_reply_prompt(
            message=message,
            history=history,
            brief_summary=brief_summary,
            database_name=self.config.sqlserver_database,
        )
        content = self.model_client.chat(system=system, user=user, temperature=0.3)
        return self.chat_store.add_assistant_message(content, action="reply")

    @staticmethod
    def _response(user_msg: Dict[str, Any], assistant_msg: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "messages": [user_msg, assistant_msg],
        }


def _progress(message: str) -> ProgressEvent:
    return {"type": "progress", "message": message}


def _result(data: Dict[str, Any]) -> ChatEvent:
    return {"type": "result", "data": data}


def _is_brief_content(filename: str, content: str) -> bool:
    name = filename.lower()
    if name.endswith((".html", ".htm", ".json")):
        return True
    start = content.lstrip()[:200].lower()
    return start.startswith("{") or "<html" in start or "prelytical" in start and "opportunity" in start


def _heuristic_route(message: str, brief_loaded: bool, has_brief_attachment: bool) -> Dict[str, Any]:
    text = message.strip()
    opp_match = re.search(r"\b(?:item|opportunity|#)\s*(\d+)\b", text, re.IGNORECASE)
    opp_index = int(opp_match.group(1)) if opp_match else None

    if BRIEF_HINTS.search(text):
        return {"action": "brief", "task": text, "brief_objective": text}

    if has_brief_attachment and not text:
        return {"action": "reply", "task": text}

    if INVESTIGATE_HINTS.search(text) or (opp_index and brief_loaded):
        return {"action": "investigate", "task": text, "opportunity_index": opp_index}

    if text.endswith("?") and len(text) < 200:
        return {"action": "ask", "task": text}

    if brief_loaded and opp_index:
        return {"action": "investigate", "task": text, "opportunity_index": opp_index}

    return {"action": "reply", "task": text}
