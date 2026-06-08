from __future__ import annotations

from typing import Any, Dict, List, Optional


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def summarize_successful_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Derive numeric highlights from query rows (local Python, no extra model call)."""
    summaries: List[Dict[str, Any]] = []
    for step in steps:
        if step.get("error") or not step.get("rows"):
            continue
        rows = step["rows"]
        columns = step.get("columns") or []
        numeric_cols = [c for c in columns if any(_to_float(r.get(c)) is not None for r in rows[:20])]
        text_cols = [c for c in columns if c not in numeric_cols]

        entry: Dict[str, Any] = {
            "purpose": step.get("purpose"),
            "row_count": len(rows),
            "columns": columns,
        }
        highlights: List[str] = []

        for num_col in numeric_cols[:2]:
            ranked = sorted(
                rows,
                key=lambda r: _to_float(r.get(num_col)) or 0,
                reverse=True,
            )
            if not ranked:
                continue
            top = ranked[0]
            label_col = text_cols[0] if text_cols else None
            label = top.get(label_col, "Top row") if label_col else "Top row"
            val = _to_float(top.get(num_col))
            if val is not None:
                highlights.append(f"Highest {num_col}: {label} ({_fmt(val)})")
            if len(ranked) > 1:
                total = sum(_to_float(r.get(num_col)) or 0 for r in rows)
                if total:
                    highlights.append(f"Total {num_col} across {len(rows)} rows: {_fmt(total)}")

        entry["highlights"] = highlights
        summaries.append(entry)
    return summaries


def _fmt(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if value == int(value):
        return str(int(value))
    return f"{value:,.2f}"
