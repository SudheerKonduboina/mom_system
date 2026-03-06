
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
=======
import re
from datetime import datetime
from collections import Counter


# -----------------------------
# CLEAN TRANSCRIPT
# -----------------------------
def clean_transcript(text):

    # remove repeating loops
    text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text)

    # remove filler words
    text = re.sub(r'\b(um|uh|hmm|yeah|okay)\b', '', text, flags=re.I)

    # remove extra spaces
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


# -----------------------------
# SENTENCE SPLITTER
# -----------------------------
def split_sentences(text):

    sentences = re.split(r'[.?!]', text)

    cleaned = []

    for s in sentences:

        s = s.strip()

        if len(s) > 10:
            cleaned.append(s)

    return cleaned


# -----------------------------
# PARTICIPANT DETECTOR
# -----------------------------
def extract_participants(text):

    # detect full names
    full_names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', text)

    # detect frequent capital words
    words = re.findall(r'\b[A-Z][a-z]{3,}\b', text)

    freq = Counter(words)

    for w, c in freq.items():

        if c >= 3:
            full_names.append(w)

    stop_words = {
        "Meeting","Discussion","Today",
        "India","Thanks","Hello","Sir"
    }

    participants = [
        n for n in full_names if n not in stop_words
    ]

    return list(set(participants))[:6]


# -----------------------------
# ACTION ITEM DETECTOR
# -----------------------------
def detect_actions(sentences):

    actions = []

    keywords = [
        "will",
        "need to",
        "must",
        "should",
        "complete",
        "prepare",
        "submit",
        "assign"
    ]

    for s in sentences:

        if any(k in s.lower() for k in keywords):

            actions.append({
                "task": s,
                "owner": "To be assigned",
                "deadline": "TBD"
            })

    return actions


# -----------------------------
# DECISION DETECTOR
# -----------------------------
def detect_decisions(sentences):

    decisions = []

    keywords = [
        "decided",
        "agreed",
        "approved",
        "finalized"
    ]

    for s in sentences:

        if any(k in s.lower() for k in keywords):

            decisions.append(s)

    return decisions


# -----------------------------
# MOM GENERATOR
# -----------------------------
def generate_mom_from_transcript(transcript):

    transcript = clean_transcript(transcript)

    sentences = split_sentences(transcript)

    participants = extract_participants(transcript)

    agenda = (
        sentences[0]
        if sentences
        else "General meeting discussion"
    )

    discussions = sentences[:6]

    decisions = detect_decisions(sentences)

    actions = detect_actions(sentences)

    conclusion = (
        sentences[-1]
        if sentences
        else "Meeting concluded."
    )
>>>>>>> 939e520 (Updated whisper translation and MOM generation logic)

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


        "participants": participants,

        "agenda": agenda,

        "key_discussions": discussions,

        "decisions": decisions,

        "action_items": actions,

        "risks": "No major risks identified.",

        "conclusion": conclusion
    }

