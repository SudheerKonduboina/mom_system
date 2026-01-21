import torchaudio
if not hasattr(torchaudio, "set_audio_backend"):
    torchaudio.set_audio_backend = lambda x: None

import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from datetime import datetime
import shutil
import json
from dotenv import load_dotenv

from app.audio_engine import AudioEngine
from app.nlp_processor import NLPProcessor
from app.mom_generator import generate_mom_from_transcript
from app.utils.audio_loader import load_audio_safe
from pyannote.audio import Pipeline
import torch

# ENV
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE_DIR, "storage")
os.makedirs(STORAGE, exist_ok=True)

app.mount("/storage", StaticFiles(directory=STORAGE), name="storage")

# Initialize engines
audio_engine = AudioEngine()
nlp_processor = NLPProcessor()

# Load diarization
try:
    diarization_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=HF_TOKEN
    )
    diarization_pipeline.to(torch.device("cpu"))
    print("Diarization Pipeline Loaded")
except Exception as e:
    diarization_pipeline = None
    print("Diarization Disabled:", e)


@app.post("/analyze-meeting")
async def analyze_meeting(file: UploadFile = File(...)):
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_meeting.webm")
    path = os.path.join(STORAGE, filename)

    try:
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        print("Running Whisper STT...")
        stt = audio_engine.process_audio(path)
        transcript = stt.get("text", "")

        print("Generating MOM...")
        mom = generate_mom_from_transcript(transcript)

        response = {
            "meeting_id": filename,
            "audio_url": f"/storage/{filename}",
            "mom": mom
        }

        # Save JSON
        with open(path.replace(".webm", ".json"), "w", encoding="utf-8") as jf:
            json.dump(response, jf, indent=4)

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/meetings")
async def list_meetings():
    """
    List all audio files in storage folder (with transcript if available).
    """
    try:
        files = sorted(os.listdir(STORAGE), reverse=True)
        meetings = []

        for f in files:
            if f.endswith(".webm"):
                json_path = os.path.join(STORAGE, f.replace(".webm", ".json"))
                if os.path.exists(json_path):
                    # Use analyzed data
                    with open(json_path, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                else:
                    # If no analysis, just return basic info
                    data = {
                        "meeting_id": f,
                        "audio_url": f"/storage/{f}",
                        "full_transcript": "",
                        "speakers": []
                    }
                meetings.append(data)

        return JSONResponse(content=meetings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
