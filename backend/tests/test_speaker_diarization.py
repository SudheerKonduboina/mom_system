# tests/test_speaker_diarization.py

import pytest
from app.speaker_diarization import SpeakerDiarizer


@pytest.fixture
def diarizer():
    return SpeakerDiarizer()


class TestTimestampAlignment:
    def test_basic_alignment(self, diarizer, sample_whisper_segments, sample_diarization_segments):
        aligned = diarizer.align_with_transcript(sample_diarization_segments, sample_whisper_segments)
        assert len(aligned) == len(sample_whisper_segments)
        assert all("speaker" in s for s in aligned)
        assert all("text" in s for s in aligned)

    def test_empty_diarization(self, diarizer, sample_whisper_segments):
        aligned = diarizer.align_with_transcript([], sample_whisper_segments)
        assert len(aligned) == len(sample_whisper_segments)
        assert all(s["speaker"] == "Speaker" for s in aligned)

    def test_empty_whisper(self, diarizer, sample_diarization_segments):
        aligned = diarizer.align_with_transcript(sample_diarization_segments, [])
        assert len(aligned) == 0

    def test_speaker_transcript(self, diarizer, sample_whisper_segments, sample_diarization_segments):
        aligned = diarizer.align_with_transcript(sample_diarization_segments, sample_whisper_segments)
        transcript = diarizer.build_speaker_transcript(aligned)
        assert isinstance(transcript, str)
        assert len(transcript) > 0

    def test_speaking_times(self, diarizer, sample_whisper_segments, sample_diarization_segments):
        aligned = diarizer.align_with_transcript(sample_diarization_segments, sample_whisper_segments)
        times = diarizer.get_speaking_times(aligned)
        assert isinstance(times, dict)
        assert all(v >= 0 for v in times.values())
