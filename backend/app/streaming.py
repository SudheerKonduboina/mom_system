# app/streaming.py
# WebSocket endpoint for real-time audio streaming and live transcription

import asyncio
import io
import json
import logging
import tempfile
import time
from typing import List

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger("Streaming")


class StreamingSession:
    """Manages a single real-time audio streaming session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.chunks: List[bytes] = []
        self.partial_transcripts: List[str] = []
        self.full_transcript = ""
        self.chunk_count = 0
        self.start_time = time.time()
        self.is_active = True

    def add_chunk(self, data: bytes):
        self.chunks.append(data)
        self.chunk_count += 1

    def get_accumulated_audio(self) -> bytes:
        return b"".join(self.chunks)

    @property
    def duration_sec(self) -> float:
        return time.time() - self.start_time


async def handle_stream(websocket: WebSocket):
    """
    WebSocket handler for real-time audio streaming.

    Protocol:
    - Client connects and sends binary audio chunks (3-5s webm)
    - Server responds with partial transcript JSON
    - Client sends text message "STOP" to end session
    - Server responds with final full transcript
    """
    await websocket.accept()
    session_id = f"stream_{int(time.time())}"
    session = StreamingSession(session_id)

    logger.info(f"Streaming session started: {session_id}")

    try:
        # Lazy imports for heavy modules
        from app.model_manager import model_manager
        from app.live_speaker_detector import LiveSpeakerDetector

        speaker_detector = LiveSpeakerDetector()

        while session.is_active:
            try:
                # Wait for data with timeout (heartbeat)
                message = await asyncio.wait_for(
                    websocket.receive(), timeout=30.0
                )
            except asyncio.TimeoutError:
                # Send heartbeat
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"type": "heartbeat"})
                continue

            # Text message (control commands)
            if "text" in message:
                text = message["text"]
                if text == "STOP":
                    session.is_active = False
                    logger.info(f"Session {session_id} stopped by client")
                    break
                elif text == "PING":
                    await websocket.send_json({"type": "pong"})
                    continue

            # Binary message (audio chunk)
            if "bytes" in message:
                chunk_data = message["bytes"]
                session.add_chunk(chunk_data)

                # Process chunk in background
                partial = await _process_chunk(
                    chunk_data, session, speaker_detector
                )

                if partial and websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(partial)

        # Session ended — send final response
        if websocket.client_state == WebSocketState.CONNECTED:
            session.full_transcript = " ".join(session.partial_transcripts)
            await websocket.send_json({
                "type": "session_complete",
                "session_id": session_id,
                "full_transcript": session.full_transcript,
                "chunks_processed": session.chunk_count,
                "duration_sec": round(session.duration_sec, 2),
            })

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        session.is_active = False
        logger.info(f"Session closed: {session_id} ({session.chunk_count} chunks)")


async def _process_chunk(chunk_data: bytes, session: StreamingSession,
                          speaker_detector) -> dict | None:
    """Process a single audio chunk: transcribe and detect speaker changes."""
    try:
        # Save accumulated audio to temp file for Whisper
        full_audio = session.get_accumulated_audio()
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(full_audio)
            tmp_path = tmp.name

        import subprocess
        import os

        # Get total duration of accumulated audio
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
             "-of", "default=noprint_wrappers=1:nokey=1", tmp_path],
            capture_output=True, text=True
        )
        try:
            total_duration = float(probe.stdout.strip())
        except ValueError:
            total_duration = 0.0

        processed_time = getattr(session, "processed_time", 0.0)
        wav_path = tmp_path + ".wav"

        if total_duration > processed_time:
            # Extract new chunk using ffmpeg
            cmd = [
                "ffmpeg", "-y", "-ss", str(processed_time), "-i", tmp_path,
                "-ar", "16000", "-ac", "1", wav_path
            ]
            subprocess.run(cmd, capture_output=True)
            session.processed_time = total_duration
        else:
            os.unlink(tmp_path)
            return None

        # Transcribe in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        transcript = await loop.run_in_executor(
            None, _transcribe_chunk, wav_path
        )

        if not transcript or len(transcript.strip()) < 3:
            try:
                os.unlink(tmp_path)
                os.unlink(wav_path)
            except:
                pass
            return None

        session.partial_transcripts.append(transcript)

        # Speaker change detection
        speaker_info = {"is_speaking": True, "current_speaker": "Speaker"}
        try:
            import librosa
            audio, sr = librosa.load(wav_path, sr=16000, mono=True)
            speaker_info = speaker_detector.detect_speaker_change(audio, sr)
        except Exception:
            pass

        # Clean up temp files
        try:
            os.unlink(tmp_path)
            os.unlink(wav_path)
        except Exception:
            pass

        return {
            "type": "partial_transcript",
            "text": transcript,
            "chunk_number": session.chunk_count,
            "speaker": speaker_info.get("current_speaker", "Speaker"),
            "speaker_changed": speaker_info.get("speaker_changed", False),
            "timestamp": round(session.duration_sec, 2),
        }

    except Exception as e:
        logger.warning(f"Chunk processing failed: {e}")
        return None


def _transcribe_chunk(audio_path: str) -> str:
    """Transcribe a single audio chunk using Whisper (runs in thread)."""
    try:
        from app.model_manager import model_manager

        model = model_manager.get_whisper()
        result = model.transcribe(
            audio_path,
            task="translate",
            language=None,
            verbose=False,
            temperature=0.0,
            fp16=False,
        )
        return (result.get("text", "") or "").strip()
    except Exception as e:
        logger.error(f"Chunk transcription error: {e}")
        return ""
