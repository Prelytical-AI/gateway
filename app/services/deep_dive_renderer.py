from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def render_investigation_html(
    *,
    title: str,
    database_name: str,
    user_question: str,
    mode: str,
    synthesis: Dict[str, Any],
    evidence_steps: List[Dict[str, Any]],
    brief_title: str = "",
    opportunity: Optional[Dict[str, Any]] = None,
) -> str:
    generated = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    approach = _esc(synthesis.get("approach_summary") or "")
    exec_summary = _esc(synthesis.get("executive_summary") or "")
    trends = synthesis.get("trends_and_patterns") or []
    implications = synthesis.get("business_implications") or []
    findings = synthesis.get("key_findings") or []
    tables_used = synthesis.get("tables_used") or []
    caveats = synthesis.get("caveats") or []
    next_steps = synthesis.get("recommended_next_steps") or []

    trends_html = "".join(f"<li>{_esc(x)}</li>" for x in trends if x)
    implications_html = "".join(f"<li>{_esc(x)}</li>" for x in implications if x)
    findings_html = "".join(f"<li>{_esc(x)}</li>" for x in findings if x)

    opp_block = ""
    if opportunity:
        opp_block = f"""
        <section class="card">
          <h2>Brief opportunity</h2>
          <p><strong>{_esc(opportunity.get("title") or "")}</strong></p>
          <p>{_esc(opportunity.get("description") or "")}</p>
        </section>"""

    failure_banner = ""
    if not evidence_steps:
        failure_banner = """
    <section class="card failure-banner">
      <h2>Limited data available</h2>
      <p>We could not retrieve enough data to produce a full analysis. Consider narrowing the question.</p>
    </section>"""

    evidence_html = "".join(_render_evidence(step) for step in evidence_steps)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_esc(title)} — Prelytical</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --text: #e7ecf3;
      --muted: #9aa8bc;
      --accent: #3b82f6;
      --border: #2d3a4f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.55;
      margin: 0;
      padding: 2rem;
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; }}
    h1 {{ font-size: 1.75rem; margin: 0 0 0.25rem; }}
    .meta {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 1.5rem; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.25rem;
    }}
    h2 {{ font-size: 1.15rem; margin: 0 0 0.75rem; color: #cbd5e1; }}
    h3 {{ font-size: 1rem; margin: 0 0 0.5rem; color: #94a3b8; }}
    ul {{ margin: 0.25rem 0 0; padding-left: 1.25rem; }}
    li {{ margin: 0.35rem 0; }}
    .pill {{
      display: inline-block;
      background: #243044;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 0.15rem 0.65rem;
      font-size: 0.8rem;
      margin: 0.15rem 0.25rem 0.15rem 0;
    }}
    .pill.mode {{ background: #1e3a5f; border-color: #2563eb; color: #93c5fd; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
      margin-top: 0.75rem;
    }}
    th, td {{
      border: 1px solid var(--border);
      padding: 0.45rem 0.6rem;
      text-align: left;
    }}
    th {{ background: #243044; }}
    tr:nth-child(even) td {{ background: rgba(255,255,255,0.02); }}
    .chart {{ margin-top: 0.75rem; }}
    .bar-row {{ display: flex; align-items: center; gap: 0.5rem; margin: 0.35rem 0; font-size: 0.82rem; }}
    .bar-label {{ flex: 0 0 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); }}
    .bar-track {{ flex: 1; background: #0b1220; border-radius: 4px; height: 18px; overflow: hidden; }}
    .bar-fill {{ background: linear-gradient(90deg, #2563eb, #3b82f6); height: 100%; border-radius: 4px; min-width: 2px; }}
    .bar-value {{ flex: 0 0 80px; text-align: right; font-variant-numeric: tabular-nums; }}
    .evidence {{ margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }}
    .evidence:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
    .note {{ color: var(--muted); font-size: 0.85rem; }}
    .failure-banner {{ border-color: #f87171; background: #2a1515; }}
    .failure-banner h2 {{ color: #fca5a5; }}
  </style>
</head>
<body>
  <div class="wrap prelytical-investigation-report">
    <h1>{_esc(title)}</h1>
    <p class="meta">
      Database: {_esc(database_name)} · Generated {generated}
      · <span class="pill mode">{_esc(mode)}</span>
      {f"· Brief: {_esc(brief_title)}" if brief_title else ""}
    </p>

    {failure_banner}

    <section class="card">
      <h2>Question</h2>
      <p>{_esc(user_question)}</p>
    </section>

    {opp_block}

    {f'<section class="card"><h2>Analysis approach</h2><p>{approach}</p></section>' if approach else ""}

    <section class="card">
      <h2>Executive summary</h2>
      <p>{exec_summary}</p>
    </section>

    {f'<section class="card"><h2>Trends &amp; patterns</h2><ul>{trends_html}</ul></section>' if trends_html else ""}

    {f'<section class="card"><h2>Business implications</h2><ul>{implications_html}</ul></section>' if implications_html else ""}

    {f'<section class="card"><h2>Key findings</h2><ul>{findings_html}</ul></section>' if findings_html else ""}

    {f'<section class="card"><h2>Supporting data</h2>{evidence_html}</section>' if evidence_html else ""}

    <section class="card">
      {_pill_row("Data sources", tables_used)}
      {_list_section("Caveats", caveats)}
      {_list_section("Recommended next steps", next_steps)}
    </section>
  </div>
</body>
</html>"""


def _render_evidence(step: Dict[str, Any]) -> str:
    purpose = _esc(step.get("purpose") or "Analysis")
    table_html = _render_data_table(step.get("columns") or [], step.get("rows") or [])
    chart_html = _render_bar_chart(step.get("columns") or [], step.get("rows") or [])

    return f"""
    <div class="evidence">
      <h3>{purpose}</h3>
      {chart_html}
      {table_html}
    </div>"""


def _render_data_table(columns: List[str], rows: List[Dict[str, Any]]) -> str:
    if not columns or not rows:
        return ""
    display_rows = rows[:50]
    head = "".join(f"<th>{_esc(c)}</th>" for c in columns)
    body = ""
    for row in display_rows:
        body += "<tr>" + "".join(f"<td>{_esc(_cell(row.get(c)))}</td>" for c in columns) + "</tr>"
    note = f'<p class="note">Showing {len(display_rows)} of {len(rows)} rows</p>' if len(rows) > len(display_rows) else ""
    return f"{note}<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _render_bar_chart(columns: List[str], rows: List[Dict[str, Any]]) -> str:
    label_col, value_col = _pick_chart_columns(columns, rows)
    if not label_col or not value_col:
        return ""

    pairs: List[Tuple[str, float]] = []
    for row in rows[:12]:
        label = _cell(row.get(label_col))
        val = _to_float(row.get(value_col))
        if label and val is not None:
            pairs.append((str(label), val))
    if len(pairs) < 2:
        return ""

    max_val = max(v for _, v in pairs) or 1.0
    bars = []
    for label, val in pairs:
        pct = max(2, int(100 * val / max_val))
        bars.append(
            f'<div class="bar-row"><span class="bar-label" title="{_esc(label)}">{_esc(label)}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>'
            f'<span class="bar-value">{_esc(_format_num(val))}</span></div>'
        )
    return f'<div class="chart">{"".join(bars)}</div>'


def _pick_chart_columns(columns: List[str], rows: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    if not columns or not rows:
        return None, None
    numeric_cols = [c for c in columns if any(_to_float(r.get(c)) is not None for r in rows[:10])]
    text_cols = [c for c in columns if c not in numeric_cols]
    if not numeric_cols:
        return None, None
    value_col = numeric_cols[0]
    label_col = text_cols[0] if text_cols else columns[0]
    if label_col == value_col and len(columns) > 1:
        label_col = columns[0] if columns[0] != value_col else columns[1]
    return label_col, value_col


def _list_section(title: str, items: List[str]) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{_esc(x)}</li>" for x in items if x)
    return f"<h3>{_esc(title)}</h3><ul>{lis}</ul>" if lis else ""


def _pill_row(title: str, items: List[str]) -> str:
    if not items:
        return ""
    pills = "".join(f'<span class="pill">{_esc(x)}</span>' for x in items if x)
    return f"<h3>{_esc(title)}</h3><p>{pills}</p>" if pills else ""


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if re.match(r"^-?\d+(\.\d+)?$", text):
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _format_num(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if value == int(value):
        return str(int(value))
    return f"{value:,.2f}"
