import re
import logging
from datetime import datetime

logger = logging.getLogger("NLPProcessor")

# Safe imports — spacy/sklearn may have numpy ABI mismatch
nlp = None
TfidfVectorizer = None
cosine_similarity = None
np = None

try:
    import numpy as _np
    np = _np
except Exception as e:
    logger.warning(f"numpy not available: {e}")

try:
    import spacy as _spacy
    try:
        nlp = _spacy.load("en_core_web_sm")
    except Exception:
        try:
            import subprocess, sys
            subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
            nlp = _spacy.load("en_core_web_sm")
        except Exception as e2:
            logger.warning(f"spacy model load failed: {e2}")
except Exception as e:
    logger.warning(f"spacy import failed (likely numpy ABI mismatch): {e}")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer as _Tfidf
    from sklearn.metrics.pairwise import cosine_similarity as _cos
    TfidfVectorizer = _Tfidf
    cosine_similarity = _cos
except Exception as e:
    logger.warning(f"sklearn import failed: {e}")


class NLPProcessor:
    def __init__(self):
        self.decision_signals = ["decided", "agreed", "approved", "finalized"]
        self.blocker_signals = ["pending", "unclear", "revisit"]
        self.action_signals = ["will", "assigned", "responsible", "complete", "finish", "deliver", "submit", "send"]

        self.deadline_patterns = [
            r"\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\bby\s+(today|tomorrow)\b",
            r"\bby\s+(\d{1,2}(st|nd|rd|th)?)\b",
            r"\bby\s+(\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?)\b",
            r"\bby\s+([a-z]{3,9}\s+\d{1,2})\b",
            r"\bnext\s+(week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\bwithin\s+\d+\s+(days|day|weeks|week|hours|hour)\b",
            r"\bin\s+\d+\s+(days|day|weeks|week|hours|hour)\b",
        ]

    def extract_intel(self, transcript: str):
        if not transcript or len(transcript) < 10:
            return self._empty()

        # If spacy unavailable, split by period
        if nlp is not None:
            doc = nlp(transcript)
            sentences = [s.text.strip() for s in doc.sents if len(s.text.strip()) > 2]
        else:
            sentences = [s.strip() for s in transcript.split('.') if len(s.strip()) > 2]

        clarity_score = 0.0
        if sentences and TfidfVectorizer is not None and np is not None:
            try:
                vectorizer = TfidfVectorizer(stop_words="english")
                tfidf = vectorizer.fit_transform(sentences)
                centroid = np.asarray(tfidf.mean(axis=0))
                scores = cosine_similarity(tfidf, centroid).flatten()
                clarity_score = round(float(np.mean(scores) * 100), 2)
            except Exception:
                clarity_score = 0.0

        decisions, actions = [], []

        for sent in sentences:
            lower = sent.lower()

            if any(d in lower for d in self.decision_signals):
                decisions.append(sent)

            if self._looks_like_action(lower):
                owner = self._extract_owner(sent)
                deadline = self._extract_deadline(sent)
                task = self._extract_task(sent, owner=owner, deadline=deadline)

                actions.append({
                    "task": task or sent,
                    "owner": owner or "TBD",
                    "deadline": deadline or "TBD"
                })

        names = sorted({a["owner"] for a in actions if a.get("owner") and a["owner"] != "TBD"})

        return {
            "agenda": "Meeting Analysis",
            "participants": names,
            "key_discussions": ". ".join(sentences[:5]) if sentences else "No discussions extracted",
            "decisions": decisions,
            "action_items": actions,
            "risks": "None detected",
            "conclusion": "Meeting summarized",
            "summary": f"{len(sentences)} segments analyzed",
            "clarity_score": clarity_score,
            "meetDate": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

    def _looks_like_action(self, lower: str) -> bool:
        if any(k in lower for k in self.action_signals):
            return True
        if re.search(r"\b(need to|please|let's|lets)\b", lower):
            return True
        return False

    def _extract_owner(self, sentence: str):
        if nlp is None:
            return None
        doc_sent = nlp(sentence)
        for ent in doc_sent.ents:
            if ent.label_ == "PERSON":
                return ent.text.strip()

        m = re.match(r"^\s*([A-Z][a-z]+)\s+(will|shall|to)\b", sentence.strip())
        if m:
            return m.group(1).strip()
        return None

    def _extract_deadline(self, sentence: str):
        lower = sentence.strip().lower()
        for pat in self.deadline_patterns:
            m = re.search(pat, lower, flags=re.IGNORECASE)
            if m:
                return m.group(0).strip()
        return None

    def _extract_task(self, sentence: str, owner: str | None, deadline: str | None):
        task = sentence.strip()

        if owner:
            task = re.sub(rf"\b{re.escape(owner)}\b", "", task).strip()

        if deadline:
            task = re.sub(re.escape(deadline), "", task, flags=re.IGNORECASE).strip()

        task = re.sub(
            r"\b(will|shall|assigned|responsible for|responsible|please|kindly|need to|needs to)\b",
            "",
            task,
            flags=re.IGNORECASE
        ).strip()

        task = task.strip(" -:;,.")
        return task

    def _empty(self):
        return {
            "agenda": "Error",
            "participants": [],
            "key_discussions": "Transcript too short",
            "decisions": [],
            "action_items": [],
            "risks": "None",
            "conclusion": "N/A",
            "summary": "Failed",
            "clarity_score": 0.0,
            "meetDate": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
