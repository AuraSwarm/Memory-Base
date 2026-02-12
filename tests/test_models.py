"""Module tests: memory_base.models (SessionStatus, model classes)."""

from memory_base.models import Session, Message, SessionSummary, SessionStatus


def test_session_status_constants():
    assert SessionStatus.ACTIVE == 1
    assert SessionStatus.COLD_ARCHIVED == 2
    assert SessionStatus.DEEP_ARCHIVED == 3
    assert SessionStatus.DELETED == 4


def test_session_table_name():
    assert Session.__tablename__ == "sessions"


def test_message_table_name():
    assert Message.__tablename__ == "messages"


def test_session_summary_table_name():
    assert SessionSummary.__tablename__ == "session_summaries"


def test_session_has_expected_columns():
    cols = {c.name for c in Session.__table__.columns}
    assert "id" in cols
    assert "updated_at" in cols
    assert "status" in cols
    assert "title" in cols


def test_message_has_expected_columns():
    cols = {c.name for c in Message.__table__.columns}
    assert "id" in cols
    assert "session_id" in cols
    assert "role" in cols
    assert "content" in cols
    assert "created_at" in cols
