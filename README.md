# 🎙️ AI MOM System (Meeting Intelligence)

Welcome to the **AI MOM System**! This project is an intelligent Meeting Minutes (MOM) generator that automatically captures, transcribes, and analyzes your online meetings in real-time. It provides a comprehensive dashboard with speaker diarization, action item tracking, and meeting insights.

This system consists of two parts:
1. **Chrome Extension:** Captures meeting audio directly from the browser tab and tracks participant join/leave events.
2. **Python Backend:** A FastAPI server that processes the audio, performs transcription using Whisper, speaker diarization using Pyannote, and AI summarization using Groq/OpenAI.

---

## ✨ Features

- **Real-time Audio Capture:** Stream meeting audio seamlessly from Chrome (supports Google Meet, Zoom, MS Teams).
- **Live Transcription:** View live transcripts in the extension popup.
- **Speaker Diarization:** Identifies "who said what" and maps anonymous speaker labels to actual participant names.
- **AI Meeting Summaries (MOM):** Automatically extracts:
  - Key Discussions
  - Decisions
  - Action Items (with Owner and Deadline)
  - Topic Tags & Engagement Scores
- **Comprehensive Dashboard:** A beautiful, responsive UI to review the meeting summary, download PDFs, and view participant attendance logs.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed on your system:

1. **Python 3.10+**: [Download Python](https://www.python.org/downloads/)
2. **FFmpeg**: Required for audio processing.
   - *Windows:* Install via `winget install ffmpeg` or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add it to your System PATH.
   - *Mac:* `brew install ffmpeg`
   - *Linux:* `sudo apt install ffmpeg`
3. **Google Chrome** or any Chromium-based browser (Edge, Brave).

---

## 🚀 Installation & Setup

### Step 1: Set up the Backend (FastAPI Server)

1. Open your terminal and navigate to the `backend` folder:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   # Mac/Linux
   source venv/bin/activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure your API Keys:
   - Create a file named `.env` in the `backend` directory.
   - Add the following keys (you can get a free Groq key at [console.groq.com](https://console.groq.com/)):
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here  # Optional fallback
   STORAGE_DIR=./storage
   ```

5. Start the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```
   *The server should now be running at `http://127.0.0.1:8000`.*

---

### Step 2: Set up the Chrome Extension

1. Open Google Chrome and go to `chrome://extensions/`.
2. Turn on **Developer mode** (toggle switch in the top right corner).
3. Click the **Load unpacked** button.
4. Select the `extension` folder inside this project directory.
5. The **AI MOM** extension icon will appear in your browser toolbar. Pin it for easy access!

---

## 📖 How to Use

1. **Start the Backend:** Ensure your FastAPI backend terminal is running.
2. **Join a Meeting:** Open a web meeting (e.g., Google Meet) in a Chrome tab.
3. **Start Recording:**
   - Click the **AI MOM extension icon** in your toolbar.
   - Click **▶ Start Recording**. 
   - You will see a "Recording in progress..." status, and live transcripts will begin to appear as people speak.
4. **During the Meeting:** 
   - Keep the meeting tab active or the "Participants" panel open for the best participant tracking results.
5. **Stop & Analyze:**
   - When the meeting ends, click the extension icon again and click **⏹ Stop**.
   - The extension will say "⏳ Processing meeting...". Make sure the backend terminal is still running, as the AI is working heavily in the background.
6. **View Results:** 
   - Once processing finishes, a new tab will automatically open with your **Meeting Intelligence Dashboard**!
   - From here, you can read the MOM, check action items, and download a PDF report!

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| **"Failed to load audio: ffmpeg"** error in terminal | Ensure FFmpeg is installed and permanently added to your system's Environment Variables `PATH`. Restart your terminal after installing. |
| **Pyannote Clustering Hangs** | The audio might be perfectly silent. The system has built-in protections for silent audio, but ensure your microphone/tab audio isn't completely muted for the duration of the test. |
| **Participants not tracked in Google Meet** | Ensure you have the "People" (Participants) sidebar opened during the meeting at least occasionally so the DOM loads their names. |
| **Server out of Memory (OOM)** | Transcribing and Diarizing locally takes RAM. If your system runs out of memory, try closing heavy browser tabs while processing. |

---

## 📂 Project Structure

```
mom_system/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI endpoints
│   │   ├── streaming.py           # Real-time WebSocket audio processing
│   │   ├── ai_mom.py              # LLM Integration (Groq/OpenAI)
│   │   ├── audio_engine.py        # Whisper Speech-to-Text
│   │   ├── speaker_diarization.py # Pyannote Speaker recognition
│   │   └── ...                    # Other utilities
│   ├── requirements.txt
│   └── .env                       # Environment variables (Add your keys here)
│
└── extension/
    ├── manifest.json              # Chrome extension config
    ├── background.js              # Service worker (handles recording state & WebSockets)
    ├── popup.html / popup.js      # The extension interface
    ├── dashboard.html / .js       # Beautiful Results UI
    ├── offscreen.html / .js       # Handles Chrome Audio Capture via Offscreen Document
    └── meet_tracker.js            # Injects into Meet/Zoom to track participants
```

Enjoy your automated meeting notes! 🎉
