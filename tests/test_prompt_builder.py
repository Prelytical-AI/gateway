from app.services.prompt_builder import (
    SQL_SYSTEM_PROMPT,
    build_blocked_answer,
    build_sql_generation_prompt,
    build_summarization_prompt,
    compact_schema_metadata,
)


def test_compact_schema_metadata_truncates_large_catalogs():
    objects = [{"name": f"t{i}", "type": "TABLE", "columns": []} for i in range(100)]
    metadata = {"schemas": [{"schema": "dbo", "objects": objects}]}
    compact = compact_schema_metadata(metadata, max_objects=10)
    assert len(compact["schemas"][0]["objects"]) == 10
    assert compact["schemas"][0]["truncated"] is True
    assert "truncated" in compact["note"].lower()


def test_sql_generation_prompt_includes_schema_and_question():
    system, user = build_sql_generation_prompt(
        question="Which region has the highest revenue?",
        schema_metadata={"schemas": [{"schema": "ai", "objects": []}]},
        max_rows=200,
    )
    assert "SELECT" in system
    assert "Which region has the highest revenue?" in user
    assert "TOP 200" in user
    assert "ai" in user


def test_summarization_prompt_includes_rows():
    system, user = build_summarization_prompt(
        question="Top region?",
        sql="SELECT TOP 5 region FROM ai.vw_demo_sales_summary",
        columns=["region"],
        rows=[{"region": "Midwest"}],
        row_count=1,
        max_rows=200,
    )
    assert "business analyst" in system.lower()
    assert "Midwest" in user
    assert "Top region?" in user


def test_blocked_answer_message():
    message = build_blocked_answer("Only SELECT statements are allowed.")
    assert "cannot run" in message.lower()
    assert "Only SELECT" in message
