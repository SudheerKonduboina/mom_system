# app/meeting_insights.py
# AI Meeting Insights: sentiment, topics, engagement score, speaking time analytics

import logging
from typing import Any, Dict, List

from app.config import settings

logger = logging.getLogger("MeetingInsights")


class MeetingInsightsEngine:
    """Generates meeting intelligence beyond basic MOM."""

    def analyze(self, transcript: str, speaking_times: Dict[str, float] = None,
                num_speakers: int = 0, duration_sec: float = 0) -> Dict[str, Any]:
        """
        Full insights analysis.
        Returns: {sentiment, topics, engagement_score, speaking_time_analytics}
        """
        insights = {
            "sentiment": self._analyze_sentiment(transcript),
            "topics": self._detect_topics(transcript),
            "engagement_score": self._calculate_engagement(
                speaking_times or {}, num_speakers, duration_sec
            ),
            "speaking_time_analytics": self._format_speaking_times(speaking_times or {}),
        }
        return insights

    def _analyze_sentiment(self, transcript: str) -> Dict[str, Any]:
        """Classify meeting tone as positive/neutral/negative."""
        if not transcript or len(transcript.strip()) < 20:
            return {"overall": "neutral", "score": 0.5}

        # Try AI-based sentiment
        ai_result = self._ai_sentiment(transcript)
        if ai_result:
            return ai_result

        # Fallback: keyword-based
        return self._keyword_sentiment(transcript)

    def _ai_sentiment(self, transcript: str) -> Dict[str, Any] | None:
        """Use LLM for sentiment analysis."""
        groq_key = settings.GROQ_API_KEY
        openai_key = settings.OPENAI_API_KEY

        if not groq_key and not openai_key:
            return None

        try:
            if groq_key:
                from groq import Groq
                client = Groq(api_key=groq_key)
                model = "llama-3.3-70b-versatile"
            else:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                model = "gpt-4o-mini"

            # Use only first 2000 chars to save tokens
            sample = transcript[:2000]
            resp = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": f"""Analyze the sentiment of this meeting transcript. 
Return ONLY a JSON object: {{"overall": "positive"|"neutral"|"negative", "score": 0.0-1.0, "details": "brief explanation"}}

Transcript:
{sample}"""
                }],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            import json
            text = resp.choices[0].message.content.strip()
            return json.loads(text)
        except Exception as e:
            logger.warning(f"AI sentiment failed: {e}")
            return None

    def _keyword_sentiment(self, transcript: str) -> Dict[str, Any]:
        """Keyword-based fallback sentiment analysis."""
        lower = transcript.lower()
        positive = ["agree", "great", "good", "excellent", "happy", "success",
                     "progress", "approve", "well done", "congratulations",
                     "thank", "perfect", "awesome", "resolved"]
        negative = ["problem", "issue", "delay", "risk", "fail", "concern",
                     "disagree", "block", "cancel", "urgent", "critical",
                     "missed", "overdue", "wrong"]

        pos_count = sum(1 for w in positive if w in lower)
        neg_count = sum(1 for w in negative if w in lower)
        total = pos_count + neg_count

        if total == 0:
            return {"overall": "neutral", "score": 0.5}

        score = pos_count / total
        if score > 0.6:
            overall = "positive"
        elif score < 0.4:
            overall = "negative"
        else:
            overall = "neutral"

        return {"overall": overall, "score": round(score, 2)}

    def _detect_topics(self, transcript: str) -> List[str]:
        """Extract key topics from transcript."""
        if not transcript or len(transcript) < 50:
            return []

        # Try AI-based topic detection
        ai_topics = self._ai_topics(transcript)
        if ai_topics:
            return ai_topics

        # Fallback: TF-IDF based keyword extraction
        return self._tfidf_topics(transcript)

    def _ai_topics(self, transcript: str) -> List[str] | None:
        """Use LLM for topic detection."""
        groq_key = settings.GROQ_API_KEY
        openai_key = settings.OPENAI_API_KEY

        if not groq_key and not openai_key:
            return None

        try:
            if groq_key:
                from groq import Groq
                client = Groq(api_key=groq_key)
                model = "llama-3.3-70b-versatile"
            else:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                model = "gpt-4o-mini"

            sample = transcript[:2000]
            resp = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": f"""Extract 3-5 key topics discussed in this meeting transcript.
Return ONLY a JSON array of topic strings with no other text.
Example: ["AI Model Training", "Backend Deployment", "Budget Review"]

Transcript:
{sample}"""
                }],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            import json
            text = resp.choices[0].message.content.strip()
            result = json.loads(text)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return result.get("topics", list(result.values())[0] if result else [])
        except Exception as e:
            logger.warning(f"AI topic detection failed: {e}")
        return None

    def _tfidf_topics(self, transcript: str) -> List[str]:
        """Fallback: extract top keywords via TF-IDF."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import numpy as np

            sentences = [s.strip() for s in transcript.split(".") if len(s.strip()) > 10]
            if len(sentences) < 2:
                return []

            vectorizer = TfidfVectorizer(
                stop_words="english", max_features=100,
                ngram_range=(1, 2), max_df=0.8
            )
            tfidf = vectorizer.fit_transform(sentences)
            scores = np.asarray(tfidf.sum(axis=0)).flatten()
            features = vectorizer.get_feature_names_out()

            top_indices = scores.argsort()[-5:][::-1]
            return [features[i].title() for i in top_indices]
        except Exception as e:
            logger.warning(f"TF-IDF topic extraction failed: {e}")
            return []

    def _calculate_engagement(self, speaking_times: Dict[str, float],
                               num_speakers: int, duration_sec: float) -> float:
        """
        Calculate meeting engagement score (0-100).
        Weighted formula:
        - Speaking time distribution uniformity (40%)
        - Number of active speakers (20%)
        - Silence ratio (20%)
        - Interaction/turn count (20%)
        """
        if not speaking_times or duration_sec <= 0:
            return 0

        total_speaking = sum(speaking_times.values())

        # 1. Distribution uniformity (40%) — how evenly distributed is speaking
        if len(speaking_times) > 1:
            times = list(speaking_times.values())
            avg = total_speaking / len(times)
            variance = sum((t - avg) ** 2 for t in times) / len(times)
            max_variance = avg ** 2  # worst case
            uniformity = 1 - min(1, variance / max(0.001, max_variance))
        else:
            uniformity = 0.3  # Single speaker = low uniformity

        # 2. Active speakers ratio (20%)
        expected_speakers = max(2, num_speakers)
        speaker_score = min(1.0, len(speaking_times) / expected_speakers)

        # 3. Silence ratio (20%) — less silence = more engagement
        silence = max(0, duration_sec - total_speaking)
        silence_ratio = silence / max(1, duration_sec)
        silence_score = 1 - min(1, silence_ratio)

        # 4. Interaction (20%) — more speakers switching = more interaction
        interaction_score = min(1.0, len(speaking_times) * 0.25)

        score = (uniformity * 40 + speaker_score * 20 +
                 silence_score * 20 + interaction_score * 20)

        return round(min(100, max(0, score)), 1)

    def _format_speaking_times(self, speaking_times: Dict[str, float]) -> List[Dict]:
        """Format speaker times for display."""
        total = sum(speaking_times.values()) or 1
        result = []
        for speaker, seconds in sorted(speaking_times.items(),
                                        key=lambda x: x[1], reverse=True):
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            result.append({
                "speaker": speaker,
                "duration_sec": round(seconds, 1),
                "display": f"{mins}m {secs}s" if mins else f"{secs}s",
                "percentage": round((seconds / total) * 100, 1),
            })
        return result
