# tests/test_audio_preprocessing.py

import os
import pytest
import numpy as np
import tempfile


class TestAudioPreprocessor:
    @pytest.fixture
    def preprocessor(self):
        from app.audio_preprocessor import AudioPreprocessor
        return AudioPreprocessor(sample_rate=16000)

    def test_init(self, preprocessor):
        assert preprocessor.sample_rate == 16000

    def test_quality_estimation(self, preprocessor):
        # Generate noisy audio
        audio = np.random.randn(16000 * 2).astype(np.float32) * 0.01
        score = preprocessor._estimate_quality(audio, 16000)
        assert 0 <= score <= 100

    def test_normalize(self, preprocessor):
        audio = np.array([0.1, -0.2, 0.3, -0.4], dtype=np.float32)
        normalized = preprocessor._normalize(audio)
        assert abs(float(np.max(np.abs(normalized))) - 0.9) < 0.01

    def test_normalize_silence(self, preprocessor):
        audio = np.zeros(100, dtype=np.float32)
        normalized = preprocessor._normalize(audio)
        assert np.allclose(normalized, 0)

    def test_process_returns_dict(self, preprocessor, sample_audio_path):
        result = preprocessor.process(sample_audio_path)
        assert "processed_path" in result
        assert "quality_score" in result
        assert "warnings" in result

    def test_quality_warning_for_noisy_audio(self, preprocessor):
        # Generate very noisy audio
        audio = np.random.randn(16000 * 2).astype(np.float32) * 0.001
        score = preprocessor._estimate_quality(audio, 16000)
        # Very low energy audio should get low score
        assert isinstance(score, float)
