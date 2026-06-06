from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def export_brief_html(
    html: str,
    *,
    export_dir: Optional[str],
    title: str,
    database_name: str,
) -> tuple[Optional[str], Optional[str]]:
    """
    Write brief HTML to export_dir if configured.

    Returns (absolute_path, error_message). path is None when skipped or failed.
    """
    if not export_dir or not str(export_dir).strip():
        return None, None

    if not html or not html.strip():
        return None, "Brief HTML was empty; nothing exported."

    try:
        target = Path(str(export_dir).strip())
        target.mkdir(parents=True, exist_ok=True)
        filename = build_brief_filename(title=title, database_name=database_name)
        dest = target / filename
        dest.write_text(html, encoding="utf-8")
        resolved = str(dest.resolve())
        logger.info("Exported executive brief to %s", resolved)
        return resolved, None
    except OSError as exc:
        message = f"Failed to export brief: {exc}"
        logger.warning(message)
        return None, message


def build_brief_filename(*, title: str, database_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = _slugify(title) or "executive-brief"
    db = _slugify(database_name) or "database"
    return f"{stamp}-{db}-{slug}.html"


def _slugify(value: str, *, max_len: int = 48) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:max_len].strip("-")
