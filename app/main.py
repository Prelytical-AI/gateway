from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.audit import AuditService
from app.services.guardrails import ValidationResult, validate_sql
from app.services.model_client import ModelClient
from app.services.prompt_builder import (
    build_blocked_answer,
    build_sql_generation_prompt,
    build_summarization_prompt,
)
from app.services.sqlserver import SQLServerService

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

audit = AuditService()
sql_service = SQLServerService()
model_client = ModelClient()


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class SqlRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=20000)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def health() -> Dict[str, Any]:
        sql_ok, _ = sql_service.test_connection()
        model_ok, _ = model_client.test_model_connection()
        return {
            "status": "ok",
            "app": settings.app_name,
            "sql_configured": sql_ok,
            "model_configured": model_ok,
        }

    @app.get("/api/config/safe")
    def safe_config() -> Dict[str, Any]:
        return {
            "sql_host": settings.sqlserver_host,
            "sql_database": settings.sqlserver_database,
            "allowed_schemas": settings.allowed_schemas,
            "model_provider": settings.model_provider,
            "model_base_url": settings.model_base_url,
            "model_name": settings.model_name,
            "max_rows": settings.sqlserver_max_rows,
            "model_skip_summarization": settings.model_skip_summarization,
            "model_timeout_seconds": settings.model_timeout_seconds,
        }

    @app.get("/api/schema")
    def get_schema() -> Dict[str, Any]:
        try:
            metadata = sql_service.get_allowed_schema_metadata()
            audit.log_event("schema_loaded", metadata={"schema_count": len(metadata.get("schemas", []))})
            return metadata
        except Exception as exc:
            audit.log_event("error", metadata={"endpoint": "/api/schema", "error": str(exc)})
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/ask")
    def ask(request: AskRequest) -> Dict[str, Any]:
        question = request.question.strip()
        audit.log_event("question_received", question=question, model_name=settings.model_name)

        try:
            schema_metadata = sql_service.get_allowed_schema_metadata()
            audit.log_event("schema_loaded", question=question, metadata={"for": "ask"})

            system_prompt, user_prompt = build_sql_generation_prompt(
                question=question,
                schema_metadata=schema_metadata,
                max_rows=settings.sqlserver_max_rows,
                max_schema_objects=settings.model_max_schema_objects,
            )
            generated_sql = model_client.generate_sql(system_prompt, user_prompt)
            audit.log_event(
                "model_sql_generated",
                question=question,
                generated_sql=generated_sql,
                model_name=settings.model_name,
            )

            validation = validate_sql(generated_sql)
            return _finalize_ask_response(question, generated_sql, validation)

        except Exception as exc:
            logger.exception("Ask flow failed")
            audit.log_event("error", question=question, metadata={"error": str(exc)})
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/sql/validate")
    def validate_sql_endpoint(request: SqlRequest) -> Dict[str, Any]:
        validation = validate_sql(request.sql)
        if validation.valid:
            audit.log_event(
                "sql_validation_passed",
                generated_sql=request.sql,
                normalized_sql=validation.normalized_sql,
                valid=True,
            )
        else:
            audit.log_event(
                "sql_validation_blocked",
                generated_sql=request.sql,
                normalized_sql=validation.normalized_sql,
                valid=False,
                blocked_reason=validation.blocked_reason,
            )
        return validation.to_dict()

    @app.post("/api/sql/execute")
    def execute_sql_endpoint(request: SqlRequest) -> Dict[str, Any]:
        validation = validate_sql(request.sql)
        if not validation.valid:
            audit.log_event(
                "sql_validation_blocked",
                generated_sql=request.sql,
                normalized_sql=validation.normalized_sql,
                valid=False,
                blocked_reason=validation.blocked_reason,
            )
            return {
                **validation.to_dict(),
                "columns": [],
                "rows": [],
                "row_count": 0,
            }

        try:
            result = sql_service.execute_readonly_query(validation.normalized_sql)
            audit.log_event(
                "sql_executed",
                generated_sql=request.sql,
                normalized_sql=validation.normalized_sql,
                valid=True,
                row_count=result["row_count"],
            )
            return {
                **validation.to_dict(),
                **result,
            }
        except Exception as exc:
            audit.log_event(
                "error",
                generated_sql=request.sql,
                normalized_sql=validation.normalized_sql,
                metadata={"error": str(exc)},
            )
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/audit/recent")
    def recent_audit() -> Dict[str, Any]:
        events = audit.recent_events(limit=100)
        return {"events": events}

    @app.get("/")
    def index():
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="UI not found")
        return FileResponse(index_path)

    return app


