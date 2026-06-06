from app.services.brief_renderer import normalize_and_render_brief, render_standalone_html_report


def test_render_includes_styling_and_scores():
    output = normalize_and_render_brief(
        {
            "executive_summary": "Demo database supports sales analytics.",
            "top_signal_opportunities": [
                {
                    "title": "Revenue by region",
                    "description": "Compare regional performance.",
                    "business_value": "High",
                    "feasibility": "High",
                    "privacy_risk": "Low",
                    "example_insights": ["Which region has the highest revenue?"],
                    "indicators": ["region_name", "revenue"],
                }
            ],
        },
        title="Test Brief",
        objective="Assess readiness",
        database_name="PrelyticalDemoDW",
        schema_metadata={
            "schemas": [
                {
                    "schema": "ai",
                    "objects": [{"name": "vw_sales_by_region", "type": "VIEW", "columns": []}],
                }
            ]
        },
    )
    html = output["html_report"]
    assert "prelytical-report-document" in html
    assert "<style>" in html
    assert "Readiness" in html
    assert "Example insights" in html or "example insights" in html.lower()
    assert output.get("readiness_score", 0) > 0


def test_inferred_opportunities_from_schema():
    output = normalize_and_render_brief(
        {"executive_summary": "Summary only."},
        title="Brief",
        objective="Objective",
        database_name="Demo",
        schema_metadata={
            "schemas": [
                {
                    "schema": "dbo",
                    "objects": [
                        {"name": "Orders", "type": "TABLE", "columns": [{"name": "revenue", "type": "money"}]},
                        {"name": "Customers", "type": "TABLE", "columns": []},
                    ],
                },
                {
                    "schema": "ai",
                    "objects": [
                        {"name": "vw_sales_by_region", "type": "VIEW", "columns": []},
                    ],
                },
            ]
        },
    )
    assert len(output["top_signal_opportunities"]) >= 2
    html = render_standalone_html_report(output, title="Brief", database_name="Demo")
    assert "ranked opportunities" in html.lower()
