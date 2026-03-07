# app/model_manager.py
# Singleton model loader with auto-selection, quantization, and GPU management

import logging
import time
import threading
from typing import Optional

try:
    import torch
except ImportError:
    torch = None

from app.config import settings

# Monkeypatch huggingface_hub to preserve compatibility between pyannote.audio and new hf_hub versions
try:
    import huggingface_hub
    original_hf_hub_download = huggingface_hub.hf_hub_download
    def patched_hf_hub_download(*args, **kwargs):
        if 'use_auth_token' in kwargs:
            kwargs['token'] = kwargs.pop('use_auth_token')
        return original_hf_hub_download(*args, **kwargs)
    huggingface_hub.hf_hub_download = patched_hf_hub_download
except Exception:
    pass

logger = logging.getLogger("ModelManager")


class ModelManager:
    """
    Manages AI model lifecycle:
    - Singleton loading (load once, reuse)
    - Auto model size selection based on GPU
    - Memory management and cleanup
    """

    _instance = None
    _lock = threading.Lock()

    _whisper_model = None
    _diarizer = None
    _whisper_loaded_at: float = 0
    _diarizer_loaded_at: float = 0

    IDLE_TIMEOUT = 300  # 5 minutes

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def device(self) -> str:
        if torch is None:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"

    @property
    def gpu_info(self) -> dict:
        if torch is None or not torch.cuda.is_available():
            return {"available": False, "device": "cpu"}
        props = torch.cuda.get_device_properties(0)
        return {
            "available": True,
            "device": props.name,
            "vram_mb": int(props.total_mem / (1024 ** 2)),
            "vram_used_mb": int(torch.cuda.memory_allocated() / (1024 ** 2)),
        }

    # -----------------------------------------------------------------------
    # Whisper
    # -----------------------------------------------------------------------
    def get_whisper(self):
        """Get or load the Whisper model (singleton)."""
        if self._whisper_model is not None:
            self._whisper_loaded_at = time.time()
            return self._whisper_model

        model_size = self._select_whisper_size()
        logger.info(f"Loading Whisper model: {model_size} on {self.device}")

        try:
            import whisper
            self._whisper_model = whisper.load_model(model_size, device=self.device)
            self._whisper_loaded_at = time.time()

            # Apply quantization for CPU
            if self.device == "cpu" and settings.USE_QUANTIZATION:
                try:
                    self._whisper_model = torch.quantization.quantize_dynamic(
                        self._whisper_model, {torch.nn.Linear}, dtype=torch.qint8
                    )
                    logger.info("Applied INT8 quantization for CPU")
                except Exception as e:
                    logger.warning(f"Quantization failed: {e}")

            logger.info(f"Whisper '{model_size}' loaded successfully on {self.device}")
            return self._whisper_model
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _select_whisper_size(self) -> str:
        """Auto-select model size based on hardware."""
        configured = settings.WHISPER_MODEL_SIZE

        if configured != "auto":
            return configured

        if not torch.cuda.is_available():
            logger.info("CPU mode: using 'base' model")
            return "base"

        vram_mb = torch.cuda.get_device_properties(0).total_mem / (1024 ** 2)
        if vram_mb >= 8000:
            return "large-v3"
        elif vram_mb >= 4000:
            return "medium"
        elif vram_mb >= 2000:
            return "small"
        else:
            return "base"

    # -----------------------------------------------------------------------
    # Speaker Diarization (pyannote)
    # -----------------------------------------------------------------------
    def get_diarizer(self):
        """Get or load the pyannote diarization pipeline (singleton)."""
        if self._diarizer is not None:
            self._diarizer_loaded_at = time.time()
            return self._diarizer

        hf_token = settings.HF_AUTH_TOKEN
        if not hf_token:
            logger.warning("HF_AUTH_TOKEN not set. Speaker diarization unavailable.")
            return None

        try:
            from pyannote.audio import Pipeline
            logger.info("Loading pyannote speaker diarization pipeline...")
            self._diarizer = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token,
            )
            if self.device == "cuda":
                self._diarizer.to(torch.device("cuda"))

            self._diarizer_loaded_at = time.time()
            logger.info("Pyannote diarization pipeline loaded successfully")
            return self._diarizer
        except Exception as e:
            logger.error(f"Failed to load diarization pipeline: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    # -----------------------------------------------------------------------
    # Memory Management
    # -----------------------------------------------------------------------
    def cleanup_idle(self):
        """Release models that haven't been used for IDLE_TIMEOUT seconds."""
        now = time.time()

        if self._whisper_model and (now - self._whisper_loaded_at > self.IDLE_TIMEOUT):
            logger.info("Releasing idle Whisper model")
            del self._whisper_model
            self._whisper_model = None
            self._clear_gpu()

        if self._diarizer and (now - self._diarizer_loaded_at > self.IDLE_TIMEOUT):
            logger.info("Releasing idle diarization model")
            del self._diarizer
            self._diarizer = None
            self._clear_gpu()

    def force_cleanup(self):
        """Force release all models and GPU memory."""
        self._whisper_model = None
        self._diarizer = None
        self._clear_gpu()
        logger.info("All models released")

    def _clear_gpu(self):
        """Clear GPU cache."""
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()

    def initialize_all(self):
        """Force initialization of all models."""
        logger.info("Initializing all models...")
        self.get_whisper()
        self.get_diarizer()
        return self.get_performance_metrics()

    def get_performance_metrics(self) -> dict:
        """Return current model status and memory usage."""
        return {
            "whisper_loaded": self._whisper_model is not None,
            "diarizer_loaded": self._diarizer is not None,
            "device": self.device,
            "gpu": self.gpu_info,
            "whisper_status": "loaded" if self._whisper_model else "not_loaded",
            "diarizer_status": "loaded" if self._diarizer else "not_loaded"
        }


# Singleton instance
model_manager = ModelManager()
