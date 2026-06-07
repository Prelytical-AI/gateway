from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Dict, List, Optional

from app.services.brief_builder import parse_brief_json
from app.services.brief_renderer import normalize_brief_output


def parse_brief_content(
    *,
    html: Optional[str] = None,
    json_text: Optional[str] = None,
) -> Dict[str, Any]:
    if json_text and json_text.strip():
        return _parse_json_brief(json_text.strip())
    if html and html.strip():
        return _parse_html_brief(html.strip())
    raise ValueError("Provide brief HTML or JSON content to import.")


def _parse_json_brief(text: str) -> Dict[str, Any]:
    data = json.loads(text)
    if isinstance(data, dict) and "output" in data:
        output = data["output"]
        title = data.get("title") or "Imported Brief"
    elif isinstance(data, dict) and "top_signal_opportunities" in data:
        output = data
        title = data.get("title") or "Imported Brief"
    else:
        output = parse_brief_json(text) if "executive_summary" in text else data
        title = output.get("title") or "Imported Brief"

    objective = output.get("executive_summary") or output.get("objective") or title
    normalized = normalize_brief_output(
        output,
        title=title,
        objective=objective,
        database_name=output.get("database_name") or "",
        schema_metadata=None,
    )
    return {
        "title": title,
        "database_name": output.get("database_name") or "",
        "executive_summary": normalized.get("executive_summary", ""),
        "opportunities": normalized.get("top_signal_opportunities") or [],
        "output": normalized,
        "html_report": output.get("html_report") or "",
    }


def _parse_html_brief(html: str) -> Dict[str, Any]:
    title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    title = unescape(title_match.group(1).strip()) if title_match else "Imported Brief"

    summary = _extract_section_text(html, "Executive summary") or _extract_tag_text(
        html, "executive-summary"
    )

    opportunities: List[Dict[str, Any]] = []
    for block in re.findall(r'<div class="opportunity">(.*?)</div>\s*(?=<div class="opportunity">|<div class="card"|</section>|$)', html, re.DOTALL | re.IGNORECASE):
        opp = _parse_opportunity_block(block)
        if opp:
            opportunities.append(opp)

    if not opportunities:
        opportunities = _parse_opportunities_fallback(html)

    for i, opp in enumerate(opportunities, 1):
        opp.setdefault("title", f"Opportunity {i}")

    return {
        "title": title,
        "database_name": "",
        "executive_summary": summary or "",
        "opportunities": opportunities,
        "output": {"top_signal_opportunities": opportunities, "executive_summary": summary},
        "html_report": html,
    }


def _parse_opportunity_block(block: str) -> Dict[str, Any]:
    title_m = re.search(r"<h3>\s*(\d+)\.\s*(.*?)<", block, re.DOTALL | re.IGNORECASE)
    title = unescape(re.sub(r"<[^>]+>", "", title_m.group(2)).strip()) if title_m else ""

    desc_m = re.search(r"<h3>.*?</h3>\s*<p>(.*?)</p>", block, re.DOTALL | re.IGNORECASE)
    description = _strip_tags(desc_m.group(1)) if desc_m else ""

    indicators = _extract_list_after_label(block, "Indicators / fields to use:")
    insights = _extract_list_after_label(block, "Example insights to pursue:")

    return {
        "title": title,
        "description": description,
        "indicators": indicators,
        "example_insights": insights,
        "why_it_matters": _extract_labeled(block, "Why it matters:"),
        "required_data": _extract_labeled(block, "Required data:"),
        "caveats": _extract_labeled(block, "Caveats:"),
        "recommended_next_step": _extract_labeled(block, "Next step:"),
        "overall_score": 70,
    }


def _parse_opportunities_fallback(html: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for m in re.finditer(r"<h3>\s*(\d+)\.\s*(.*?)<", html, re.DOTALL | re.IGNORECASE):
        title = _strip_tags(m.group(2))
        if title and "Executive" not in title and "Readiness" not in title:
            items.append({"title": title, "indicators": [], "description": ""})
    return items[:8]


def _extract_list_after_label(block: str, label: str) -> List[str]:
    pattern = re.escape(label) + r".*?<ul[^>]*>(.*?)</ul>"
    m = re.search(pattern, block, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    return [_strip_tags(x) for x in re.findall(r"<li>(.*?)</li>", m.group(1), re.DOTALL) if _strip_tags(x)]


def _extract_labeled(block: str, label: str) -> str:
    pattern = re.escape(label) + r"\s*(.*?)(?:</p>|$)"
    m = re.search(pattern, block, re.DOTALL | re.IGNORECASE)
    return _strip_tags(m.group(1)) if m else ""


def _extract_section_text(html: str, heading: str) -> str:
    pattern = rf"<h2[^>]*>{re.escape(heading)}</h2>\s*<p>(.*?)</p>"
    m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    return _strip_tags(m.group(1)) if m else ""


def _extract_tag_text(html: str, class_name: str) -> str:
    m = re.search(rf'class="{class_name}"[^>]*>(.*?)</', html, re.DOTALL | re.IGNORECASE)
    return _strip_tags(m.group(1)) if m else ""


def _strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", cleaned).strip())
