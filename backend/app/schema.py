from pydantic import BaseModel
from typing import List, Optional

class MeetingSegment(BaseModel):
    start: float
    end: float
    speaker_id: str
    text: str

class ActionItem(BaseModel):
    task: str
    owner: Optional[str]
    deadline: Optional[str]
    priority: str

class MOMResponse(BaseModel):
    meeting_id: str
    summary: str
    action_items: List[ActionItem]
    transcript: List[MeetingSegment]
    clarity_score: float