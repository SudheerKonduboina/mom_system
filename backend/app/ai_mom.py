# app/ai_mom.py
# AI-powered MOM generation with context memory support

import os
import json
from datetime import datetime
from typing import Any, Dict, Optional

from openai import OpenAI
try:
    from groq import Groq
except ImportError:
    Groq = None

from app.config import settings


SYSTEM = """You are an expert meeting assistant. Your task is to extract high-quality Minutes of Meeting (MOM) from the provided transcript.

Guidelines:
1. Accuracy: Only include facts mentioned in the transcript.
2. Structure: Return STRICT JSON matching the target schema.
3. Participants: Identify people speaking or mentioned.
4. Action Items: Be specific. Format: { "task": "detailed description", "owner": "Name or TBD", "deadline": "Date or TBD", "status": "Pending" }.
5. Key Discussions: Summarize the main points clearly. Convert the transcript into bullet points describing the topics.
6. Summary: Include a meeting summary/insights, weaving in the overall meeting tone, sentiment, and engagement level, based on the transcript.
7. Decisions: Extract specific phrases like "we decided", "final decision", "agreed that", "we will" to outline exactly what was decided.

Required JSON Structure:
{
  "meeting_title": "Short descriptive meeting title",
  "date": "YYYY-MM-DD",
  "participants": ["Name1", "Name2"],
  "agenda": "Topics of discussion",
  "summary": "Meeting insights, sentiment, engagement level, and general tone.",
  "key_discussions": ["Point 1", "Point 2"],
  "decisions": ["Decision 1", "Decision 2"],
  "action_items": [
    {"task": "Extract specific task", "owner": "Name", "deadline": "TBD", "status": "Pending"}
  ],
  "risks_followups": ["Risk 1 or None"],
  "conclusion": "Brief closing statement"
}

If the transcript is bilingual (e.g., Hindi/English), provide the summary in English.
Avoid filler words and repetitions."""


def _fallback_mom(reason: str = "Needs review") -> Dict[str, Any]:
    return {
        "meeting_title": "Meeting Summary",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "participants": [],
        "agenda": "Meeting Summary",
        "summary": "Transcript too short or unclear.",
        "duration": "0s",
        "total_attendees": 0,
        "attendance_log": [],
        "key_discussions": ["Transcript too short or unclear."],
        "decisions": [],
        "action_items": [],
        "risks_followups": ["Low audio clarity"],
        "conclusion": reason
    }



def _extract_json(text: str) -> str:
    """Extract the first JSON block from text."""
    if not text:
        return "{}"

    text = text.strip()

    if "```json" in text:
        text = text.split("```json")[-1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[-1].split("```")[0].strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return "{}"


def ai_generate_mom(transcript: str, context_prompt: str = "") -> Dict[str, Any]:
    """
    Generate MOM using AI with optional context from previous meetings.

    Args:
        transcript: The meeting transcript text
        context_prompt: Optional context from previous meetings (pending actions, recurring topics)
    """
    if not transcript or len(transcript.strip()) < 20:
        return _fallback_mom("Transcript too short for AI analysis.")

    groq_key = settings.GROQ_API_KEY
    openai_key = settings.OPENAI_API_KEY

    if not groq_key and not openai_key:
        return _fallback_mom("No AI API keys found (GROQ_API_KEY or OPENAI_API_KEY).")

    try:
        # Prefer Groq (free tier friendly)
        client = None
        model = ""
        if groq_key and Groq:
            print("Using Groq AI Engine...")
            client = Groq(api_key=groq_key)
            model = "llama-3.3-70b-versatile"
        elif openai_key:
            print("Using OpenAI Engine...")
            client = OpenAI(api_key=openai_key)
            model = "gpt-4o-mini"
        else:
            return _fallback_mom("Groq library not installed even though key is present.")

        # Build messages with optional context
        system_msg = SYSTEM
        if context_prompt:
            system_msg += f"\n\nPrevious Meeting Context:\n{context_prompt}"
            system_msg += ("\n\nUse this context to:"
                          "\n- Note follow-ups on previous action items"
                          "\n- Detect recurring topics"
                          "\n- Reference prior decisions if relevant")

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Transcript:\n{transcript}"},
            ],
            temperature=0.1,
            response_format={"type": "json_object"} if "llama-3" in model or "gpt" in model else None
        )

        text = (resp.choices[0].message.content or "").strip()
        json_text = _extract_json(text)
        mom = json.loads(json_text)

        # Merge with defaults to ensure all keys exist
        defaults = {
            "meeting_title": "Meeting Summary",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "participants": [],
            "agenda": "Meeting Summary",
            "summary": "Meeting details processed",
            "duration": "0s",
            "total_attendees": 0,
            "attendance_log": [],
            "key_discussions": [],
            "decisions": [],
            "action_items": [],
            "risks_followups": [],
            "conclusion": "",
        }

        for key, val in defaults.items():
            if key not in mom:
                mom[key] = val

        return mom

    except Exception as e:
        print(f"AI Generation Error ({'Groq' if groq_key else 'OpenAI'}): {e}")
        # Groq failed → try OpenAI fallback
        if groq_key and openai_key:
            print("Groq failed, trying OpenAI fallback...")
            try:
                client = OpenAI(api_key=openai_key)
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": f"Transcript:\n{transcript}"},
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                text = (resp.choices[0].message.content or "").strip()
                json_text = _extract_json(text)
                return json.loads(json_text)
            except Exception as e2:
                print(f"OpenAI fallback also failed: {e2}")

        return _fallback_mom(f"AI processing failed: {str(e)}")