def _finalize_ask_response(
    question: str,
    generated_sql: str,
    validation: ValidationResult,
) -> Dict[str, Any]:
    base = {
        "question": question,
        "sql": generated_sql,
        "valid": validation.valid,
        "blocked_reason": validation.blocked_reason,
        "row_count": 0,
        "columns": [],
        "rows": [],
        "answer": "",
        "normalized_sql": validation.normalized_sql,
        "warnings": validation.warnings,
    }

    if not validation.valid:
        audit.log_event(
            "sql_validation_blocked",
            question=question,
            generated_sql=generated_sql,
            normalized_sql=validation.normalized_sql,
            valid=False,
            blocked_reason=validation.blocked_reason,
            model_name=settings.model_name,
        )
        base["answer"] = build_blocked_answer(validation.blocked_reason or "Validation failed.")
        return base

    audit.log_event(
        "sql_validation_passed",
        question=question,
        generated_sql=generated_sql,
        normalized_sql=validation.normalized_sql,
        valid=True,
        model_name=settings.model_name,
    )

    try:
        query_result = sql_service.execute_readonly_query(validation.normalized_sql)
    except Exception as exc:
        audit.log_event(
            "error",
            question=question,
            generated_sql=generated_sql,
            normalized_sql=validation.normalized_sql,
            metadata={"stage": "execute", "error": str(exc)},
        )
        base["valid"] = False
        base["blocked_reason"] = f"SQL execution failed: {exc}"
        base["answer"] = build_blocked_answer(base["blocked_reason"])
        return base

    audit.log_event(
        "sql_executed",
        question=question,
        generated_sql=generated_sql,
        normalized_sql=validation.normalized_sql,
        valid=True,
        row_count=query_result["row_count"],
        model_name=settings.model_name,
    )

    summary_system, summary_user = build_summarization_prompt(
        question=question,
        sql=validation.normalized_sql,
        columns=query_result["columns"],
        rows=query_result["rows"],
        row_count=query_result["row_count"],
        max_rows=settings.sqlserver_max_rows,
        truncated=bool(query_result.get("truncated")),
    )

    if settings.model_skip_summarization:
        answer = (
            f"Query returned {query_result['row_count']} row(s). "
            "Summarization is disabled (MODEL_SKIP_SUMMARIZATION=true) — see the table below."
        )
        audit.log_event(
            "model_summary_skipped",
            question=question,
            generated_sql=generated_sql,
            normalized_sql=validation.normalized_sql,
            valid=True,
            row_count=query_result["row_count"],
            model_name=settings.model_name,
        )
    else:
        try:
            answer = model_client.summarize_results(summary_system, summary_user)
            audit.log_event(
                "model_summary_generated",
                question=question,
                generated_sql=generated_sql,
                normalized_sql=validation.normalized_sql,
                valid=True,
                row_count=query_result["row_count"],
                model_name=settings.model_name,
            )
        except Exception as exc:
            logger.exception("Summary generation failed")
            audit.log_event(
                "error",
                question=question,
                metadata={"stage": "summary", "error": str(exc)},
            )
            answer = (
                "Query executed successfully, but summarization failed. "
                f"Returned {query_result['row_count']} rows — see the table below."
            )

    base.update(
        {
            "sql": validation.normalized_sql,
            "row_count": query_result["row_count"],
            "columns": query_result["columns"],
            "rows": query_result["rows"],
            "answer": answer,
        }
    )
    return base


app = create_app()
