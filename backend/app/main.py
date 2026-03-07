# app/main.py
# AI Meeting Intelligence Backend — Full Pipeline
# Integrates: preprocessing, transcription, diarization, speaker mapping,
# insights, context memory, action tracking, error detection, task queue, streaming

try:
    import torchaudio
    if not hasattr(torchaudio, "set_audio_backend"):
        torchaudio.set_audio_backend = lambda x: None
except ImportError:
    torchaudio = None
except Exception:
    torchaudio = None

import os
import json
import logging
import shutil
import traceback
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.config import settings
from app.auth_middleware import AuthMiddleware, validate_upload

# Safe imports for optional modules
try:
    from app.ai_mom import ai_generate_mom
except Exception:
    ai_generate_mom = None

try:
    from app.audio_engine import AudioEngine
except Exception as e:
    print(f"WARNING: AudioEngine unavailable: {e}")
    AudioEngine = None

try:
    from app.nlp_processor import NLPProcessor
except Exception as e:
    print(f"WARNING: NLPProcessor unavailable: {e}")
    NLPProcessor = None

try:
    from app.speaker_diarization import SpeakerDiarizer
except Exception:
    SpeakerDiarizer = None

try:
    from app.speaker_mapper import SpeakerMapper
except Exception:
    SpeakerMapper = None

try:
    from app.meeting_insights import MeetingInsightsEngine
except Exception:
    MeetingInsightsEngine = None

from app.error_detection import detect_errors
from app.context_memory import ContextMemory
from app.action_tracker import ActionTracker
from app.task_queue import task_queue

try:
    from app.streaming import handle_stream
except Exception:
    handle_stream = None

import app.database as db_module

# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
app = FastAPI(title="MOM Intelligence Backend", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Auth middleware (only enforced if API_SECRET_KEY is set)
app.add_middleware(AuthMiddleware)

# ---------------------------------------------------------------------------
# STORAGE & DB
# ---------------------------------------------------------------------------
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.STORAGE_DIR), name="storage")

# Initialize database tables
db_module.init_db()

@app.on_event("startup")
async def startup_event():
    """Pre-load models on startup to speed up first request."""
    from app.model_manager import model_manager
    import asyncio
    
    def load():
        try:
            logger.info("Startup pre-loading: Whisper")
            model_manager.get_whisper()
            logger.info("Startup pre-loading: Diarizer")
            model_manager.get_diarizer()
        except Exception as e:
            print(f"Startup pre-load warning: {e}")

    # Run in thread to not block startup if slow
    asyncio.get_event_loop().run_in_executor(None, load)


# ---------------------------------------------------------------------------
# ENGINES (lazy-initialized via ModelManager)
# ---------------------------------------------------------------------------
audio_engine = AudioEngine() if AudioEngine else None
nlp_engine = NLPProcessor() if NLPProcessor else None
diarizer = SpeakerDiarizer() if SpeakerDiarizer else None
speaker_mapper = SpeakerMapper() if SpeakerMapper else None
insights_engine = MeetingInsightsEngine() if MeetingInsightsEngine else None
context_memory = ContextMemory()
action_tracker = ActionTracker()

# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    from app.model_manager import model_manager
    metrics = model_manager.get_performance_metrics()
    
    # If not loaded, trigger initialization (will happen in background if already running)
    if not metrics["whisper_loaded"] or not metrics["diarizer_loaded"]:
        # We don't block here, but we ensure the loading is triggered
        model_manager.get_whisper()
        model_manager.get_diarizer()
        metrics = model_manager.get_performance_metrics()

    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        "models": metrics,
    }

# ---------------------------------------------------------------------------
# WEBSOCKET: Real-time streaming
# ---------------------------------------------------------------------------
if handle_stream:
    @app.websocket("/ws/stream-audio")
    async def websocket_stream(websocket: WebSocket):
        await handle_stream(websocket)

# ---------------------------------------------------------------------------
# API: ANALYZE MEETING (async with task queue)
# ---------------------------------------------------------------------------
@app.post("/analyze-meeting")
async def analyze_meeting(
    file: UploadFile = File(...),
    attendance_events: str | None = Form(None),
    platform: str | None = Form("google_meet"),
):
    # Input validation
    file_errors = validate_upload(file.filename or "", file.size or 0)
    if file_errors:
        raise HTTPException(status_code=400, detail="; ".join(file_errors))

    meeting_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_meeting.webm")
    audio_path = os.path.join(settings.STORAGE_DIR, meeting_id)
    json_path = audio_path.replace(".webm", ".json")

    # Parse attendance
    attendance = []
    if attendance_events:
        try:
            attendance = json.loads(attendance_events)
            if not isinstance(attendance, list):
                attendance = []
        except Exception:
            attendance = []

    # Save audio file
    try:
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {e}")

    # Create meeting in database
    db_module.create_meeting(
        meeting_id=meeting_id,
        platform=platform or "google_meet",
        audio_url=f"/storage/{meeting_id}",
    )

    # Process synchronously (or use task queue for async)
    try:
        result = _process_meeting(meeting_id, audio_path, attendance, platform)

        # Save result as JSON for backward compatibility
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(result, jf, ensure_ascii=False, indent=4)

        return result

    except Exception as e:
        traceback.print_exc()
        db_module.update_meeting_status(meeting_id, "failed")
        raise HTTPException(status_code=500, detail=str(e))


