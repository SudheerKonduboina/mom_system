# app/config.py
# Centralized configuration from environment variables

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application-wide configuration loaded from .env"""

    # --- AI / Model ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    HF_AUTH_TOKEN: str = os.getenv("HF_AUTH_TOKEN", "")
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "medium")
    USE_QUANTIZATION: bool = os.getenv("USE_QUANTIZATION", "false").lower() == "true"
    GPU_MEMORY_LIMIT_MB: int = int(os.getenv("GPU_MEMORY_LIMIT_MB", "0"))

    # --- Audio ---
    MAX_AUDIO_DURATION_SEC: int = int(os.getenv("MAX_AUDIO_DURATION_SEC", "14400"))  # 4 hours
    PROCESSING_TIMEOUT_SEC: int = int(os.getenv("PROCESSING_TIMEOUT_SEC", "300"))  # 5 min
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 1  # mono

    # --- Security ---
    API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "")
    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS",
        "chrome-extension://*,http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "100"))
    RATE_LIMIT_PER_MIN: int = int(os.getenv("RATE_LIMIT_PER_MIN", "10"))

    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./storage/meetings.db")

    # --- Storage ---
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    STORAGE_DIR: str = os.path.join(BASE_DIR, "storage")

    @classmethod
    def auto_select_whisper_model(cls) -> str:
        """Auto-select Whisper model based on available hardware."""
        import torch
        if torch.cuda.is_available():
            vram_mb = torch.cuda.get_device_properties(0).total_mem / (1024 ** 2)
            if vram_mb >= 8000:
                return "large-v3"
            elif vram_mb >= 4000:
                return "medium"
            else:
                return "small"
        return cls.WHISPER_MODEL_SIZE  # fallback to configured


settings = Settings()
