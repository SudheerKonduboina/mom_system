# --- ADDED MONKEY PATCH FOR TORCHAUDIO COMPATIBILITY ---
import torchaudio
try:
    if not hasattr(torchaudio, 'set_audio_backend'):
        torchaudio.set_audio_backend = lambda x: None
except ImportError:
    pass
# -----------------------------------------------------

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.audio_engine import AudioEngine
from app.nlp_processor import NLPProcessor
from datetime import datetime
import shutil
import os
from pyannote.audio import Pipeline  # Intern A requirement
from dotenv import load_dotenv # New Import

# Load the variables from .env
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

app = FastAPI()

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Setup Storage Directory
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file_path))
storage_dir = os.path.join(project_root, "storage")

if not os.path.exists(storage_dir):
    os.makedirs(storage_dir)

# 3. Mount storage
app.mount("/storage", StaticFiles(directory=storage_dir), name="storage")

# 4. Initialize Engines
audio_engine = AudioEngine()
nlp_processor = NLPProcessor()

# Initialize Diarization Pipeline (Intern A)
# Now uses the safe HF_TOKEN variable loaded from .env
try:
    diarization_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization", 
        use_auth_token=HF_TOKEN 
    )
except Exception as e:
    print(f"Diarization Startup Warning: {e}")
    diarization_pipeline = None

@app.get("/meetings")
async def get_meetings():
    try:
        files = os.listdir(storage_dir)
        meeting_files = sorted([f for f in files if f.endswith(".webm")], reverse=True)
        return {"meetings": meeting_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-meeting")
async def analyze_meeting(file: UploadFile = File(...)):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    unique_filename = f"{timestamp}_meeting.webm"
    temp_path = os.path.join(storage_dir, unique_filename)
    
    try:
        # 5. Save the file
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(temp_path)
        print(f"--- Audio Received: {file_size} bytes ---")

        if file_size < 100:
            raise HTTPException(status_code=400, detail="Audio file too small or empty")

        # 6. Speech-to-Text
        print("Running Whisper STT...")
        transcript_result = audio_engine.process_audio(temp_path)
        
        # 7. Speaker Diarization Logic (Intern A - Merged)
        attributed_transcript = ""
        raw_text = ""
        
        # Extract segments/text from Whisper result
        if isinstance(transcript_result, dict):
            segments = transcript_result.get("segments", [])
            raw_text = transcript_result.get("text", "")
            
            # If Diarization is available, merge speaker labels with segments
            if diarization_pipeline and segments:
                print("Running Speaker Diarization...")
                diarization = diarization_pipeline(temp_path)
                
                for segment in segments:
                    start = segment['start']
                    stop = segment['end']
                    text = segment['text']
                    
                    # Find which speaker was talking during this time segment
                    speaker = "Unknown"
                    for turn, _, speaker_label in diarization.itertracks(yield_label=True):
                        if turn.start <= start <= turn.end:
                            speaker = speaker_label
                            break
                    attributed_transcript += f"Speaker {speaker}: {text}\n"
            else:
                attributed_transcript = raw_text
        else:
            raw_text = str(transcript_result)
            attributed_transcript = raw_text

        print(f"DEBUG: Extracted Transcript Length: {len(raw_text)} characters")

        # 8. AI Intelligence Extraction
        print("Running AI Intelligence Extraction...")
        # Use the speaker-attributed transcript for better intelligence
        intel_data = nlp_processor.extract_intel(attributed_transcript)

        # 9. Final Return Object
        return {
            "meeting_id": unique_filename, 
            "audio_url": f"/storage/{unique_filename}", 
            "full_transcript": attributed_transcript, 
            "summary": intel_data.get("summary", ""),
            "agenda": intel_data.get("agenda", ""),
            "key_discussions": intel_data.get("key_discussions", ""),
            "decisions": intel_data.get("decisions", []), 
            "action_items": intel_data.get("action_items", []),
            "risks": intel_data.get("risks", ""),
            "conclusion": intel_data.get("conclusion", ""),
            "participants": intel_data.get("participants", []),
            "clarity_score": intel_data.get("clarity_score", 0.0)
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)