def _process_meeting(meeting_id: str, audio_path: str,
                     attendance: list, platform: str = "google_meet") -> dict:
    """Full meeting processing pipeline."""
    db_module.update_meeting_status(meeting_id, "processing")

    all_warnings = []

    # ─── Step 1: Transcription (with preprocessing) ─────────────
    stt_result = audio_engine.process_audio(audio_path)

    transcript = ""
    whisper_segments = []
    audio_quality = 50

    if stt_result:
        transcript = (stt_result.get("text") or "").strip()
        whisper_segments = stt_result.get("segments", [])
        preprocess_info = stt_result.get("preprocessing", {})
        audio_quality = preprocess_info.get("quality_score", 50)
        all_warnings.extend(preprocess_info.get("warnings", []))

    if len(transcript) < 20:
        transcript = (
            "Meeting discussion detected but speech was unclear or partially untranslated. "
            "Manual review is recommended."
        )

    # ─── Step 2: Speaker Diarization ────────────────────────────
    if not whisper_segments or len(transcript.strip()) < 5:
        # Skip diarization if there is no speech or transcript is extremely short
        logger.warning(f"Skipping diarization for {meeting_id} due to lack of speech.")
        diarization_segments = []
        aligned_segments = []
        speaking_times = {}
        speaker_transcript = transcript
    else:
        processed_audio_path = stt_result.get("preprocessing", {}).get("processed_path", audio_path)
        diarization_segments = diarizer.diarize(processed_audio_path)
        aligned_segments = diarizer.align_with_transcript(diarization_segments, whisper_segments)
        speaking_times = diarizer.get_speaking_times(aligned_segments)
        speaker_transcript = diarizer.build_speaker_transcript(aligned_segments)

    # ─── Step 3: Speaker Name Mapping ───────────────────────────
    speaker_ids = list(set(s.get("speaker", "") for s in aligned_segments if s.get("speaker")))
    participant_names = list(set(
        e.get("name", "") for e in attendance
        if e.get("name") and e.get("type") == "PARTICIPANT_JOIN"
    ))

    speaker_map = speaker_mapper.map_speakers(
        speaker_ids, participant_names, aligned_segments, attendance
    )
    aligned_segments = speaker_mapper.apply_mapping(aligned_segments, speaker_map)
    # Rebuild transcript with real names
    speaker_transcript = diarizer.build_speaker_transcript(aligned_segments)

    # Update speaking_times with real names
    real_speaking_times = {}
    for sid, secs in speaking_times.items():
        real_name = speaker_map.get(sid, sid)
        real_speaking_times[real_name] = real_speaking_times.get(real_name, 0) + secs
    speaking_times = real_speaking_times

    # Merge participants from attendance + speaker detection
    all_participants = set(participant_names)
    all_participants.update(speaker_map.values())
    all_participants = sorted(p for p in all_participants if p and not p.startswith("Speaker_"))

    # ─── Step 4: Context Memory ─────────────────────────────────
    context = context_memory.get_context_for_meeting(
        list(all_participants), meeting_id
    )

    # ─── Step 5: MOM Generation ─────────────────────────────────
    combined_transcript = speaker_transcript if speaker_transcript else transcript

    if ai_generate_mom is not None:
        mom = ai_generate_mom(combined_transcript, context_prompt=context.get("context_prompt", ""))
    else:
        mom = nlp_engine.extract_intel(combined_transcript)

    # Ensure participants are populated
    if not mom.get("participants") or mom["participants"] == []:
        mom["participants"] = list(all_participants)

    # ─── Step 6: Meeting Insights ───────────────────────────────
    num_speakers = len(speaker_ids) or len(all_participants)
    duration = stt_result.get("metadata", {}).get("duration", 0) if stt_result else 0

    insights = insights_engine.analyze(
        combined_transcript, speaking_times, num_speakers, duration
    )

    # Merge AI sentiment/topics if available
    if mom.get("sentiment"):
        insights["sentiment"] = {"overall": mom["sentiment"], "score": 0.5}
    if mom.get("topics_detected"):
        insights["topics"] = mom["topics_detected"]

    # ─── Step 7: Action Item Tracking ───────────────────────────
    action_items = mom.get("action_items", [])
    enriched_actions = action_tracker.process_new_actions(
        meeting_id, action_items, context.get("pending_action_items", [])
    )

    # ─── Step 8: Error Detection ────────────────────────────────
    detection_warnings = detect_errors(
        transcript=transcript,
        mom=mom,
        audio_quality_score=audio_quality,
        whisper_segments=whisper_segments
    )
    all_warnings.extend(detection_warnings)

    # ─── Step 9: Persist to Database ────────────────────────────
    duration_sec = stt_result.get("metadata", {}).get("duration", 0) if stt_result else 0
    language = stt_result.get("metadata", {}).get("language", "unknown") if stt_result else "unknown"

    db_module.update_meeting_status(
        meeting_id, "completed",
        duration_sec=duration_sec, language=language
    )
    db_module.save_transcript(meeting_id, transcript, speaker_transcript, language)
    db_module.save_participants(meeting_id, [
        {"name": n, "speaker_id": next((k for k, v in speaker_map.items() if v == n), None)}
        for n in all_participants
    ])
    db_module.save_mom(meeting_id, {**mom, **insights})
    db_module.save_speaker_segments(meeting_id, aligned_segments)
    if all_warnings:
        db_module.save_warnings(meeting_id, all_warnings)

    # Update context memory for future meetings
    context_memory.update_after_meeting(
        meeting_id, list(all_participants), insights.get("topics", [])
    )

    # ─── Build Response ─────────────────────────────────────────
    response = {
        "meeting_id": meeting_id,
        "audio_url": f"/storage/{meeting_id}",
        "platform": platform,
        "full_transcript": transcript,
        "speaker_transcript": speaker_transcript,
        "speaker_map": speaker_map,
        "participants": list(all_participants),
        "attendance_events": attendance,
        "mom": mom,
        "insights": insights,
        "action_items": enriched_actions,
        "warnings": all_warnings,
        "context": {
            "is_recurring": context.get("is_recurring", False),
            "series_name": context.get("series_name"),
            "pending_from_previous": context.get("pending_action_items", []),
        },
    }

    return response

