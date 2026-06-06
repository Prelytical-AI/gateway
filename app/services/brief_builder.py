from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "brief-master-directive.md"

MAX_TABLES_WITH_COLUMNS = 18
MAX_COLUMNS_PER_TABLE = 8
MAX_TABLE_INVENTORY = 60


def load_brief_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise RuntimeError(f"Brief prompt not found: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def schema_metadata_to_artifact(
    schema_metadata: Dict[str, Any],
    *,
    database_name: str,
) -> Dict[str, Any]:
    """Turn live SQL Server schema metadata into platform-style source context."""
    tables: List[Dict[str, Any]] = []
    table_inventory: List[Dict[str, Any]] = []

    for schema in schema_metadata.get("schemas", []):
        schema_name = schema.get("schema", "")
        for obj in schema.get("objects", []):
            obj_name = obj.get("name", "")
            qualified = f"{schema_name}.{obj_name}" if schema_name else obj_name
            columns = obj.get("columns") or []
            table_inventory.append(
                {
                    "name": qualified,
                    "type": obj.get("type", "TABLE"),
                    "column_count": len(columns),
                }
            )
            if len(tables) < MAX_TABLES_WITH_COLUMNS:
                tables.append(
                    {
                        "name": qualified,
                        "type": obj.get("type", "TABLE"),
                        "column_count": len(columns),
                        "columns": [
                            {"name": c.get("name"), "type": c.get("type")}
                            for c in columns[:MAX_COLUMNS_PER_TABLE]
                        ],
                    }
                )

    total_tables = len(table_inventory)
    entities = [
        {
            "name": item["name"],
            "estimated_fields": item["column_count"],
            "grain": "unknown — metadata-only review",
        }
        for item in table_inventory[:40]
    ]

    shape = {
        "shape_summary": {
            "table_count": total_tables,
            "entity_count": len(entities),
            "review_mode": "metadata_only",
            "truncated_for_prompt": total_tables > MAX_TABLES_WITH_COLUMNS,
        },
        "entities": entities,
        "table_inventory": table_inventory[:MAX_TABLE_INVENTORY],
        "tables": tables,
        "joins": [],
        "common_terms": _infer_common_terms(table_inventory),
    }

    return {
        "name": database_name,
        "artifact_type": "schema",
        "context": (
            "Live SQL Server schema metadata from the connected read-only gateway. "
            "No row-level data was reviewed for this brief."
        ),
        "summary": (
            f"Schema review of {database_name} covering {total_tables} table/view(s) "
            f"across allowed schemas."
        ),
        "shape": shape,
        "quality_notes": [
            "Metadata extracted from SQL Server catalog views.",
            "Join paths and grains are inferred from naming unless documented elsewhere.",
        ],
        "sensitivity_flags": [],
    }


def build_brief_prompt(
    *,
    title: str,
    objective: str,
    business_context: Optional[str],
    audience: str,
    schema_metadata: Dict[str, Any],
    database_name: str,
) -> tuple[str, str]:
    artifact = schema_metadata_to_artifact(schema_metadata, database_name=database_name)
    domains: List[Dict[str, Any]] = []
    if business_context and business_context.strip():
        domains.append(
            {
                "name": database_name,
                "business_context": business_context.strip(),
                "goals": [],
                "pain_points": [],
                "key_metrics": [],
                "privacy_notes": "On-premises deployment; data stays in client environment.",
            }
        )

    final_context = {
        "title": title,
        "objective": objective,
        "final_run_context": objective,
        "audience": audience,
        "depth": "executive",
        "constraints": {
            "deployment": "on_premises_sql_gateway",
            "evidence_mode": "schema_metadata_only",
        },
    }

    user_prompt = (
        "Build a Prelytical executive brief from the context layers below.\n"
        "Use FINAL RUN CONTEXT as the highest-priority business instruction, DOMAIN CONTEXT "
        "to interpret business relevance, and SOURCE CONTEXT as the evidence base.\n\n"
        "FINAL RUN CONTEXT JSON:\n"
        f"{_json(final_context)}\n\n"
        "DOMAIN CONTEXT JSON:\n"
        f"{_json(domains)}\n\n"
        "SOURCE CONTEXT JSON:\n"
        f"{_json([artifact])}\n\n"
        "Return only valid JSON matching the Prelytical brief contract. The html_report field "
        "must be a complete standalone HTML document beginning with <!doctype html>, including "
        "its own embedded CSS, and requiring no external stylesheet to look polished."
    )

    return load_brief_system_prompt(), user_prompt


def parse_brief_json(content: str) -> Dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(text[start : end + 1])
        else:
            raise RuntimeError(f"Model did not return valid brief JSON: {text[:500]}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Brief JSON must be an object at the top level.")
    return parsed


def _infer_common_terms(table_inventory: List[Dict[str, Any]]) -> List[str]:
    terms: List[str] = []
    names = " ".join(item.get("name", "") for item in table_inventory).lower()
    for keyword in (
        "order",
        "customer",
        "product",
        "revenue",
        "region",
        "category",
        "sales",
        "invoice",
        "account",
    ):
        if keyword in names and keyword not in terms:
            terms.append(keyword)
    return terms[:12]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), default=str)
