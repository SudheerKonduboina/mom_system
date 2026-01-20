from typing import Dict
import re

def generate_mom_from_transcript(transcript: str) -> Dict:
    if not transcript or len(transcript.strip()) == 0:
        return {}

    # Basic heuristic-based structuring (LLM-ready later)
    sentences = re.split(r'(?<=[.!?]) +', transcript)

    key_points = sentences[:10]
    decisions = [s for s in sentences if "decide" in s.lower() or "decision" in s.lower()]
    risks = [s for s in sentences if "risk" in s.lower() or "problem" in s.lower()]
    actions = [s for s in sentences if "should" in s.lower() or "need to" in s.lower()]

    return {
        "meetDate": None,
        "participants": [],
        "agenda": "Auto-generated from meeting discussion",
        "summary": " ".join(sentences[:5]),
        "key_discussions": "\n".join(key_points),
        "decisions": decisions if decisions else [],
        "action_items": [
            {"task": a, "owner": "TBD", "deadline": "TBD"} for a in actions[:5]
        ],
        "risks": " ".join(risks) if risks else "No major risks discussed.",
        "conclusion": "Meeting concluded with the above discussion points."
    }
