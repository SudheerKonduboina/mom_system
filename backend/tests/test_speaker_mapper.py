# tests/test_speaker_mapper.py

import pytest
from app.speaker_mapper import SpeakerMapper


@pytest.fixture
def mapper():
    return SpeakerMapper()


class TestSpeakerMapper:
    def test_empty_inputs(self, mapper):
        result = mapper.map_speakers([], [])
        assert result == {}

    def test_no_participants(self, mapper):
        result = mapper.map_speakers(["SPEAKER_00", "SPEAKER_01"], [])
        assert result == {"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "SPEAKER_01"}

    def test_sequential_fallback(self, mapper):
        result = mapper.map_speakers(
            ["SPEAKER_00", "SPEAKER_01"],
            ["Alice", "Bob"]
        )
        assert len(result) == 2
        assert "Alice" in result.values() or "SPEAKER_00" in result.values()

    def test_apply_mapping(self, mapper, sample_whisper_segments, sample_diarization_segments):
        from app.speaker_diarization import SpeakerDiarizer
        diarizer = SpeakerDiarizer()
        aligned = diarizer.align_with_transcript(sample_diarization_segments, sample_whisper_segments)

        mapping = {"SPEAKER_00": "John", "SPEAKER_01": "Alice", "SPEAKER_02": "Rahul"}
        result = mapper.apply_mapping(aligned, mapping)

        assert len(result) == len(aligned)
        for seg in result:
            assert "speaker_name" in seg
            assert "speaker_id" in seg

    def test_mapping_confidence(self, mapper):
        high = mapper._mapping_confidence({"S0": "Alice", "S1": "Bob"})
        low = mapper._mapping_confidence({"S0": "Speaker 1", "S1": "Speaker 2"})
        assert high > low
