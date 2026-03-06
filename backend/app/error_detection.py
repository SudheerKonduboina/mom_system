# app/error_detection.py
# Error detection: audio quality, transcript validation, JSON structure checks

import logging
from typing import Any, Dict, List

logger = logging.getLogger("ErrorDetection")

REQUIRED_MOM_KEYS = [
    "meetDate", "participants", "agenda", "key_discussions",
    "decisions", "action_items", "risks", "conclusion"
]


def detect_errors(transcript: str = "", mom: Dict[str, Any] = None,
                  audio_quality_score: float = 100,
                  whisper_segments: List[Dict] = None) -> List[Dict[str, str]]:
    """
    Run all error detection checks.
    Returns: [{level: "warning"|"error", message: str}, ...]
    """
    warnings = []

    # 1. Low Audio Quality
    if audio_quality_score < 10:
        warnings.append({
            "level": "warning",
            "message": f"Audio clarity low (quality score: {audio_quality_score:.1f}). "
                       "Some speech may not be transcribed correctly."
        })
    elif audio_quality_score < 5:
        warnings.append({
            "level": "error",
            "message": "Very poor audio quality. Transcript may be unreliable."
        })

    # 2. Missing / Short Transcript
    word_count = len(transcript.split()) if transcript else 0
    if word_count < 5:
        warnings.append({
            "level": "error",
            "message": "Meeting speech unclear or no speech detected. Manual review recommended."
        })
    elif word_count < 20:
        warnings.append({
            "level": "warning",
            "message": f"Very short transcript ({word_count} words). "
                       "Content may be incomplete."
        })

    # 3. Low confidence segments from Whisper
    if whisper_segments:
        low_conf = [s for s in whisper_segments
                     if s.get("confidence", 0) < -1.0]
        if len(low_conf) > len(whisper_segments) * 0.5:
            warnings.append({
                "level": "warning",
                "message": f"{len(low_conf)}/{len(whisper_segments)} segments have "
                           "low confidence. Transcription accuracy may be reduced."
            })

    # 4. MOM JSON Structure Validation
    if mom:
        missing_keys = [k for k in REQUIRED_MOM_KEYS if k not in mom]
        if missing_keys:
            warnings.append({
                "level": "warning",
                "message": f"MOM missing fields: {', '.join(missing_keys)}. "
                           "Some sections may be incomplete."
            })

        # Check if action items have proper structure
        action_items = mom.get("action_items", [])
        if isinstance(action_items, list):
            for i, item in enumerate(action_items):
                if isinstance(item, dict):
                    if not item.get("task"):
                        warnings.append({
                            "level": "warning",
                            "message": f"Action item {i + 1} has no task description."
                        })
                elif isinstance(item, str):
                    # String-only action items lack structure
                    warnings.append({
                        "level": "warning",
                        "message": f"Action item {i + 1} lacks owner/deadline structure."
                    })

    # 5. Hallucination detection
    if transcript:
        hallucination_patterns = [
            "thank you for watching",
            "please subscribe",
            "like and share",
            "don't forget to subscribe",
        ]
        for pattern in hallucination_patterns:
            if pattern in transcript.lower():
                warnings.append({
                    "level": "warning",
                    "message": "Possible Whisper hallucination detected. "
                               "Some generated text may not be from the meeting."
                })
                break

    return warnings