# ---------------------------------------------------------------------------
# API: LIST MEETINGS (from database)
# ---------------------------------------------------------------------------
@app.get("/meetings")
async def list_meetings(limit: int = 50, offset: int = 0):
    try:
        meetings = db_module.list_meetings(limit=limit, offset=offset)
        return JSONResponse(content=meetings)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------------------------
# API: GET SINGLE MEETING
# ---------------------------------------------------------------------------
@app.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: str):
    meeting = db_module.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting

# ---------------------------------------------------------------------------
# API: DELETE MEETING
# ---------------------------------------------------------------------------
@app.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str):
    if db_module.delete_meeting(meeting_id):
        return {"status": "deleted", "meeting_id": meeting_id}
    raise HTTPException(status_code=404, detail="Meeting not found")

# ---------------------------------------------------------------------------
# API: MEETING STATUS (for async processing)
# ---------------------------------------------------------------------------
@app.get("/meeting-status/{meeting_id}")
async def meeting_status(meeting_id: str):
    status = task_queue.get_status(meeting_id)
    if status:
        return status
    # Check database
    meeting = db_module.get_meeting(meeting_id)
    if meeting:
        return {"task_id": meeting_id, "status": meeting.get("status", "unknown")}
    raise HTTPException(status_code=404, detail="Meeting not found")

# ---------------------------------------------------------------------------
# API: ACTION ITEMS
# ---------------------------------------------------------------------------
@app.get("/action-items")
async def list_action_items(status: str = None, owner: str = None):
    items = db_module.get_action_items(status=status, owner=owner)
    return items

@app.patch("/action-items/{item_id}")
async def patch_action_item(item_id: int, status: str = None, priority: str = None):
    updates = {}
    if status:
        updates["status"] = status
    if priority:
        updates["priority"] = priority
    if db_module.update_action_item(item_id, **updates):
        return {"status": "updated", "id": item_id}
    raise HTTPException(status_code=404, detail="Action item not found")

@app.get("/action-items/overdue")
async def overdue_items():
    return action_tracker.check_overdue()

@app.get("/action-items/summary")
async def action_summary(owner: str):
    return action_tracker.get_summary_for_owner(owner)

# ---------------------------------------------------------------------------
# LOCAL RUN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
