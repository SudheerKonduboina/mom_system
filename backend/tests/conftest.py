# tests/conftest.py
# Shared fixtures for the test suite

import os
import sys
import tempfile
import shutil
import pytest

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_storage():
    """Create a temporary storage directory for tests."""
    tmp = tempfile.mkdtemp(prefix="mom_test_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def test_client():
    """FastAPI test client."""
    # Set test environment
    os.environ["API_SECRET_KEY"] = ""  # Disable auth for tests
    os.environ["ALLOWED_ORIGINS"] = "*"

    from app.main import app
    client = TestClient(app)
    yield client


@pytest.fixture
def sample_transcript():
    """Sample meeting transcript for testing."""
    return (
        "John: Good morning everyone, let's start with the agenda for today. "
        "We need to discuss the API deployment timeline and review the Q3 results. "
        "Alice: I think the API deployment should be done by Friday. "
        "John: Agreed. Rahul, can you handle the deployment? "
        "Rahul: Yes, I'll complete the deployment by Friday. "
        "Alice: There's also a risk that the database migration might fail. "
        "John: Let's add that as a risk item. "
        "Everyone: Sounds good. Let's wrap up. "
        "John: Great meeting. Action items: Rahul deploys API by Friday, "
        "Alice reviews database migration plan by Wednesday."
    )


@pytest.fixture
def sample_mom():
    """Sample MOM dict for testing."""
    return {
        "meetDate": "2026-03-06",
        "participants": ["John", "Alice", "Rahul"],
        "agenda": "API Deployment Review",
        "key_discussions": [
            "API deployment timeline discussed",
            "Q3 results review"
        ],
        "decisions": ["Deploy API by Friday"],
        "action_items": [
            {"task": "Deploy API to production", "owner": "Rahul", "deadline": "Friday", "priority": "high"},
            {"task": "Review database migration plan", "owner": "Alice", "deadline": "Wednesday", "priority": "medium"},
        ],
        "risks": ["Database migration might fail"],
        "conclusion": "API deployment scheduled for Friday. Migration risk noted.",
        "sentiment": "positive",
        "topics_detected": ["API Deployment", "Database Migration", "Q3 Results"],
    }


@pytest.fixture
def sample_audio_path():
    """Create a minimal WAV file for testing."""
    import numpy as np

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        import soundfile as sf
        # Generate 2 seconds of silence with some noise
        sr = 16000
        duration = 2
        audio = np.random.randn(sr * duration).astype(np.float32) * 0.01
        sf.write(tmp.name, audio, sr)
    except ImportError:
        # Write minimal WAV header if soundfile not available
        import struct
        sr = 16000
        samples = sr * 2
        data = b'\x00\x00' * samples
        tmp.write(b'RIFF')
        tmp.write(struct.pack('<I', 36 + len(data)))
        tmp.write(b'WAVE')
        tmp.write(b'fmt ')
        tmp.write(struct.pack('<IHHIIHH', 16, 1, 1, sr, sr * 2, 2, 16))
        tmp.write(b'data')
        tmp.write(struct.pack('<I', len(data)))
        tmp.write(data)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def sample_whisper_segments():
    """Sample Whisper transcription segments."""
    return [
        {"start": 0.0, "end": 3.5, "text": "Good morning everyone let's start.", "confidence": -0.3},
        {"start": 3.5, "end": 8.0, "text": "We need to discuss the API deployment.", "confidence": -0.2},
        {"start": 8.0, "end": 12.0, "text": "I think deployment should be done by Friday.", "confidence": -0.4},
        {"start": 12.0, "end": 16.0, "text": "Rahul can you handle the deployment?", "confidence": -0.3},
        {"start": 16.0, "end": 18.0, "text": "Yes I'll complete it.", "confidence": -0.5},
    ]


@pytest.fixture
def sample_diarization_segments():
    """Sample diarization segments."""
    return [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 3.5},
        {"speaker": "SPEAKER_00", "start": 3.5, "end": 8.0},
        {"speaker": "SPEAKER_01", "start": 8.0, "end": 12.0},
        {"speaker": "SPEAKER_00", "start": 12.0, "end": 16.0},
        {"speaker": "SPEAKER_02", "start": 16.0, "end": 18.0},
    ]


@pytest.fixture
def sample_attendance_events():
    """Sample attendance events from extension."""
    return [
        {"type": "PARTICIPANT_JOIN", "name": "John", "at": "2026-03-06T10:00:00Z"},
        {"type": "PARTICIPANT_JOIN", "name": "Alice", "at": "2026-03-06T10:00:05Z"},
        {"type": "PARTICIPANT_JOIN", "name": "Rahul", "at": "2026-03-06T10:01:00Z"},
        {"type": "PARTICIPANT_LEAVE", "name": "Alice", "at": "2026-03-06T10:30:00Z"},
    ]
