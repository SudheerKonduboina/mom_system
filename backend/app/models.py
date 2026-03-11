# app/models.py
# SQLAlchemy ORM models for persistent meeting data

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, JSON,
    ForeignKey, Boolean, Enum as SAEnum, create_engine
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), default="Untitled Meeting")
    platform = Column(String(50), default="google_meet")    # google_meet, zoom, teams, generic
    meet_date = Column(DateTime, default=datetime.utcnow)
    duration_sec = Column(Float, default=0)
    audio_url = Column(String(500))
    status = Column(String(50), default="queued")            # queued, processing, completed, failed
    language = Column(String(50), default="unknown")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transcript = relationship("Transcript", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    participants = relationship("Participant", back_populates="meeting", cascade="all, delete-orphan")
    mom_record = relationship("MOMRecord", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    speaker_segments = relationship("SpeakerSegment", back_populates="meeting", cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="meeting", cascade="all, delete-orphan")
    warnings = relationship("Warning", back_populates="meeting", cascade="all, delete-orphan")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(255), ForeignKey("meetings.meeting_id"), nullable=False)
    full_text = Column(Text, default="")
    speaker_labeled_text = Column(Text, default="")           # With speaker names
    language = Column(String(50), default="unknown")
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="transcript")


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(255), ForeignKey("meetings.meeting_id"), nullable=False)
    name = Column(String(255), nullable=False)
    speaker_id = Column(String(50))                           # Speaker_0, Speaker_1, etc.
    join_time = Column(DateTime)
    leave_time = Column(DateTime)
    duration_sec = Column(Float, default=0)
    speaking_time_sec = Column(Float, default=0)
    is_self = Column(Boolean, default=False)

    meeting = relationship("Meeting", back_populates="participants")


class MOMRecord(Base):
    __tablename__ = "mom_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(255), ForeignKey("meetings.meeting_id"), nullable=False)
    meeting_title = Column(String(500), default="Meeting Summary")
    date = Column(String(100), default="")
    participants = Column(JSON, default=list)
    agenda = Column(Text, default="Meeting Summary")
    summary = Column(Text, default="")
    duration = Column(String(50), default="0s")
    total_attendees = Column(Integer, default=0)
    attendance_log = Column(JSON, default=list)
    key_discussions = Column(JSON, default=list)
    decisions = Column(JSON, default=list)
    risks_followups = Column(JSON, default=list)
    conclusion = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="mom_record")


class SpeakerSegment(Base):
    __tablename__ = "speaker_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(255), ForeignKey("meetings.meeting_id"), nullable=False)
    speaker_name = Column(String(255), default="Unknown")
    speaker_id = Column(String(50))
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    text = Column(Text, default="")
    confidence = Column(Float, default=0)

    meeting = relationship("Meeting", back_populates="speaker_segments")


class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(255), ForeignKey("meetings.meeting_id"), nullable=False)
    task = Column(Text, nullable=False)
    owner = Column(String(255), default="TBD")
    deadline = Column(String(255), default="TBD")
    status = Column(String(20), default="Pending")            # Pending, In Progress, Completed, Overdue
    linked_meeting_id = Column(String(255))                   # Follow-up from which meeting
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    meeting = relationship("Meeting", back_populates="action_items")


class Warning(Base):
    __tablename__ = "warnings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String(255), ForeignKey("meetings.meeting_id"), nullable=False)
    level = Column(String(20), default="warning")             # warning, error
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="warnings")


class MeetingSeries(Base):
    __tablename__ = "meeting_series"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), default="Recurring Meeting")
    participant_hash = Column(String(64), index=True)         # Hash of sorted participant names
    frequency = Column(String(50))                            # daily, weekly, biweekly, monthly
    last_meeting_id = Column(String(255))
    meeting_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContextLink(Base):
    __tablename__ = "context_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_meeting_id = Column(String(255), nullable=False, index=True)
    target_meeting_id = Column(String(255), nullable=False)
    link_type = Column(String(50), default="follow_up")       # follow_up, continuation, reference
    created_at = Column(DateTime, default=datetime.utcnow)
