# app/database.py
# Database engine, session management, and CRUD helpers

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, select, update, delete
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import (
    Base, Meeting, Transcript, Participant, MOMRecord,
    SpeakerSegment, ActionItem, Warning, MeetingSeries, ContextLink
)

# ---------------------------------------------------------------------------
# Engine & Session  (sync for simplicity with Whisper; async-ready structure)
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(settings.STORAGE_DIR, "meetings.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    """Create all tables if they don't exist."""
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get a database session."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


# ---------------------------------------------------------------------------
# Meeting CRUD
# ---------------------------------------------------------------------------

def create_meeting(meeting_id: str, platform: str = "google_meet",
                   audio_url: str = "", title: str = "Untitled Meeting") -> Meeting:
    db = get_db()
    try:
        meeting = Meeting(
            meeting_id=meeting_id,
            title=title,
            platform=platform,
            audio_url=audio_url,
            status="queued",
            meet_date=datetime.utcnow(),
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        return meeting
    finally:
        db.close()


def update_meeting_status(meeting_id: str, status: str, **kwargs):
    db = get_db()
    try:
        meeting = db.query(Meeting).filter(Meeting.meeting_id == meeting_id).first()
        if meeting:
            meeting.status = status
            for key, value in kwargs.items():
                if hasattr(meeting, key):
                    setattr(meeting, key, value)
            db.commit()
    finally:
        db.close()


def get_meeting(meeting_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        meeting = db.query(Meeting).filter(Meeting.meeting_id == meeting_id).first()
        if not meeting:
            return None
        return _meeting_to_dict(db, meeting)
    finally:
        db.close()


def list_meetings(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    db = get_db()
    try:
        meetings = (
            db.query(Meeting)
            .order_by(Meeting.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_meeting_to_dict(db, m) for m in meetings]
    finally:
        db.close()


def delete_meeting(meeting_id: str) -> bool:
    db = get_db()
    try:
        meeting = db.query(Meeting).filter(Meeting.meeting_id == meeting_id).first()
        if meeting:
            db.delete(meeting)
            db.commit()
            return True
        return False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Transcript CRUD
# ---------------------------------------------------------------------------

def save_transcript(meeting_id: str, full_text: str,
                    speaker_labeled_text: str = "", language: str = "unknown"):
    db = get_db()
    try:
        transcript = Transcript(
            meeting_id=meeting_id,
            full_text=full_text,
            speaker_labeled_text=speaker_labeled_text,
            language=language,
            word_count=len(full_text.split()),
        )
        db.add(transcript)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Participants CRUD
# ---------------------------------------------------------------------------

def save_participants(meeting_id: str, participants: List[Dict]):
    db = get_db()
    try:
        for p in participants:
            participant = Participant(
                meeting_id=meeting_id,
                name=p.get("name", "Unknown"),
                speaker_id=p.get("speaker_id"),
                join_time=p.get("join_time"),
                leave_time=p.get("leave_time"),
                duration_sec=p.get("duration_sec", 0),
                speaking_time_sec=p.get("speaking_time_sec", 0),
            )
            db.add(participant)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# MOM CRUD
# ---------------------------------------------------------------------------

def save_mom(meeting_id: str, mom_data: Dict[str, Any]):
    db = get_db()
    try:
        mom = MOMRecord(
            meeting_id=meeting_id,
            meeting_title=mom_data.get("meeting_title", "Meeting Summary"),
            date=mom_data.get("date", datetime.now().strftime("%Y-%m-%d")),
            participants=mom_data.get("participants", []),
            agenda=mom_data.get("agenda", "Meeting Summary"),
            summary=mom_data.get("summary", ""),
            duration=mom_data.get("duration", "0s"),
            total_attendees=mom_data.get("total_attendees", 0),
            attendance_log=mom_data.get("attendance_log", []),
            key_discussions=mom_data.get("key_discussions", []),
            decisions=mom_data.get("decisions", []),
            risks_followups=mom_data.get("risks_followups", []),
            conclusion=mom_data.get("conclusion", ""),
        )
        db.add(mom)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Action Items CRUD
# ---------------------------------------------------------------------------

def save_action_items(meeting_id: str, items: List[Dict]):
    db = get_db()
    try:
        for item in items:
            ai = ActionItem(
                meeting_id=meeting_id,
                task=item.get("task", ""),
                owner=item.get("owner", "TBD"),
                deadline=item.get("deadline", "TBD"),
                status=item.get("status", "Pending")
            )
            db.add(ai)
        db.commit()
    finally:
        db.close()


def get_action_items(status: str = None, owner: str = None,
                     meeting_id: str = None) -> List[Dict]:
    db = get_db()
    try:
        query = db.query(ActionItem)
        if status:
            query = query.filter(ActionItem.status == status)
        if owner:
            query = query.filter(ActionItem.owner.ilike(f"%{owner}%"))
        if meeting_id:
            query = query.filter(ActionItem.meeting_id == meeting_id)
        items = query.order_by(ActionItem.created_at.desc()).all()
        return [
            {
                "id": a.id, "meeting_id": a.meeting_id, "task": a.task,
                "owner": a.owner, "deadline": a.deadline,
                "status": a.status, "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in items
        ]
    finally:
        db.close()


def update_action_item(item_id: int, **kwargs) -> bool:
    db = get_db()
    try:
        item = db.query(ActionItem).filter(ActionItem.id == item_id).first()
        if not item:
            return False
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        if kwargs.get("status") == "completed":
            item.completed_at = datetime.utcnow()
        db.commit()
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Speaker Segments CRUD
# ---------------------------------------------------------------------------

def save_speaker_segments(meeting_id: str, segments: List[Dict]):
    db = get_db()
    try:
        for seg in segments:
            ss = SpeakerSegment(
                meeting_id=meeting_id,
                speaker_name=seg.get("speaker_name", "Unknown"),
                speaker_id=seg.get("speaker_id"),
                start_time=seg.get("start", 0),
                end_time=seg.get("end", 0),
                text=seg.get("text", ""),
                confidence=seg.get("confidence", 0),
            )
            db.add(ss)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Warnings CRUD
# ---------------------------------------------------------------------------

def save_warnings(meeting_id: str, warnings: List[Dict]):
    db = get_db()
    try:
        for w in warnings:
            warning = Warning(
                meeting_id=meeting_id,
                level=w.get("level", "warning"),
                message=w.get("message", ""),
            )
            db.add(warning)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _meeting_to_dict(db: Session, meeting: Meeting) -> Dict[str, Any]:
    """Convert a Meeting ORM object to a full dict with related data."""
    result = {
        "meeting_id": meeting.meeting_id,
        "title": meeting.title,
        "platform": meeting.platform,
        "meet_date": meeting.meet_date.isoformat() if meeting.meet_date else None,
        "duration_sec": meeting.duration_sec,
        "audio_url": meeting.audio_url,
        "status": meeting.status,
        "language": meeting.language,
        "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
    }

    # Transcript
    t = db.query(Transcript).filter(Transcript.meeting_id == meeting.meeting_id).first()
    if t:
        result["full_transcript"] = t.full_text
        result["speaker_transcript"] = t.speaker_labeled_text
        result["word_count"] = t.word_count

    # MOM
    mom = db.query(MOMRecord).filter(MOMRecord.meeting_id == meeting.meeting_id).first()
    if mom:
        result["mom"] = {
            "meeting_title": mom.meeting_title,
            "date": mom.date,
            "participants": mom.participants,
            "agenda": mom.agenda,
            "summary": mom.summary,
            "duration": mom.duration,
            "total_attendees": mom.total_attendees,
            "attendance_log": mom.attendance_log,
            "key_discussions": mom.key_discussions,
            "decisions": mom.decisions,
            "risks_followups": mom.risks_followups,
            "conclusion": mom.conclusion
        }

    # Participants
    parts = db.query(Participant).filter(Participant.meeting_id == meeting.meeting_id).all()
    result["participants"] = [
        {"name": p.name, "speaker_id": p.speaker_id,
         "join_time": p.join_time.isoformat() if p.join_time else None,
         "leave_time": p.leave_time.isoformat() if p.leave_time else None,
         "duration_sec": p.duration_sec, "speaking_time_sec": p.speaking_time_sec}
        for p in parts
    ]

    # Action items
    actions = db.query(ActionItem).filter(ActionItem.meeting_id == meeting.meeting_id).all()
    result["action_items"] = [
        {"id": a.id, "task": a.task, "owner": a.owner, "deadline": a.deadline,
         "status": a.status}
        for a in actions
    ]

    # Warnings
    warns = db.query(Warning).filter(Warning.meeting_id == meeting.meeting_id).all()
    result["warnings"] = [{"level": w.level, "message": w.message} for w in warns]

    return result
