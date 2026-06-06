from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def normalize_and_render_brief(
    raw: Dict[str, Any],
    *,
    title: str,
    objective: str,
    database_name: str,
    schema_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Normalize model JSON and always produce a polished standalone HTML report."""
    output = normalize_brief_output(
        raw,
        title=title,
        objective=objective,
        database_name=database_name,
        schema_metadata=schema_metadata,
    )
    output["html_report"] = render_standalone_html_report(
        output,
        title=title,
        database_name=database_name,
    )
    return output


def normalize_brief_output(
    raw: Dict[str, Any],
    *,
    title: str,
    objective: str,
    database_name: str,
    schema_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out = dict(raw)
    table_names = _table_names_from_schema(schema_metadata)

    out["executive_summary"] = _text(
        out.get("executive_summary") or out.get("summary") or objective
    )
    out["business_context_interpreted"] = _text(
        out.get("business_context_interpreted") or out.get("business_context") or objective
    )
    out["data_shape_overview"] = _text(
        out.get("data_shape_overview")
        or _default_data_shape_overview(table_names, database_name)
    )
    out["readiness_score"] = _score(out.get("readiness_score"), default=_fallback_readiness(table_names))
    out["confidence_score"] = _score(out.get("confidence_score"), default=max(40, out["readiness_score"] - 5))

    scope = out.get("scope_reviewed") if isinstance(out.get("scope_reviewed"), dict) else {}
    out["scope_reviewed"] = {
        "domains": _as_list(scope.get("domains")) or [database_name],
        "artifacts": _as_list(scope.get("artifacts")) or table_names[:12] or [database_name],
        "notes": _text(scope.get("notes") or "Schema metadata review — no row-level data examined."),
    }

    opportunities = _normalize_opportunities(out)
    if len(opportunities) < 3 and table_names:
        opportunities = _merge_opportunities(opportunities, _infer_opportunities_from_schema(table_names))
    out["top_signal_opportunities"] = opportunities[:8]

    out["ranked_recommendations"] = _as_list(out.get("ranked_recommendations")) or [
        o["title"] for o in out["top_signal_opportunities"]
    ]
    out["privacy_considerations"] = _text(
        out.get("privacy_considerations")
        or "On-premises deployment. Schema-only review; validate PII columns before row-level analysis."
    )
    out["not_ready_analysis"] = _as_list(out.get("not_ready_analysis")) or [
        "Row-level validation not performed in this metadata-only brief.",
        "Join paths and grains should be confirmed with subject-matter experts.",
    ]
    out["deep_dive_prompts"] = _normalize_prompts(out)
    out["recommended_next_steps"] = _as_list(out.get("recommended_next_steps")) or [
        "Review ranked opportunities with business stakeholders.",
        "Run deep-dive prompts in Prelytical Ask (read-only SQL).",
        "Validate privacy exclusions before exposing detail rows.",
    ]
    return out


def render_standalone_html_report(
    output: Dict[str, Any],
    *,
    title: str,
    database_name: str,
) -> str:
    readiness = output.get("readiness_score", 0)
    confidence = output.get("confidence_score", 0)
    generated = datetime.now(timezone.utc).strftime("%B %d, %Y")
    opportunities_html = "".join(
        _render_opportunity(opp, index) for index, opp in enumerate(output.get("top_signal_opportunities", []), 1)
    )
    if not opportunities_html:
        opportunities_html = (
            '<div class="card"><p>No ranked opportunities returned. Add business context and regenerate.</p></div>'
        )

    shape_rows = "".join(
        f"<tr><td>{_esc(a)}</td></tr>" for a in _as_list(output.get("scope_reviewed", {}).get("artifacts"))[:20]
    )
    prompts_html = "".join(_render_prompt(p) for p in output.get("deep_dive_prompts", [])[:6])
    not_ready = "".join(f"<li>{_esc(x)}</li>" for x in output.get("not_ready_analysis", []))
    next_steps = "".join(f"<li>{_esc(x)}</li>" for x in output.get("recommended_next_steps", []))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(title)}</title>
  <style>
    :root {{
      --navy: #0f2744;
      --navy-mid: #16365c;
      --teal: #0d9488;
      --teal-light: #ccfbf1;
      --bg: #eef6fb;
      --card: #ffffff;
      --text: #1e293b;
      --muted: #64748b;
      --high: #067647;
      --med: #b54708;
      --low: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body.prelytical-report-document {{
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: linear-gradient(180deg, #eef6fb 0%, #f8fafc 100%);
      color: var(--text);
      line-height: 1.55;
    }}
    main.page.prelytical-report-page {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .brand {{
      font-weight: 700;
      color: var(--navy);
      letter-spacing: -0.02em;
    }}
    .pill {{
      background: var(--teal-light);
      color: var(--teal);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      padding: 6px 12px;
      border-radius: 999px;
    }}
    .hero {{
      background: linear-gradient(135deg, var(--navy), var(--navy-mid));
      color: #fff;
      border-radius: 24px;
      padding: 32px;
      margin-bottom: 24px;
    }}
    .hero .eyebrow {{
      color: #99f6e4;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin: 0 0 8px;
    }}
    .hero h1 {{ margin: 0 0 12px; font-size: 2rem; line-height: 1.2; }}
    .hero .subtitle {{ margin: 0; color: #c7d6ea; max-width: 720px; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 16px;
      margin-top: 24px;
    }}
    .metric {{
      background: rgba(255,255,255,0.1);
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 16px;
      padding: 16px;
    }}
    .metric span {{ display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: #94a3b8; }}
    .metric strong {{ font-size: 1.75rem; color: #fff; }}
    .section {{ margin-bottom: 24px; }}
    .section h2 {{
      color: var(--navy);
      font-size: 1.15rem;
      margin: 0 0 12px;
      padding-bottom: 8px;
      border-bottom: 2px solid var(--teal-light);
    }}
    .card {{
      background: var(--card);
      border: 1px solid #e2e8f0;
      border-radius: 18px;
      padding: 20px 24px;
      box-shadow: 0 8px 24px rgba(15, 39, 68, 0.06);
      margin-bottom: 16px;
    }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    @media (max-width: 860px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
    table.shape {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    table.shape th, table.shape td {{
      border-bottom: 1px solid #e2e8f0;
      padding: 10px 12px;
      text-align: left;
    }}
    table.shape th {{ color: var(--muted); font-weight: 600; width: 40%; }}
    .opportunity {{
      border-left: 4px solid var(--teal);
      padding-left: 16px;
      margin-bottom: 20px;
    }}
    .opportunity h3 {{ margin: 0 0 8px; color: var(--navy); }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }}
    .badge {{
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 4px 10px;
      border-radius: 999px;
    }}
    .badge-high {{ background: #ecfdf3; color: var(--high); }}
    .badge-med {{ background: #fffaeb; color: var(--med); }}
    .badge-low {{ background: #fef3f2; color: var(--low); }}
    .score-pill {{
      display: inline-block;
      background: var(--navy);
      color: #fff;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 0.85rem;
      margin-left: 6px;
    }}
    ul.compact {{ margin: 8px 0; padding-left: 20px; color: var(--muted); }}
    ul.compact li {{ margin-bottom: 4px; }}
    .callout {{
      background: var(--teal-light);
      border: 1px solid #99f6e4;
      border-radius: 14px;
      padding: 16px 20px;
      margin-top: 12px;
    }}
    .prompt-block {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 14px 16px;
      margin-bottom: 12px;
    }}
    .prompt-block code {{
      display: block;
      margin-top: 8px;
      font-size: 0.82rem;
      white-space: pre-wrap;
      word-break: break-word;
      color: var(--navy-mid);
    }}
    .footer {{
      text-align: center;
      color: var(--muted);
      font-size: 0.85rem;
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px solid #e2e8f0;
    }}
    @media print {{
      body {{ background: #fff; }}
      .hero {{ break-inside: avoid; }}
      .opportunity, .card {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body class="prelytical-report-document">
  <main class="page prelytical-report-page">
    <div class="topbar">
      <div class="brand">Prelytical AI</div>
      <span class="pill">Executive Data Readiness Brief</span>
      <span class="pill">{_esc(database_name)} · {generated}</span>
    </div>

    <header class="hero">
      <p class="eyebrow">Schema-first analysis · metadata only</p>
      <h1>{_esc(title)}</h1>
      <p class="subtitle">{_esc(_text(output.get("executive_summary")))}</p>
      <div class="metrics">
        <div class="metric"><span>Readiness</span><strong>{readiness}%</strong></div>
        <div class="metric"><span>Confidence</span><strong>{confidence}%</strong></div>
        <div class="metric"><span>Sources reviewed</span><strong>{len(_as_list(output.get("scope_reviewed", {}).get("artifacts")))}</strong></div>
        <div class="metric"><span>Opportunities</span><strong>{len(output.get("top_signal_opportunities", []))}</strong></div>
      </div>
    </header>

    <section class="section">
      <h2>Executive snapshot</h2>
      <div class="card">
        <p>{_esc(_text(output.get("business_context_interpreted")))}</p>
        <div class="callout">
          <strong>Privacy posture:</strong> {_esc(_text(output.get("privacy_considerations")))}
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Data shape overview</h2>
      <div class="grid2">
        <div class="card">
          <p>{_esc(_text(output.get("data_shape_overview")))}</p>
        </div>
        <div class="card">
          <table class="shape">
            <thead><tr><th>Table / view reviewed</th></tr></thead>
            <tbody>{shape_rows}</tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>What you are ready to answer — ranked opportunities</h2>
      <div class="card">
        {opportunities_html}
      </div>
    </section>

    <section class="section">
      <h2>Deep dive prompts</h2>
      <div class="card">
        {prompts_html or "<p>No deep-dive prompts generated.</p>"}
      </div>
    </section>

    <section class="section grid2">
      <div class="card">
        <h2 style="margin-top:0;border:none;padding:0;">Not ready yet</h2>
        <ul class="compact">{not_ready}</ul>
      </div>
      <div class="card">
        <h2 style="margin-top:0;border:none;padding:0;">Recommended next steps</h2>
        <ol class="compact">{next_steps}</ol>
      </div>
    </section>

    <p class="footer">Generated by Prelytical Secure SQL Gateway · On-premises · Schema metadata review</p>
  </main>
</body>
</html>"""


def _render_opportunity(opp: Dict[str, Any], index: int) -> str:
    title = _text(opp.get("title")) or f"Opportunity {index}"
    desc = _text(opp.get("description"))
    badges = (
        _badge("Business value", opp.get("business_value"), opp.get("value_score"))
        + _badge("Feasibility", opp.get("feasibility"), opp.get("feasibility_score"))
        + _badge("Privacy risk", opp.get("privacy_risk"), opp.get("privacy_risk_score"), invert=True)
        + f'<span class="badge badge-med">Time: {_esc(_text(opp.get("time_to_insight") or "Medium"))}</span>'
        + f'<span class="badge badge-high">Overall {_score(opp.get("overall_score"), 70)}</span>'
    )
    insights = _as_list(opp.get("example_insights"))
    indicators = _as_list(opp.get("indicators"))
    insights_html = "".join(f"<li>{_esc(x)}</li>" for x in insights) if insights else ""
    indicators_html = "".join(f"<li>{_esc(x)}</li>" for x in indicators) if indicators else ""

    extra = ""
    if insights_html:
        extra += f"<p><strong>Example insights to pursue:</strong></p><ul class=\"compact\">{insights_html}</ul>"
    if indicators_html:
        extra += f"<p><strong>Indicators / fields to use:</strong></p><ul class=\"compact\">{indicators_html}</ul>"

    return f"""
    <div class="opportunity">
      <h3>{index}. {_esc(title)} <span class="score-pill">{_score(opp.get("overall_score"), 70)}</span></h3>
      <p>{_esc(desc)}</p>
      <div class="badges">{badges}</div>
      {extra}
      <p><strong>Why it matters:</strong> {_esc(_text(opp.get("why_it_matters") or desc))}</p>
      <p><strong>Required data:</strong> {_esc(_text(opp.get("required_data") or "See indicators above"))}</p>
      <p><strong>Caveats:</strong> {_esc(_text(opp.get("caveats") or "Metadata-only review — validate with sample queries."))}</p>
      <p><strong>Next step:</strong> {_esc(_text(opp.get("recommended_next_step")))}</p>
    </div>"""


def _render_prompt(prompt: Dict[str, Any]) -> str:
    title = _text(prompt.get("title")) or "Deep dive"
    text = _text(prompt.get("prompt_text") or prompt.get("sql") or "")
    use = _text(prompt.get("intended_use") or "Run in Prelytical Ask")
    return f"""
    <div class="prompt-block">
      <strong>{_esc(title)}</strong> — <span class="small">{_esc(use)}</span>
      <code>{_esc(text)}</code>
    </div>"""


def _normalize_opportunities(out: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = out.get("top_signal_opportunities")
    items: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw, 1):
            if isinstance(item, dict):
                items.append(_normalize_opportunity(item, index))
            elif _text(item):
                items.append(_normalize_opportunity({"title": _text(item)}, index))
    if not items:
        for index, rec in enumerate(_as_list(out.get("ranked_recommendations")), 1):
            items.append(_normalize_opportunity({"title": _text(rec)}, index))
    return items


def _normalize_opportunity(data: Dict[str, Any], index: int) -> Dict[str, Any]:
    title = _text(data.get("title")) or f"Opportunity {index}"
    business_value = _label(data.get("business_value"), "Medium")
    feasibility = _label(data.get("feasibility"), "Medium")
    privacy_risk = _label(data.get("privacy_risk"), "Low")
    value_score = _score(data.get("value_score"), _label_score(business_value))
    feasibility_score = _score(data.get("feasibility_score"), _label_score(feasibility))
    privacy_score = _score(data.get("privacy_risk_score"), 100 - _label_score(privacy_risk))
    overall = _score(data.get("overall_score"), round((value_score + feasibility_score + privacy_score) / 3))

    insights = _as_list(data.get("example_insights"))
    indicators = _as_list(data.get("indicators"))

    return {
        "title": title,
        "description": _text(data.get("description"))
        or f"Schema supports executive analysis paths related to {title.lower()}.",
        "business_value": business_value,
        "feasibility": feasibility,
        "privacy_risk": privacy_risk,
        "time_to_insight": _text(data.get("time_to_insight") or "Medium"),
        "value_score": value_score,
        "feasibility_score": feasibility_score,
        "privacy_risk_score": privacy_score,
        "overall_score": overall,
        "example_insights": insights,
        "indicators": indicators,
        "why_it_matters": _text(data.get("why_it_matters") or data.get("description")),
        "required_data": _text(data.get("required_data")),
        "caveats": _text(data.get("caveats")),
        "recommended_next_step": _text(data.get("recommended_next_step"))
        or "Validate with a read-only query in Prelytical Ask.",
    }


def _infer_opportunities_from_schema(table_names: List[str]) -> List[Dict[str, Any]]:
    templates = [
        (
            lambda n: "sales" in n or "revenue" in n,
            "Revenue & sales performance",
            [
                "Which region or category drives the most revenue?",
                "How is revenue trending by month?",
                "Where are concentration risks in the sales mix?",
            ],
            ["region_name", "category_name", "revenue", "month_start", "order_date"],
        ),
        (
            lambda n: "customer" in n,
            "Customer segmentation & retention",
            [
                "Which customer segments contribute most value?",
                "Where are churn or repeat-purchase patterns visible?",
            ],
            ["customer_id", "customer_name", "segment", "region_id"],
        ),
        (
            lambda n: "order" in n,
            "Order volume & operational throughput",
            [
                "What is order volume by region or time period?",
                "Are there seasonal peaks in order activity?",
            ],
            ["order_id", "order_date", "customer_id", "region_id", "amount"],
        ),
        (
            lambda n: "product" in n or "category" in n,
            "Product & category mix",
            [
                "Which categories dominate revenue or volume?",
                "Where is assortment under-performing?",
            ],
            ["category_name", "product_id", "revenue"],
        ),
        (
            lambda n: "region" in n,
            "Regional coverage & geographic performance",
            [
                "How does performance compare across regions?",
                "Which markets are under-penetrated?",
            ],
            ["region_name", "region_id"],
        ),
    ]

    joined = " ".join(table_names).lower()
    results: List[Dict[str, Any]] = []
    for predicate, title, insights, indicators in templates:
        if any(predicate(n.lower()) for n in table_names) or predicate(joined):
            results.append(
                _normalize_opportunity(
                    {
                        "title": title,
                        "description": f"Inferred from schema objects: {', '.join(table_names[:4])}{'…' if len(table_names) > 4 else ''}.",
                        "business_value": "High" if "revenue" in title.lower() or "sales" in title.lower() else "Medium",
                        "feasibility": "High",
                        "privacy_risk": "Low",
                        "time_to_insight": "Short",
                        "example_insights": insights,
                        "indicators": [i for i in indicators if any(i in n.lower() for n in table_names)] or indicators,
                        "why_it_matters": f"Executives can prioritize decisions using {title.lower()} once validated.",
                        "required_data": ", ".join(indicators[:5]),
                        "recommended_next_step": f"Run Ask: \"{insights[0]}\"",
                    },
                    len(results) + 1,
                )
            )
    return results[:6]


def _merge_opportunities(existing: List[Dict[str, Any]], inferred: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    titles = {o["title"].lower() for o in existing}
    merged = list(existing)
    for opp in inferred:
        if opp["title"].lower() not in titles:
            merged.append(opp)
            titles.add(opp["title"].lower())
    return merged


def _normalize_prompts(out: Dict[str, Any]) -> List[Dict[str, str]]:
    prompts = out.get("deep_dive_prompts")
    if isinstance(prompts, list) and prompts:
        result = []
        for index, p in enumerate(prompts, 1):
            if isinstance(p, dict):
                result.append(
                    {
                        "title": _text(p.get("title")) or f"Deep dive {index}",
                        "prompt_text": _text(p.get("prompt_text") or p.get("sql") or ""),
                        "intended_use": _text(p.get("intended_use") or "Prelytical Ask"),
                    }
                )
            elif _text(p):
                result.append(
                    {
                        "title": f"Deep dive {index}",
                        "prompt_text": _text(p),
                        "intended_use": "Prelytical Ask",
                    }
                )
        return result

    # Build from opportunities
    built = []
    for opp in out.get("top_signal_opportunities", [])[:4]:
        insights = _as_list(opp.get("example_insights"))
        if insights:
            built.append(
                {
                    "title": opp.get("title", "Analysis"),
                    "prompt_text": insights[0],
                    "intended_use": "Natural language question in Ask tab",
                }
            )
    return built


def _table_names_from_schema(schema_metadata: Optional[Dict[str, Any]]) -> List[str]:
    if not schema_metadata:
        return []
    names: List[str] = []
    for schema in schema_metadata.get("schemas", []):
        schema_name = schema.get("schema", "")
        for obj in schema.get("objects", []):
            names.append(f"{schema_name}.{obj.get('name', '')}")
    return names


def _default_data_shape_overview(table_names: List[str], database_name: str) -> str:
    if not table_names:
        return f"Metadata review of {database_name}; no schema objects were enumerated."
    views = [n for n in table_names if "vw_" in n.lower()]
    tables = [n for n in table_names if n not in views]
    parts = [f"{len(table_names)} object(s) across allowed schemas"]
    if views:
        parts.append(f"{len(views)} curated view(s) in ai schema for executive-ready aggregates")
    if tables:
        parts.append(f"{len(tables)} base table(s) available for deeper drill-down")
    return ". ".join(parts) + "."


def _fallback_readiness(table_names: List[str]) -> int:
    if not table_names:
        return 35
    score = 45 + min(len(table_names), 8) * 5
    if any("ai.vw_" in n.lower() or ".vw_" in n.lower() for n in table_names):
        score += 10
    return min(score, 92)


def _badge(label: str, value: Any, score: Any = None, invert: bool = False) -> str:
    text = _label(value, "Medium")
    css = _signal_class(text, invert=invert)
    score_bit = f' {_score(score, _label_score(text))}' if score is not None else ""
    return f'<span class="badge badge-{css}">{_esc(label)}: {_esc(text)}{score_bit}</span>'


def _signal_class(value: str, invert: bool = False) -> str:
    lowered = value.lower()
    if "high" in lowered:
        return "low" if invert else "high"
    if "low" in lowered:
        return "high" if invert else "low"
    return "med"


def _label(value: Any, default: str) -> str:
    text = _text(value)
    if not text:
        return default
    for candidate in ("High", "Medium", "Low"):
        if candidate.lower() in text.lower():
            return candidate
    return text[:20] if len(text) <= 20 else default


def _label_score(label: str) -> int:
    if label == "High":
        return 85
    if label == "Low":
        return 35
    return 60


def _score(value: Any, default: int = 0) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, score))


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "; ".join(_text(v) for v in value if _text(v))
    return str(value).strip()


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _esc(value: Any) -> str:
    return html.escape(_text(value), quote=True)
