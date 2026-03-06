# tests/test_error_detection.py

import pytest
from app.error_detection import detect_errors


class TestErrorDetection:
    def test_low_quality_audio(self):
        warnings = detect_errors(audio_quality_score=5)
        assert any("clarity" in w["message"].lower() or "quality" in w["message"].lower() for w in warnings)

    def test_short_transcript(self):
        warnings = detect_errors(transcript="hi")
        assert any("short" in w["message"].lower() or "unclear" in w["message"].lower() for w in warnings)

    def test_missing_mom_keys(self):
        warnings = detect_errors(mom={"agenda": "Test"})
        assert any("missing" in w["message"].lower() for w in warnings)

    def test_valid_mom(self, sample_mom):
        warnings = detect_errors(transcript="A" * 100, mom=sample_mom, audio_quality_score=80)
        # No critical errors expected
        assert not any(w["level"] == "error" for w in warnings)

    def test_hallucination_detection(self):
        transcript = "This is a meeting. Thank you for watching. Please subscribe."
        warnings = detect_errors(transcript=transcript)
        assert any("hallucination" in w["message"].lower() for w in warnings)

    def test_no_transcript(self):
        warnings = detect_errors(transcript="")
        assert any(w["level"] == "error" for w in warnings)
