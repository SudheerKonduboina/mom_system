# tests/test_meeting_insights.py

import pytest
from app.meeting_insights import MeetingInsightsEngine


@pytest.fixture
def engine():
    return MeetingInsightsEngine()


class TestSentiment:
    def test_keyword_positive(self, engine):
        result = engine._keyword_sentiment("Great job everyone, excellent progress approved.")
        assert result["overall"] in ("positive", "neutral")

    def test_keyword_negative(self, engine):
        result = engine._keyword_sentiment("Critical issue, delay risk, problems blocking.")
        assert result["overall"] in ("negative", "neutral")

    def test_empty_text(self, engine):
        result = engine._analyze_sentiment("")
        assert result["overall"] == "neutral"


class TestTopics:
    def test_tfidf_topics(self, engine, sample_transcript):
        topics = engine._tfidf_topics(sample_transcript)
        assert isinstance(topics, list)

    def test_empty_text(self, engine):
        topics = engine._detect_topics("")
        assert topics == []


class TestEngagement:
    def test_no_data(self, engine):
        score = engine._calculate_engagement({}, 0, 0)
        assert score == 0

    def test_single_speaker(self, engine):
        score = engine._calculate_engagement({"Alice": 300}, 1, 600)
        assert 0 <= score <= 100

    def test_balanced_speakers(self, engine):
        score = engine._calculate_engagement(
            {"Alice": 200, "Bob": 200, "Charlie": 200}, 3, 600
        )
        assert score > 30  # Balanced = good engagement

    def test_imbalanced_speakers(self, engine):
        balanced = engine._calculate_engagement(
            {"Alice": 200, "Bob": 200}, 2, 400
        )
        imbalanced = engine._calculate_engagement(
            {"Alice": 380, "Bob": 20}, 2, 400
        )
        assert balanced >= imbalanced


class TestSpeakingTimeFormat:
    def test_format(self, engine):
        result = engine._format_speaking_times({"Alice": 125, "Bob": 60})
        assert len(result) == 2
        assert result[0]["percentage"] > result[1]["percentage"]
        assert "display" in result[0]
