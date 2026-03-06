from datetime import datetime
import re
from typing import List, Dict

WEEKDAYS = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
RELATIVE = r"(today|tomorrow|tonight|this week|next week|this month|next month)"
TIME_HINTS = r"(\d{1,2}(:\d{2})?\s?(am|pm)?)"
DATE_HINTS = r"(\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?)"

# ✅ phrases that look like actions but are NOT action items
NOISE_TASKS = [
    "let's have a look",
    "lets have a look",
    "have a look",
    "take a look",
    "we will see",
    "we'll see",
    "we can see",
    "it doesn't matter",
    "sounds good",
    "okay",
    "ok"
]

ACTION_VERBS = [
    "finish", "complete", "submit", "send", "share", "update", "fix",
    "deliver", "create", "build", "review", "schedule", "deploy",
    "prepare", "draft", "call", "message", "implement", "test"
]

def _split_sentences(text: str) -> List[str]:
    chunks = re.split(r"[.\n!?]+", text)
    return [c.strip() for c in chunks if len(c.strip()) > 8]

def _clean_task(task: str) -> str:
    task = task.strip()
    task = re.sub(r"\s+", " ", task)
    task = re.sub(r"^(to\s+|please\s+|kindly\s+)", "", task, flags=re.I).strip()
    task = re.sub(r"\b(asap)\b", "", task, flags=re.I).strip()
    return task

def _extract_deadline(sentence: str) -> str | None:
    s = sentence.strip()

    m = re.search(r"\bwithin\s+(\d+)\s+(day|days|hour|hours|week|weeks)\b", s, flags=re.I)
    if m:
        return f"within {m.group(1)} {m.group(2)}"

    m = re.search(rf"\b{WEEKDAYS}\b", s, flags=re.I)
    if m:
        return m.group(0).title()

    m = re.search(rf"\b{RELATIVE}\b", s, flags=re.I)
    if m:
        return m.group(0).title()

    m = re.search(rf"\b{DATE_HINTS}\b", s, flags=re.I)
    if m:
        return m.group(0)

    m = re.search(rf"\b{TIME_HINTS}\b", s, flags=re.I)
    if m:
        return m.group(0)

    # "by X", "before X", "on X"
    m = re.search(r"\b(by|before|on|at|next)\s+([^,;]+)", s, flags=re.I)
    if m:
        return m.group(0).strip()

    return None

def _extract_owner_and_task(sentence: str) -> tuple[str | None, str | None]:
    s = sentence.strip()

    m = re.search(r"\bassign(ed)?\s+(.*?)\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", s)
    if m:
        task = _clean_task(m.group(2))
        owner = m.group(3).strip()
        return owner, task

    m = re.search(
        r"^\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(will|needs to|need to|should|can|is going to|to)\s+(.*)$",
        s,
        flags=re.I,
    )
    if m:
        owner = m.group(1).strip()
        task = _clean_task(m.group(3))
        return owner, task

    return None, None

def _looks_like_real_task(sentence: str) -> bool:
    low = sentence.lower().strip()

    # noise phrases
    for p in NOISE_TASKS:
        if p in low:
            return False

    # too short or mostly filler
    if len(low) < 18:
        return False

    # must contain a stronger action verb OR a deadline + "will/need"
    if any(v in low for v in ACTION_VERBS):
        return True

    if (" will " in f" {low} " or "need to" in low or "needs to" in low) and _extract_deadline(sentence):
        return True

    return False

def extract_action_items(transcript: str) -> List[Dict]:
    sentences = _split_sentences(transcript)

    items: List[Dict] = []
    seen = set()

    for sent in sentences:
        if not _looks_like_real_task(sent):
            continue

        owner, task = _extract_owner_and_task(sent)
        deadline = _extract_deadline(sent)

        if not task:
            task = _clean_task(sent)

        if not task or len(task) < 8:
            continue

        key = (task.lower(), (owner or "").lower(), (deadline or "").lower())
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "task": task,
            "owner": owner or "TBD",
            "deadline": deadline or "TBD"
        })

    return items

def generate_mom_from_transcript(transcript: str) -> dict:
    if not transcript or len(transcript.strip()) < 20:
        return {
            "meetDate": datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "participants": [],
            "agenda": "Meeting Summary",
            "key_discussions": "Discussion could not be clearly extracted from audio.",
            "decisions": ["No decisions recorded"],
            "action_items": [{
                "task": "Manual review required",
                "owner": "TBD",
                "deadline": "TBD"
            }],
            "risks": "Audio clarity risk",
            "conclusion": "Meeting recorded but content needs review"
        }

    sentences = _split_sentences(transcript)

    discussions = sentences[:8]
    key_discussions = "\n• " + "\n• ".join(discussions) if discussions else "No discussions extracted"

    decisions = []
    for s in sentences:
        low = s.lower()
        if any(k in low for k in ["decided", "agreed", "approved", "finalized", "we will go with", "we should go with"]):
            decisions.append(s.strip())

    action_items = extract_action_items(transcript)

    return {
        "meetDate": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "participants": [],
        "agenda": "Meeting Summary",
        "key_discussions": key_discussions,
        "decisions": decisions if decisions else ["No decisions recorded"],
        "action_items": action_items if action_items else [{
            "task": "No clear action items detected (manual review recommended)",
            "owner": "TBD",
            "deadline": "TBD"
        }],
        "risks": "None detected",
        "conclusion": "Minutes generated automatically from meeting audio."
    }
