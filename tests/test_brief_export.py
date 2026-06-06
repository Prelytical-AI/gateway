from pathlib import Path

from app.services.brief_export import build_brief_filename, export_brief_html


def test_build_brief_filename_slugifies():
    name = build_brief_filename(title="Executive Data Readiness Brief!", database_name="PrelyticalDemoDW")
    assert name.endswith(".html")
    assert "prelyticaldemodw" in name
    assert "executive-data-readiness-brief" in name


def test_export_brief_html_writes_file(tmp_path: Path):
    html = "<!doctype html><html><body>ok</body></html>"
    path, err = export_brief_html(
        html,
        export_dir=str(tmp_path),
        title="Test Brief",
        database_name="Demo",
    )
    assert err is None
    assert path is not None
    assert Path(path).exists()
    assert Path(path).read_text(encoding="utf-8") == html


def test_export_skipped_when_path_empty():
    path, err = export_brief_html(
        "<html></html>",
        export_dir="",
        title="T",
        database_name="D",
    )
    assert path is None
    assert err is None
