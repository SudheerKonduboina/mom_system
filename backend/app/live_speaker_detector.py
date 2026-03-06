# app/live_speaker_detector.py
# Real-time speaker change detection for streaming audio chunks

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("LiveSpeakerDetector")


class LiveSpeakerDetector:
    """
    Detects speaker changes in real-time from streaming audio chunks.
    Uses VAD (Voice Activity Detection) + simple energy-based speaker change detection.
    """

    def __init__(self):
        self._vad_model = None
        self._current_speaker = None
        self._speaker_count = 0
        self._speaker_embeddings: Dict[str, list] = {}

    def _load_vad(self):
        """Load silero VAD model (lightweight, CPU-friendly)."""
        if self._vad_model is not None:
            return self._vad_model
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True,
            )
            self._vad_model = model
            logger.info("Silero VAD model loaded")
            return model
        except Exception as e:
            logger.warning(f"Could not load VAD model: {e}")
            return None

    def detect_speaker_change(self, audio_chunk, sample_rate: int = 16000) -> Dict:
        """
        Process an audio chunk and detect if the speaker changed.

        Returns:
            {
                "is_speaking": bool,
                "speaker_changed": bool,
                "current_speaker": str,
                "confidence": float
            }
        """
        import numpy as np

        result = {
            "is_speaking": False,
            "speaker_changed": False,
            "current_speaker": self._current_speaker or "Speaker_0",
            "confidence": 0.0,
        }

        if audio_chunk is None or len(audio_chunk) == 0:
            return result

        # Ensure numpy array
        if not isinstance(audio_chunk, np.ndarray):
            audio_chunk = np.array(audio_chunk, dtype=np.float32)

        # Step 1: Voice Activity Detection
        is_speaking = self._check_vad(audio_chunk, sample_rate)
        result["is_speaking"] = is_speaking

        if not is_speaking:
            return result

        # Step 2: Speaker change via energy pattern analysis
        energy_profile = self._compute_energy_profile(audio_chunk, sample_rate)
        speaker_changed, confidence = self._detect_change(energy_profile)

        if speaker_changed:
            self._speaker_count += 1
            self._current_speaker = f"Speaker_{self._speaker_count}"
            result["speaker_changed"] = True

        result["current_speaker"] = self._current_speaker or "Speaker_0"
        result["confidence"] = confidence

        return result

    def _check_vad(self, audio_chunk, sample_rate: int) -> bool:
        """Check if there's speech activity in the chunk."""
        import numpy as np

        # Simple energy-based VAD fallback
        energy = np.sqrt(np.mean(audio_chunk ** 2))
        threshold = 0.01  # Adjust based on testing

        # Try silero VAD first
        vad = self._load_vad()
        if vad is not None:
            try:
                import torch
                tensor = torch.FloatTensor(audio_chunk)
                if len(tensor.shape) > 1:
                    tensor = tensor.mean(dim=0)
                # silero expects specific sample rate
                if sample_rate != 16000:
                    import torchaudio
                    tensor = torchaudio.functional.resample(tensor, sample_rate, 16000)
                speech_prob = vad(tensor, 16000).item()
                return speech_prob > 0.5
            except Exception:
                pass

        return energy > threshold

    def _compute_energy_profile(self, audio_chunk, sample_rate: int) -> list:
        """Compute energy profile for speaker change detection."""
        import numpy as np

        frame_size = int(0.03 * sample_rate)  # 30ms frames
        hop_size = int(0.01 * sample_rate)    # 10ms hop

        energies = []
        for i in range(0, len(audio_chunk) - frame_size, hop_size):
            frame = audio_chunk[i:i + frame_size]
            energies.append(float(np.sqrt(np.mean(frame ** 2))))

        return energies

    def _detect_change(self, energy_profile: list) -> Tuple[bool, float]:
        """Detect speaker change based on energy pattern shifts."""
        if len(energy_profile) < 10:
            return False, 0.0

        import numpy as np

        # Split into first half and second half
        mid = len(energy_profile) // 2
        first_half = np.array(energy_profile[:mid])
        second_half = np.array(energy_profile[mid:])

        # Compare energy distributions
        mean_diff = abs(float(np.mean(first_half)) - float(np.mean(second_half)))
        avg_energy = float(np.mean(energy_profile)) or 0.001

        # Normalized difference
        change_score = mean_diff / avg_energy

        # A significant energy pattern change suggests speaker change
        # This is a simplified heuristic — pyannote diarization is more accurate
        speaker_changed = change_score > 0.5
        confidence = min(1.0, change_score)

        return speaker_changed, round(confidence, 3)

    def reset(self):
        """Reset detector state for a new meeting."""
        self._current_speaker = None
        self._speaker_count = 0
        self._speaker_embeddings.clear()
