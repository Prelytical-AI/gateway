from app.services.brief_import import parse_brief_content
from app.services.brief_renderer import normalize_and_render_brief
from app.services.deep_dive_renderer import render_investigation_html
from app.services.deep_dive import extract_json_object


SAMPLE_BRIEF_OUTPUT = {
    "executive_summary": "Demo database supports sales analytics.",
    "top_signal_opportunities": [
        {
            "title": "Revenue by region",
            "description": "Compare regional performance.",
            "indicators": ["region_name", "revenue"],
            "example_insights": ["Which region has the highest revenue?"],
        },
        {
            "title": "Customer concentration",
            "description": "Find top customers by spend.",
            "indicators": ["customer_id", "total_spend"],
            "example_insights": ["Who are the top 10 customers?"],
        },
    ],
}


def test_parse_brief_json():
    import json

    parsed = parse_brief_content(json_text=json.dumps(SAMPLE_BRIEF_OUTPUT))
    assert len(parsed["opportunities"]) == 2
    assert parsed["opportunities"][0]["title"] == "Revenue by region"
    assert "region_name" in parsed["opportunities"][0]["indicators"]


def test_parse_brief_html():
    output = normalize_and_render_brief(
        SAMPLE_BRIEF_OUTPUT,
        title="Test Brief",
        objective="Assess readiness",
        database_name="PrelyticalDemoDW",
        schema_metadata=None,
    )
    html = output["html_report"]
    parsed = parse_brief_content(html=html)
    assert len(parsed["opportunities"]) >= 2
    assert any("Revenue" in (o.get("title") or "") for o in parsed["opportunities"])


def test_render_investigation_html_executive_layout():
    evidence_steps = [
        {
            "purpose": "Regional revenue totals",
            "row_count": 3,
            "columns": ["region", "total"],
            "rows": [
                {"region": "West", "total": 120000},
                {"region": "East", "total": 95000},
                {"region": "Central", "total": 80000},
            ],
        }
    ]
    html = render_investigation_html(
        title="Regional revenue investigation",
        database_name="PrelyticalDemoDW",
        user_question="Look at item 1 from the brief and run it",
        mode="opportunity",
        synthesis={
            "approach_summary": "Compared revenue across regions using aggregated sales data.",
            "executive_summary": "West leads revenue at $120,000.",
            "trends_and_patterns": ["West outperforms other regions by 26%."],
            "business_implications": ["Prioritize West region playbook in underperforming markets."],
            "key_findings": ["West is highest at 120,000"],
            "tables_used": ["ai.vw_demo"],
        },
        evidence_steps=evidence_steps,
        brief_title="Test Brief",
        opportunity=SAMPLE_BRIEF_OUTPUT["top_signal_opportunities"][0],
    )
    assert "prelytical-investigation-report" in html
    assert "bar-fill" in html
    assert "West" in html
    assert "Regional revenue totals" in html
    assert "Trends &amp; patterns" in html
    assert "Business implications" in html
    assert "Investigation steps" not in html
    assert "Step 1:" not in html
    assert "<pre>" not in html


def test_summarize_successful_steps():
    from app.services.investigation_analysis import summarize_successful_steps

    steps = [
        {
            "purpose": "Sales by category",
            "columns": ["category_name", "total_revenue"],
            "rows": [
                {"category_name": "Analytics", "total_revenue": 727500},
                {"category_name": "Reporting", "total_revenue": 313250},
            ],
        }
    ]
    highlights = summarize_successful_steps(steps)
    assert len(highlights) == 1
    assert highlights[0]["purpose"] == "Sales by category"
    assert any("727" in h for h in highlights[0]["highlights"])


def test_extract_json_object_from_fenced_response():
    raw = 'Here is the plan:\n```json\n{"queries": [{"purpose": "test"}]}\n```'
    data = extract_json_object(raw)
    assert data["queries"][0]["purpose"] == "test"
