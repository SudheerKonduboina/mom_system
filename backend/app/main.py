import torchaudio
if not hasattr(torchaudio, "set_audio_backend"):
    torchaudio.set_audio_backend = lambda x: None

import os
import json
import shutil
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.audio_engine import AudioEngine
from app.mom_generator import generate_mom_from_transcript

# --------------------------------------------------
# ENV & APP
# --------------------------------------------------
load_dotenv()

app = FastAPI(title="MOM Intelligence Backend", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --------------------------------------------------
# STORAGE
# --------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE_DIR, "storage")
os.makedirs(STORAGE, exist_ok=True)

app.mount("/storage", StaticFiles(directory=STORAGE), name="storage")

# --------------------------------------------------
# ENGINES
# --------------------------------------------------
audio_engine = AudioEngine()

# --------------------------------------------------
# API: ANALYZE MEETING
# --------------------------------------------------
@app.post("/analyze-meeting")
async def analyze_meeting(file: UploadFile = File(...)):
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_meeting.webm")
    audio_path = os.path.join(STORAGE, filename)
    json_path = audio_path.replace(".webm", ".json")

    try:
        # Save audio
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Whisper STT
        print("Running Whisper STT...")
        stt_result = audio_engine.process_audio(audio_path)

        transcript = ""
        if stt_result and "text" in stt_result:
            transcript = stt_result["text"].strip()

        if len(transcript) < 20:
            transcript = (
                "Meeting discussion detected but speech was unclear or partially untranslated. "
                "Manual review is recommended."
            )

        # Generate MOM
        print("Generating MOM...")
        mom = generate_mom_from_transcript(transcript)

        response = {
            "meeting_id": filename,
            "audio_url": f"/storage/{filename}",
            "full_transcript": transcript,
            "mom": mom
        }

        # Persist meeting data
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(response, jf, ensure_ascii=False, indent=4)

        return response

    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------
# API: LIST MEETINGS
# --------------------------------------------------
@app.get("/meetings")
async def list_meetings():
    try:
        meetings = []
        files = sorted(os.listdir(STORAGE), reverse=True)

        for f in files:
            if not f.endswith(".webm"):
                continue

            json_path = os.path.join(STORAGE, f.replace(".webm", ".json"))

            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
            else:
                data = {
                    "meeting_id": f,
                    "audio_url": f"/storage/{f}",
                    "full_transcript": "",
                    "mom": None
                }

            meetings.append(data)

        return JSONResponse(content=meetings)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------
# LOCAL RUN
# --------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
