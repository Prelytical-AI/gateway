from app.core.config import Settings
from app.services.brief_builder import parse_brief_json, schema_metadata_to_artifact


def _sample_metadata(table_count: int) -> dict:
    objects = [
        {
            "name": f"Table{i}",
            "type": "TABLE",
            "columns": [{"name": f"Col{j}", "type": "int", "nullable": False} for j in range(5)],
        }
        for i in range(table_count)
    ]
    return {"schemas": [{"schema": "dbo", "objects": objects}]}


def test_schema_metadata_to_artifact_builds_shape():
    metadata = {
        "schemas": [
            {
                "schema": "dbo",
                "objects": [
                    {
                        "name": "Orders",
                        "type": "TABLE",
                        "columns": [{"name": "OrderId", "type": "int", "nullable": False}],
                    }
                ],
            }
        ]
    }
    artifact = schema_metadata_to_artifact(metadata, database_name="DemoDB")
    assert artifact["artifact_type"] == "schema"
    assert artifact["shape"]["shape_summary"]["table_count"] == 1
    assert artifact["shape"]["tables"][0]["name"] == "dbo.Orders"


def test_schema_metadata_to_artifact_respects_env_limits():
    metadata = _sample_metadata(5)
    cfg = Settings.model_construct(
        brief_max_tables_with_columns=2,
        brief_max_columns_per_table=1,
        brief_max_table_inventory=3,
        brief_max_entities=2,
    )
    artifact = schema_metadata_to_artifact(metadata, database_name="DemoDB", config=cfg)
    shape = artifact["shape"]
    assert len(shape["tables"]) == 2
    assert len(shape["tables"][0]["columns"]) == 1
    assert len(shape["table_inventory"]) == 3
    assert len(shape["entities"]) == 2
    assert shape["shape_summary"]["truncated_for_prompt"] is True


def test_parse_brief_json_strips_fences():
    raw = '```json\n{"executive_summary":"Hello","html_report":"<!doctype html>"}\n```'
    parsed = parse_brief_json(raw)
    assert parsed["executive_summary"] == "Hello"
