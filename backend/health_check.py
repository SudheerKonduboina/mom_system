import os
import sys
import logging
from dotenv import load_dotenv

# Monkeypatch huggingface_hub
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

# Add parent directory to path to import app modules if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HealthCheck")

def check_health():
    print("\nSystem Health Check")
    print("-------------------")
    
    whisper_loaded = False
    diarizer_loaded = False
    
    # HF Token check
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HF_AUTH_TOKEN")
    if not hf_token:
        print("Error: HF_TOKEN or HF_AUTH_TOKEN not found in environment variables.")
    
    # 1. Load Whisper
    try:
        import whisper
        import torch
        
        model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        print(f"Loading Whisper model ({model_size}) on {device}...")
        model = whisper.load_model(model_size, device=device)
        whisper_loaded = True
        print("Whisper model loaded successfully.")
    except Exception as e:
        import traceback
        print(f"Whisper Loading Failed: {e}")
        traceback.print_exc()
        whisper_loaded = False

    # 2. Load Pyannote Diarization
    try:
        from pyannote.audio import Pipeline
        import torch
        
        print("Loading Pyannote speaker diarization pipeline...")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
            
        diarizer_loaded = (pipeline is not None)
        print("Diarizer pipeline loaded successfully.")
    except Exception as e:
        import traceback
        print(f"Diarizer Loading Failed: {e}")
        traceback.print_exc()
        diarizer_loaded = False

    # Final Report
    print("\nHealth Status Report")
    print("--------------------")
    print(f"Whisper Loaded: {whisper_loaded}")
    print(f"Diarizer Loaded: {diarizer_loaded}")
    
    if whisper_loaded and diarizer_loaded:
        print("Status: READY")
    else:
        print("Status: DEGRADED")

if __name__ == "__main__":
    check_health()
