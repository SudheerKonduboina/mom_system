import torchaudio
if not hasattr(torchaudio, "set_audio_backend"):
    torchaudio.set_audio_backend = lambda x: None

import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import shutil
from dotenv import load_dotenv

from app.audio_engine import AudioEngine
from app.nlp_processor import NLPProcessor
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE_DIR, "storage")
os.makedirs(STORAGE, exist_ok=True)

app.mount("/storage", StaticFiles(directory=STORAGE), name="storage")

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

        transcript = ""
        speakers = []

        # === SAFE DIARIZATION (MERGED LOGIC) ===
        if diarization_pipeline is not None:
            try:
                print("Running Speaker Diarization...")
                waveform, sr = load_audio_safe(path)

                diarization = diarization_pipeline({
                    "waveform": waveform,
                    "sample_rate": sr
                })

                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    speakers.append({
                        "speaker": speaker,
                        "start": turn.start,
                        "end": turn.end
                    })

                # Map speakers to STT segments (original logic preserved)
                for seg in stt.get("segments", []):
                    speaker_label = "Unknown"
                    for s in speakers:
                        if s["start"] <= seg["start"] <= s["end"]:
                            speaker_label = s["speaker"]
                            break
                    transcript += f"Speaker {speaker_label}: {seg['text']}\n"

            except Exception as e:
                print("Diarization failed, continuing without it:", e)
                transcript = stt["text"]

        else:
            print("Diarization disabled")
            transcript = stt["text"]

        print("Running NLP Intelligence...")

        try:
            intel = nlp_processor.extract_intel(transcript)
        except Exception as e:
            print("NLP failed, returning transcript only:", e)
            intel = {}

        return {
            "meeting_id": filename,
            "audio_url": f"/storage/{filename}",
            "full_transcript": transcript,
            **intel
        }


    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
