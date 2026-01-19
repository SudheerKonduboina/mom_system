import os
import json
import pandas as pd
import numpy as np
import spacy
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load NLP model locally
try:
    nlp = spacy.load("en_core_web_sm")
except:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

class NLPProcessor:
    def __init__(self):
        # Local Rule Signals from your engine
        self.decision_signals = ['decided', 'agreed', 'approved', 'finalized', 'confirmed']
        self.blocker_signals = ['not decided', 'unclear', 'pending', 'unresolved', 'revisit', 'needs confirmation']
        self.action_signals = ['will', 'shall', 'responsible', 'assigned to', 'needs to', 'coordinate', 'complete']
        self.question_signals = ['?', 'should we', 'do we', 'unclear', 'open question']
        self.domain_keywords = ['deployment', 'deadline', 'budget', 'qa', 'security', 'risk', 'monitoring', 'ui', 'launch', 'pipeline']
        
        # Model ID kept for internal reference, though Gemini is no longer used
        self.model_id = "local-spacy-engine"

    def extract_owner(self, doc, prev_entities):
        current_names = [ent.text for ent in doc.ents if ent.label_ in ["PERSON", "ORG"]]
        if current_names:
            return current_names[0]
        text = doc.text.lower()
        if any(p in text for p in ["he", "she", "they"]) and prev_entities:
            return prev_entities[-1]
        return "Not Mentioned"

    def extract_intel(self, transcript_input):
        # Ensure we have a string
        if isinstance(transcript_input, dict):
            transcript_text = transcript_input.get("text", "")
        else:
            transcript_text = str(transcript_input)

        if not transcript_text or len(transcript_text.strip()) < 10:
            return self._get_empty_response("Transcript too short.")

        # Run Local Engine Analysis
        doc = nlp(transcript_text)
        sentences = [sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 5]
        
        if not sentences:
            return self._get_empty_response("No valid sentences found.")

        # TF-IDF calculations
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(sentences)
        t_scores = np.asarray(tfidf_matrix.sum(axis=1)).flatten()
        t_norm = (t_scores / (t_scores.max() if t_scores.max() > 0 else 1)) * 100
        centroid = np.asarray(tfidf_matrix.mean(axis=0))
        s_scores = cosine_similarity(tfidf_matrix, centroid).flatten() * 100

        # Organize into your project's expected JSON format
        results = {
            "agenda": "Weekly Sync Meeting",
            "participants": [],
            "key_discussions": "",
            "decisions": [],
            "action_items": [], 
            "risks": "None detected during local analysis.",
            "conclusion": "Meeting adjourned after key points were summarized.",
            "summary": "",
            "clarity_score": round(float(np.mean(s_scores)), 2),
            "meetDate": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
        }

        entity_history = []
        key_discussion_points = []

        for i, sent_text in enumerate(sentences):
            # --- START MERGED LOGIC: SPEAKER DETECTION ---
            if "Speaker " in sent_text:
                speaker_label = sent_text.split(":")[0] # Extracts "Speaker 0"
                if speaker_label not in results["participants"]:
                    results["participants"].append(speaker_label)
            # --- END MERGED LOGIC ---

            low_sent = sent_text.lower()
            sent_doc = nlp(sent_text)
            
            # Extract Owner/Entities
            owner = self.extract_owner(sent_doc, entity_history)
            if owner != "Not Mentioned": 
                entity_history.append(owner)
                if owner not in results["participants"]: results["participants"].append(owner)

            # Classification
            has_blocker = any(sig in low_sent for sig in self.blocker_signals)
            has_decision = any(sig in low_sent for sig in self.decision_signals)
            has_action = any(sig in low_sent for sig in self.action_signals)

            if has_decision and not has_blocker:
                results["decisions"].append(sent_text)
            elif has_action and not has_blocker:
                # Updated to return dictionary for the HTML table
                results["action_items"].append({
                    "task": sent_text,
                    "owner": owner if owner != "Not Mentioned" else "Assignee TBD",
                    "deadline": "TBD" 
                })
            
            if s_scores[i] > 50: # High importance sentences
                key_discussion_points.append(sent_text)

        results["key_discussions"] = ". ".join(key_discussion_points[:5])
        results["summary"] = f"Local analysis completed. Found {len(results['decisions'])} decisions and {len(results['action_items'])} actions."
        
        return results

    def _get_empty_response(self, error_msg):
        return {
            "agenda": "Error",
            "participants": [],
            "key_discussions": error_msg,
            "decisions": [],
            "action_items": [],
            "risks": "None",
            "conclusion": "N/A",
            "summary": "Analysis failed.",
            "clarity_score": 0.0,
            "meetDate": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
        }