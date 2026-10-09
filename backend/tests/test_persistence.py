import pytest
from app.services.storage import Storage


def test_durable_sessions_guides_and_workspace_scope(tmp_path):
    db = tmp_path / "durable.db"
    store = Storage(str(db))
    ws = store.create_workspace("one")
    other = store.create_workspace("two")
    session = store.create_chat_session(ws.id, "Chat")
    store.append_chat_turn(session["id"], ws.id, "question", "answer", [], ["src"], [])
    guide = store.create_saved_guide(ws.id, {"title": "Guide", "workspace_id": ws.id, "executive_summary": "S", "key_concepts": []}, ["src"])
    reopened = Storage(str(db))
    assert reopened.get_chat_session(ws.id, session["id"])["messages"][1]["content"] == "answer"
    assert reopened.get_saved_guide(ws.id, guide["id"])["source_ids"] == ["src"]
    assert reopened.get_chat_session(other.id, session["id"]) is None
    assert reopened.get_saved_guide(other.id, guide["id"]) is None
