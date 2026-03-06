# app/audio_preprocessor.py
# Audio preprocessing: format conversion, noise reduction, normalization, quality scoring

import os
import subprocess
import tempfile
import logging
from typing import Dict, Optional

logger = logging.getLogger("AudioPreprocessor")


class AudioPreprocessor:
    """
    Preprocesses raw meeting audio for optimal Whisper transcription.
    Pipeline: webm → wav (16kHz mono) → noise reduction → normalization → quality score
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if ffmpeg and optional libs are available."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            self.has_ffmpeg = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.has_ffmpeg = False
            logger.warning("ffmpeg not found. Audio conversion will be limited.")

        try:
            import noisereduce
            self.has_noisereduce = True
        except ImportError:
            self.has_noisereduce = False
            logger.warning("noisereduce not installed. Skipping noise reduction.")

    def process(self, input_path: str) -> Dict:
        """
        Full preprocessing pipeline.
        Returns: {processed_path, quality_score, duration_sec, warnings: []}
        """
        warnings = []
        processed_path = input_path

        # Step 1: Convert to WAV (16kHz, mono)
        wav_path = self._convert_to_wav(input_path)
        if wav_path:
            processed_path = wav_path
        else:
            warnings.append({"level": "warning", "message": "Could not convert audio to WAV. Using original file."})

        # Step 2: Load audio for analysis
        try:
            import librosa
            import numpy as np

            audio, sr = librosa.load(processed_path, sr=self.sample_rate, mono=True)
            duration_sec = len(audio) / sr

            # Step 3: Quality score (SNR estimation)
            quality_score = self._estimate_quality(audio, sr)
            if quality_score < 10:
                warnings.append({
                    "level": "warning",
                    "message": f"Audio clarity low (SNR: {quality_score:.1f} dB). Some speech may not be transcribed correctly."
                })

            # Step 4: Noise reduction
            if self.has_noisereduce and quality_score < 20:
                audio = self._reduce_noise(audio, sr)
                logger.info("Applied noise reduction")

            # Step 5: Normalize volume
            audio = self._normalize(audio)

            # Step 6: Trim silence
            audio_trimmed, _ = librosa.effects.trim(audio, top_db=30)
            if len(audio_trimmed) > self.sample_rate:  # at least 1 second after trim
                audio = audio_trimmed

            # Save processed audio
            import soundfile as sf
            processed_path = processed_path.replace(".wav", "_processed.wav")
            if processed_path == input_path:
                processed_path = input_path + "_processed.wav"
            sf.write(processed_path, audio, self.sample_rate)

            return {
                "processed_path": processed_path,
                "quality_score": round(quality_score, 2),
                "duration_sec": round(duration_sec, 2),
                "warnings": warnings,
            }

        except ImportError:
            logger.warning("librosa not available. Skipping audio analysis.")
            warnings.append({"level": "warning", "message": "Audio analysis libraries not available."})
            return {
                "processed_path": processed_path,
                "quality_score": 50,  # assume OK
                "duration_sec": 0,
                "warnings": warnings,
            }
        except Exception as e:
            logger.error(f"Audio preprocessing error: {e}")
            warnings.append({"level": "warning", "message": f"Audio preprocessing failed: {str(e)}"})
            return {
                "processed_path": input_path,
                "quality_score": 0,
                "duration_sec": 0,
                "warnings": warnings,
            }

    def _convert_to_wav(self, input_path: str) -> Optional[str]:
        """Convert any audio format to WAV (16kHz, mono) using ffmpeg."""
        if not self.has_ffmpeg:
            return None

        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".wav":
            return input_path

        output_path = os.path.splitext(input_path)[0] + ".wav"
        try:
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-ar", str(self.sample_rate),
                "-ac", "1",
                "-acodec", "pcm_s16le",
                output_path
            ]
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            logger.info(f"Converted {ext} → .wav: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"ffmpeg conversion failed: {e}")
            return None

    def _estimate_quality(self, audio, sr: int) -> float:
        """Estimate audio quality via simple SNR calculation."""
        import numpy as np

        # Simple energy-based SNR estimate
        frame_length = int(0.025 * sr)
        hop_length = int(0.010 * sr)

        energy = []
        for i in range(0, len(audio) - frame_length, hop_length):
            frame = audio[i:i + frame_length]
            energy.append(float(np.sum(frame ** 2)))

        if not energy:
            return 0

        energy = sorted(energy)
        noise_floor = max(1e-10, float(np.mean(energy[:len(energy) // 10])))  # bottom 10%
        signal_level = max(1e-10, float(np.mean(energy[len(energy) // 2:])))  # top 50%

        snr_db = 10 * float(np.log10(signal_level / noise_floor))
        return max(0, min(100, snr_db))

    def _reduce_noise(self, audio, sr: int):
        """Apply spectral gating noise reduction."""
        try:
            import noisereduce as nr
            import numpy as np
            return nr.reduce_noise(y=audio, sr=sr, prop_decrease=0.6)
        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}")
            return audio

    def _normalize(self, audio):
        """Normalize audio volume to target level."""
        import numpy as np
        peak = float(np.max(np.abs(audio)))
        if peak > 0:
            target = 0.9  # normalize to 90% of max
            audio = audio * (target / peak)
        return audio
