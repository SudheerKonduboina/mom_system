# tests/test_action_tracker.py

import pytest
from app.action_tracker import ActionTracker


@pytest.fixture
def tracker():
    return ActionTracker()


class TestPriorityInference:
    def test_high_priority(self, tracker):
        assert tracker._infer_priority("Deploy ASAP to production", "today") == "high"
        assert tracker._infer_priority("Critical bug fix needed urgently", "TBD") == "high"

    def test_low_priority(self, tracker):
        assert tracker._infer_priority("Nice to have feature when possible", "TBD") == "low"

    def test_medium_priority(self, tracker):
        assert tracker._infer_priority("Review code changes", "next week") == "medium"


class TestDeadlineCheck:
    def test_tbd_not_overdue(self, tracker):
        assert tracker._is_past_deadline("TBD", "2026-03-06") is False

    def test_past_date(self, tracker):
        assert tracker._is_past_deadline("2026-01-01", "2026-03-06") is True

    def test_future_date(self, tracker):
        assert tracker._is_past_deadline("2030-12-31", "2026-03-06") is False

    def test_day_name_not_overdue(self, tracker):
        assert tracker._is_past_deadline("Monday", "2026-03-06") is False


class TestFollowUpMatching:
    def test_match_found(self, tracker):
        pending = [
            {"task": "Deploy API to production", "owner": "Rahul", "from_meeting": "m1"}
        ]
        match = tracker._find_matching_pending("Deploy API completed", "Rahul", pending)
        assert match is not None

    def test_no_match(self, tracker):
        pending = [
            {"task": "Deploy API to production", "owner": "Rahul", "from_meeting": "m1"}
        ]
        match = tracker._find_matching_pending("Design new UI", "Alice", pending)
        assert match is None
