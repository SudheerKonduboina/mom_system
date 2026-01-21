from datetime import datetime

def generate_mom_from_transcript(transcript: str) -> dict:
    if not transcript or len(transcript) < 20:
        return empty_mom("Transcript too short")

    sentences = [s.strip() for s in transcript.split('.') if len(s.strip()) > 8]

    discussions, decisions, actions = [], [], []

    for s in sentences:
        l = s.lower()
        if any(k in l for k in ["decide", "agreed", "final"]):
            decisions.append(s)
        elif any(k in l for k in ["need to", "will", "assign"]):
            actions.append({
                "task": s,
                "owner": "TBD",
                "deadline": "TBD"
            })
        else:
            discussions.append(s)

    return {
        "meetDate": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "participants": [],
        "agenda": "Meeting Summary",
        "key_discussions": "\n• " + "\n• ".join(discussions[:8]),
        "decisions": decisions or ["No decisions recorded"],
        "action_items": actions or [{
            "task": "No action items",
            "owner": "-",
            "deadline": "-"
        }],
        "risks": "No major risks identified",
        "conclusion": "Meeting concluded successfully"
    }

def empty_mom(reason):
    return {
        "meetDate": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "participants": [],
        "agenda": "Meeting",
        "key_discussions": reason,
        "decisions": [],
        "action_items": [],
        "risks": "N/A",
        "conclusion": "Insufficient data"
    }
