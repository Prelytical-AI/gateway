import pytest

from app.services.guardrails import validate_sql


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


def test_top_appended_to_select_star():
    result = validate_sql("SELECT * FROM ai.vw_demo_sales_summary")
    assert result.valid
    assert result.normalized_sql.upper().startswith("SELECT TOP")
