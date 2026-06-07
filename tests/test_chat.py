from app.services.brief_session import BriefSessionStore
from app.services.chat_agent import _heuristic_route, _is_brief_content
from app.services.chat_store import ChatStore


def test_chat_store_remembers_messages():
    store = ChatStore(max_messages=10)
    store.add_user_message("hello")
    store.add_assistant_message("hi there", action="reply")
    msgs = store.list_messages()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    model_hist = store.recent_for_model()
    assert len(model_hist) == 2


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
    session = BriefSessionStore()
    assert session.summary()["loaded"] is False
