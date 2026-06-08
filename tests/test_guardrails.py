import pytest

from app.core.config import Settings
from app.services.guardrails import validate_sql

DBO_ALLOWED = Settings.model_construct(
    sqlserver_allowed_schemas="ai,dbo",
    sqlserver_blocked_schemas="sys,INFORMATION_SCHEMA",
)


@pytest.mark.parametrize(
    "sql,expect_valid,reason_fragment",
    [
        ("SELECT TOP 10 * FROM ai.vw_sales_summary", True, None),
        ("SELECT * FROM ai.vw_sales_summary", True, None),
        ("DELETE FROM ai.vw_sales_summary", False, "SELECT"),
        ("DROP TABLE dbo.Customers", False, None),
        ("SELECT * FROM dbo.Customers", False, "Schema 'dbo'"),
        ("SELECT SSN FROM ai.vw_customer_detail", False, "ssn"),
        ("EXEC xp_cmdshell 'dir'", False, None),
        ("SELECT * FROM OtherDb.ai.vw_sales_summary", False, "Cross-database"),
        (
            "SELECT * FROM ai.vw_sales_summary; SELECT * FROM ai.vw_other",
            False,
            "single SQL statement",
        ),
    ],
)
def test_guardrails(sql, expect_valid, reason_fragment):
    result = validate_sql(sql)
    assert result.valid is expect_valid
    if expect_valid and sql.strip().upper().startswith("SELECT *"):
        assert "TOP" in result.normalized_sql.upper()
    if reason_fragment:
        assert result.blocked_reason and reason_fragment.lower() in result.blocked_reason.lower()


def test_table_aliases_not_treated_as_schemas():
    sql = (
        "SELECT TOP 10 o.customer_id, SUM(o.revenue) AS total "
        "FROM dbo.Orders o GROUP BY o.customer_id ORDER BY total DESC"
    )
    result = validate_sql(sql, DBO_ALLOWED)
    assert result.valid, result.blocked_reason


def test_join_aliases_not_treated_as_schemas():
    sql = (
        "SELECT TOP 10 c.name, COUNT(o.id) AS orders "
        "FROM dbo.Customers c JOIN dbo.Orders o ON c.id = o.customer_id "
        "GROUP BY c.name"
    )
    result = validate_sql(sql, DBO_ALLOWED)
    assert result.valid, result.blocked_reason


def test_ai_view_alias():
    sql = (
        "SELECT TOP 5 v.region, SUM(v.revenue) AS total "
        "FROM ai.vw_sales_by_region v GROUP BY v.region"
    )
    result = validate_sql(sql)
    assert result.valid, result.blocked_reason


def test_top_appended_to_select_star():
    result = validate_sql("SELECT * FROM ai.vw_demo_sales_summary")
    assert result.valid
    assert result.normalized_sql.upper().startswith("SELECT TOP")
