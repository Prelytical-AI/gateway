from app.services.brief_builder import parse_brief_json, schema_metadata_to_artifact


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


def test_parse_brief_json_strips_fences():
    raw = '```json\n{"executive_summary":"Hello","html_report":"<!doctype html>"}\n```'
    parsed = parse_brief_json(raw)
    assert parsed["executive_summary"] == "Hello"
