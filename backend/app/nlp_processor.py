import pandas as pd
import numpy as np
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    nlp = spacy.load("en_core_web_sm")
except:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

class NLPProcessor:
    def __init__(self):
        self.decision_signals = ["decided", "agreed", "approved", "finalized"]
        self.blocker_signals = ["pending", "unclear", "revisit"]
        self.action_signals = ["will", "assigned", "responsible", "complete"]

    def extract_intel(self, transcript):
        if not transcript or len(transcript) < 10:
            return self._empty()

        doc = nlp(transcript)
        sentences = [s.text.strip() for s in doc.sents if len(s.text.strip()) > 2]

        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf = vectorizer.fit_transform(sentences)
        scores = cosine_similarity(tfidf, tfidf.mean(axis=0)).flatten()

        decisions, actions = [], []

        for sent in sentences:
            lower = sent.lower()
            if any(d in lower for d in self.decision_signals):
                decisions.append(sent)
            if any(a in lower for a in self.action_signals):
                actions.append({
                    "task": sent,
                    "owner": "TBD",
                    "deadline": "TBD"
                })

        return {
            "agenda": "Meeting Analysis",
            "participants": [],
            "key_discussions": ". ".join(sentences[:5]),
            "decisions": decisions,
            "action_items": actions,
            "risks": "None detected",
            "conclusion": "Meeting summarized",
            "summary": f"{len(sentences)} segments analyzed",
            "clarity_score": round(float(np.mean(scores) * 100), 2),
            "meetDate": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
        }

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
            "meetDate": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
        }
