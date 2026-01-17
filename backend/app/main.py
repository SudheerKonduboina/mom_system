from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.audio_engine import AudioEngine
from app.nlp_processor import NLPProcessor
from datetime import datetime
import shutil
import os

app = FastAPI()

# 1. CORS Middleware - Essential for the Chrome Extension to talk to the server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Setup Storage Directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
storage_dir = os.path.join(base_dir, "storage")

if not os.path.exists(storage_dir):
    os.makedirs(storage_dir)

# 3. Mount the storage folder so files can be accessed via URL
app.mount("/storage", StaticFiles(directory=storage_dir), name="storage")

# 4. Initialize Engines
audio_engine = AudioEngine()
nlp_processor = NLPProcessor()

# --- NEW ENDPOINT: GET HISTORY ---
@app.get("/meetings")
async def get_meetings():
    """Returns a list of all saved .webm meeting files."""
    try:
        files = os.listdir(storage_dir)
        # Filter only .webm files and sort by newest first (date-based filename)
        meeting_files = sorted([f for f in files if f.endswith(".webm")], reverse=True)
        return {"meetings": meeting_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not retrieve history: {str(e)}")

# --- EXISTING ENDPOINT: ANALYZE MEETING ---
@app.post("/analyze-meeting")
async def analyze_meeting(file: UploadFile = File(...)):
    # Create a Unique Name using Date and Time
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    unique_filename = f"{timestamp}_meeting.webm"
    temp_path = os.path.join(storage_dir, unique_filename)
    
    try:
        # 5. Save the incoming audio permanently
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(temp_path)
        print(f"--- Recording Saved Permanently ---")
        print(f"File Path: {temp_path}")
        print(f"File Size: {file_size} bytes")

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Received empty audio file")

        # 6. Step 1: Speech-to-Text (STT) via Whisper
        print("Processing Speech-to-Text...")
        transcript_data = audio_engine.process_audio(temp_path)
        
        # 7. Step 2: NLP Intelligence Extraction (MOM)
        print("Extracting Action Items and Summary...")
        intel_data = nlp_processor.extract_intel(transcript_data)

        # 8. Return the full intelligence package
        return {
            "meeting_id": unique_filename, 
            "audio_url": f"/storage/{unique_filename}", 
            "summary": intel_data.get("summary", "No summary generated"),
            "action_items": intel_data.get("action_items", []),
            "transcript": transcript_data,
            "clarity_score": intel_data.get("clarity_score", 0.0)
        }

    except Exception as e:
        print(f"CRITICAL SYSTEM ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Backend Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)