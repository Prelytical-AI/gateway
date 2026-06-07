import tempfile
from pathlib import Path

from app.services.brief_session import BriefSessionStore
from app.services.chat_agent import _heuristic_route, _is_brief_content
from app.services.chat_store import ChatStore


def test_chat_store_persists_across_instances():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite3"
        store1 = ChatStore(db, max_messages=10)
        store1.add_user_message("hello")
        store1.add_assistant_message("hi there", action="reply")

        store2 = ChatStore(db, max_messages=10)
        msgs = store2.list_messages()
        assert len(msgs) == 2
        assert msgs[0]["content"] == "hello"
        assert msgs[1]["content"] == "hi there"


def test_brief_session_persists_across_instances():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite3"
        session1 = BriefSessionStore(db)
        session1.import_content(
            json_text='{"top_signal_opportunities": [{"title": "Revenue", "indicators": ["revenue"]}], "executive_summary": "Demo"}',
            database_name="DemoDB",
        )

        session2 = BriefSessionStore(db)
        summary = session2.summary()
        assert summary["loaded"] is True
        assert summary["opportunity_count"] == 1
        assert session2.get_opportunity(1)["title"] == "Revenue"


def test_chat_store_clear():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite3"
        store = ChatStore(db)
        store.add_user_message("x")
        store.clear()
        assert store.list_messages() == []


def test_heuristic_route_investigate():
    route = _heuristic_route("look at item 2 from the brief and run it", brief_loaded=True, has_brief_attachment=False)
    assert route["action"] == "investigate"
    assert route.get("opportunity_index") == 2


def test_heuristic_route_brief():
    route = _heuristic_route("generate the executive data readiness brief", brief_loaded=False, has_brief_attachment=False)
    assert route["action"] == "brief"


def test_is_brief_content():
    assert _is_brief_content("brief.html", "<html><div class=\"opportunity\">")
    assert _is_brief_content("data.json", '{"top_signal_opportunities": []}')
    assert not _is_brief_content("notes.txt", "hello world")


def test_brief_session_summary_empty():
    with tempfile.TemporaryDirectory() as tmp:
        session = BriefSessionStore(Path(tmp) / "test.sqlite3")
        assert session.summary()["loaded"] is False
