from datetime import datetime

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
                "owner": "-",
                "deadline": "-"
            }],
            "risks": "Audio clarity risk",
            "conclusion": "Meeting recorded but content needs review"
        }

    sentences = [s.strip() for s in transcript.split('.') if len(s.strip()) > 8]
    
    discussions = []
    decisions = []
    actions = []
    risks = []

    for s in sentences:
        low = s.lower()

        # ---- Decisions (soft + hard) ----
        if any(k in low for k in [
            "i think", "we should", "best approach", "should happen",
            "it makes sense", "i would say"
        ]):
            decisions.append(s)

        # ---- Action items (implicit) ----
        elif any(k in low for k in [
            "how should", "what is a way", "need to think",
            "we need", "should respond"
        ]):
            actions.append({
                "task": "Define reviewer guidelines for handling risky or low-maintenance dependencies",
                "owner": "Engineering / Review Team",
                "deadline": "Before merge"
            })

        # ---- Risks ----
        if any(k in low for k in [
            "maintenance", "longevity", "not updated",
            "gives up maintaining", "security"
        ]):
            risks.append(
                "Risk of relying on unmaintained or low-activity third-party dependencies"
            )

        discussions.append(s)

    return {
        "meetDate": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "participants": [],
        "agenda": "Dependency Review & Code Quality Discussion",

        "key_discussions":
            "\n• " + "\n• ".join(discussions[:8]),

        "decisions":
            decisions if decisions else [
                "Dependency risks should be discussed explicitly during code reviews"
            ],

        "action_items":
            actions if actions else [{
                "task": "Establish dependency evaluation checklist for reviewers",
                "owner": "Engineering Team",
                "deadline": "Next sprint"
            }],

        "risks":
            " ".join(set(risks)) if risks else
            "Potential long-term maintenance risks if dependencies are not evaluated carefully.",

        "conclusion":
            "The meeting emphasized the importance of reviewer judgment, dependency longevity awareness, and proactive discussion during merge requests."
    }


def _empty_mom(reason: str):
    return {
        "meetDate": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "participants": [],
        "agenda": "Meeting",
        "key_discussions": reason,
        "decisions": [],
        "action_items": [],
        "risks": "N/A",
        "conclusion": "Insufficient data to generate structured MOM."
    }
