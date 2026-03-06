# AI Minutes of Meeting (MOM) System

An intelligent Chrome Extension paired with a FastAPI backend that captures tab audio, transcribes speech using OpenAI's Whisper, and extracts action items and summaries automatically.

# Project Status: Alpha (Core Functionality Complete)
Tab Audio Capture	✅ Complete	Captures system/tab audio via Chrome Offscreen API.
Backend Transmission	✅ Complete	Streams audio blobs from Extension to FastAPI server.
Backend Transmission	✅ Complete	Streams audio blobs from Extension to FastAPI server.
Speech-to-Text	✅ Complete	Transcription via OpenAI Whisper (Base Model).
MOM Intelligence	✅ Complete	Regex-based extraction of Action Items & Summaries.
User Dashboard	✅ Complete	Live status updates and display of results in the popup.
History System	⏳ In Progress	Backend API is ready; UI integration is pending.

# System Architecture
Chrome Extension (Frontend): Handles the user interface and captures the raw audio stream from the active tab.
Offscreen Document: A hidden browser page that records the audio and converts it into a transferable data format.
FastAPI (Backend): Receives the audio, saves it to the disk, and runs the AI pipeline.
AI Pipeline: Whisper STT converts audio to text $\rightarrow$ NLP Processor extracts MOM data.

# How to Run the System

1. Prerequisites
Python 3.9+, FFmpeg: Required by Whisper for audio processing. Ensure it is added to your system PATH., Google Chrome Browser.

2. Backend Setup
cd mom_system/backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

Install dependencies: pip install fastapi uvicorn openai-whisper torch

Start the server: python -m uvicorn app.main:app --reload

The server will be live at http://127.0.0.1:8000.

3. Extension SetupOpen Chrome and navigate to chrome://extensions/.Enable Developer Mode (top right toggle).Click Load unpacked.Select the extension folder from your project directory.🛠️ Usage InstructionsOpen any tab with audio (e.g., a YouTube video or a Google Meet).Click the AI MOM icon in your Chrome toolbar.Click Start Recording. (A red pulse will blink to indicate active recording).Click Stop & Generate MOM.Wait for the status to change from "Processing..." to "Analysis Complete!".View your summary and action items directly in the popup.Check backend/storage/ to find the permanent audio file of the session.

4. 📂 File StructurePlaintextmom_system/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI Routes & Storage Config
│   │   ├── audio_engine.py    # Whisper STT Logic
│   │   └── nlp_processor.py    # Regex MOM Extraction
|   |   |__ ai_mom.py
|   |   |__ mom_generator.py
|   |   |__ Schema.py
|   |   |__ utile.py                     
│   ├── storage/               # PERMANENT AUDIO FILES (.webm)
│   └── venv/           # Python Environment    
|   |__ .env    
|   |__ requirement.txt           
└── extension/
|   ├── manifest.json          # Extension Permissions
|   ├── popup.html/js          # User Interface
|   ├── background.js          # Orchestrator (Service Worker)
|   └── offscreen.html/js 
|   |__ dashboard.html     
|   |__ dashboard.js
|   |__extension/html2pdf.bundle.min.js
|   |__ meet_tracker.js
|
|__ .gitignore
|__ readme.md


📝 TroubleshootingTranscription is slow: Whisper runs on your CPU by default. For faster results, ensure you have an NVIDIA GPU with CUDA installed."No Audio" error: Ensure you have selected the "Share Audio" checkbox if Chrome prompts you when capturing the tab.404/Connection Error: Ensure the FastAPI server is running before clicking "Stop" in the extension.
