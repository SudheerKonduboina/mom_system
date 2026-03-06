# tests/test_database.py

import os
import pytest
import tempfile
from datetime import datetime

# Override DB path before importing
_test_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db}"


class TestDatabase:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Fresh database for each test."""
        import app.database as db_mod
        from app.models import Base
        db_mod.DB_PATH = _test_db
        db_mod.DATABASE_URL = f"sqlite:///{_test_db}"

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(db_mod.DATABASE_URL)
        Base.metadata.create_all(bind=engine)
        db_mod.engine = engine
        db_mod.SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        yield
        Base.metadata.drop_all(bind=engine)

    def test_create_meeting(self):
        import app.database as db
        meeting = db.create_meeting("test_001", platform="google_meet", title="Test Meeting")
        assert meeting.meeting_id == "test_001"
        assert meeting.status == "queued"

    def test_update_meeting_status(self):
        import app.database as db
        db.create_meeting("test_002")
        db.update_meeting_status("test_002", "completed", duration_sec=300)
        meeting = db.get_meeting("test_002")
        assert meeting["status"] == "completed"

    def test_save_and_get_transcript(self):
        import app.database as db
        db.create_meeting("test_003")
        db.save_transcript("test_003", "Hello world", "Speaker: Hello world", "english")
        meeting = db.get_meeting("test_003")
        assert meeting["full_transcript"] == "Hello world"
        assert meeting["word_count"] == 2

    def test_action_items_crud(self):
        import app.database as db
        db.create_meeting("test_004")
        db.save_action_items("test_004", [
            {"task": "Deploy API", "owner": "Rahul", "deadline": "Friday", "priority": "high"},
            {"task": "Review code", "owner": "Alice", "priority": "medium"},
        ])
        items = db.get_action_items(meeting_id="test_004")
        assert len(items) == 2
        assert items[0]["owner"] in ("Rahul", "Alice")

    def test_update_action_item(self):
        import app.database as db
        db.create_meeting("test_005")
        db.save_action_items("test_005", [{"task": "Test task", "owner": "Bob"}])
        items = db.get_action_items(meeting_id="test_005")
        assert len(items) == 1
        db.update_action_item(items[0]["id"], status="completed")
        updated = db.get_action_items(meeting_id="test_005")
        assert updated[0]["status"] == "completed"

    def test_list_meetings(self):
        import app.database as db
        db.create_meeting("test_006a", title="First")
        db.create_meeting("test_006b", title="Second")
        meetings = db.list_meetings(limit=10)
        assert len(meetings) >= 2

    def test_delete_meeting(self):
        import app.database as db
        db.create_meeting("test_007")
        assert db.delete_meeting("test_007") is True
        assert db.get_meeting("test_007") is None

    def test_save_warnings(self):
        import app.database as db
        db.create_meeting("test_008")
        db.save_warnings("test_008", [
            {"level": "warning", "message": "Low audio quality"},
        ])
        meeting = db.get_meeting("test_008")
        assert len(meeting["warnings"]) == 1
