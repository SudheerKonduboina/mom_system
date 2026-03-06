# app/speaker_mapper.py
# Maps diarization Speaker_N labels to real participant names

import logging
import os
import json
from typing import Dict, List, Optional

from app.config import settings

logger = logging.getLogger("SpeakerMapper")


class SpeakerMapper:
    """
    Maps anonymous speaker IDs (SPEAKER_00, SPEAKER_01...) to real participant names.
    Strategies: join-order correlation, AI-assisted mapping, fallback.
    """

    def map_speakers(self, speaker_ids: List[str], participant_names: List[str],
                     aligned_segments: List[Dict] = None,
                     attendance_events: List[Dict] = None) -> Dict[str, str]:
        """
        Returns: {speaker_id: real_name} mapping.
        """
        if not speaker_ids:
            return {}

        if not participant_names:
            return {sid: sid for sid in speaker_ids}

        # Strategy 1: Join-order correlation
        mapping = self._join_order_mapping(speaker_ids, participant_names,
                                           aligned_segments, attendance_events)
        if mapping and self._mapping_confidence(mapping) > 0.6:
            logger.info(f"Speaker mapping via join-order: {mapping}")
            return mapping

        # Strategy 2: AI-assisted mapping
        if aligned_segments:
            ai_mapping = self._ai_assisted_mapping(speaker_ids, participant_names,
                                                     aligned_segments)
            if ai_mapping:
                logger.info(f"Speaker mapping via AI: {ai_mapping}")
                return ai_mapping

        # Strategy 3: Sequential fallback
        mapping = {}
        for i, sid in enumerate(speaker_ids):
            if i < len(participant_names):
                mapping[sid] = participant_names[i]
            else:
                mapping[sid] = f"Speaker {i + 1}"

        logger.info(f"Speaker mapping via fallback: {mapping}")
        return mapping

    def _join_order_mapping(self, speaker_ids: List[str],
                            participant_names: List[str],
                            aligned_segments: List[Dict] = None,
                            attendance_events: List[Dict] = None) -> Dict[str, str]:
        """
        Map speakers by correlating first-speaking time with join time.
        """
        if not aligned_segments or not attendance_events:
            return {}

        # Get first speaking time per speaker
        first_speak = {}
        for seg in aligned_segments:
            speaker = seg.get("speaker", "")
            if speaker and speaker not in first_speak:
                first_speak[speaker] = seg.get("start", 0)

        # Get join time per participant (sorted)
        join_times = {}
        for event in attendance_events:
            if event.get("type") == "PARTICIPANT_JOIN" and event.get("name"):
                name = event["name"].strip()
                if name not in join_times:
                    join_times[name] = event.get("at", "")

        if not first_speak or not join_times:
            return {}

        # Sort both by time and map
        speakers_by_time = sorted(first_speak.items(), key=lambda x: x[1])
        participants_by_join = sorted(join_times.items(), key=lambda x: x[1])

        mapping = {}
        for i, (sid, _) in enumerate(speakers_by_time):
            if i < len(participants_by_join):
                mapping[sid] = participants_by_join[i][0]
            else:
                mapping[sid] = f"Speaker {i + 1}"

        return mapping

    def _ai_assisted_mapping(self, speaker_ids: List[str],
                              participant_names: List[str],
                              aligned_segments: List[Dict]) -> Optional[Dict[str, str]]:
        """Use LLM to infer speaker-to-name mapping from transcript context."""
        groq_key = settings.GROQ_API_KEY
        openai_key = settings.OPENAI_API_KEY

        if not groq_key and not openai_key:
            return None

        try:
            # Build excerpt of transcript
            excerpts = []
            for seg in aligned_segments[:30]:  # First 30 segments
                speaker = seg.get("speaker", "Unknown")
                text = seg.get("text", "").strip()
                if text:
                    excerpts.append(f"{speaker}: {text}")

            transcript_sample = "\n".join(excerpts)
            names_str = ", ".join(participant_names)

            prompt = f"""Given these meeting participants: {names_str}
And this transcript with anonymous speaker labels:
{transcript_sample}

Map each speaker label to a real participant name based on context clues
(self-references, being addressed by name, role references, etc.).

Return ONLY a JSON object mapping speaker IDs to names.
Example: {{"SPEAKER_00": "John", "SPEAKER_01": "Alice"}}
If unsure about a mapping, keep the original speaker label."""

            if groq_key:
                try:
                    from groq import Groq
                    client = Groq(api_key=groq_key)
                    model = "llama-3.3-70b-versatile"
                except ImportError:
                    client = None
            if (not groq_key or client is None) and openai_key:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                model = "gpt-4o-mini"

            if client is None:
                return None

            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            text = (resp.choices[0].message.content or "").strip()
            if "```" in text:
                text = text.split("```json")[-1].split("```")[0].strip() if "```json" in text else text.split("```")[1].strip()

            mapping = json.loads(text)
            if isinstance(mapping, dict) and mapping:
                return mapping

        except Exception as e:
            logger.warning(f"AI speaker mapping failed: {e}")

        return None

    def _mapping_confidence(self, mapping: Dict[str, str]) -> float:
        """Estimate confidence of a mapping (0-1)."""
        if not mapping:
            return 0
        # Higher confidence when names are real (not Speaker N)
        real_names = sum(1 for v in mapping.values() if not v.startswith("Speaker"))
        return real_names / len(mapping)

    def apply_mapping(self, aligned_segments: List[Dict],
                      mapping: Dict[str, str]) -> List[Dict]:
        """Replace speaker IDs with real names in aligned segments."""
        result = []
        for seg in aligned_segments:
            new_seg = dict(seg)
            speaker_id = seg.get("speaker", "")
            new_seg["speaker_id"] = speaker_id
            new_seg["speaker_name"] = mapping.get(speaker_id, speaker_id)
            new_seg["speaker"] = new_seg["speaker_name"]
            result.append(new_seg)
        return result
