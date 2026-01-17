import re

class NLPProcessor:
    def __init__(self):
        # Heuristics for MOM detection logic - Combined from both versions
        self.action_triggers = [
            r"(?i)i will", r"(?i)we need to", r"(?i)let's ensure", 
            r"(?i)action item", r"(?i)assigned to", r"(?i)by next week",
            r"(?i)need to", r"(?i)must", r"(?i)task"
        ]

    def extract_intel(self, audio_output: dict):
        """
        Processes the dictionary from AudioEngine to generate MOM.
        audio_output contains 'raw_text' and 'segments'.
        """
        try:
            # 1. Prepare data
            full_text = audio_output.get("raw_text", "")
            segments = audio_output.get("segments", [])
            action_items = []

            # 2. Extract Action Items using segment-level granularity
            # This is more accurate than scanning the whole block of text
            for seg in segments:
                text = seg['text']
                if any(re.search(trigger, text) for trigger in self.action_triggers):
                    action_items.append({
                        "task": text,
                        "owner": self._detect_owner(text),
                        "deadline": self._detect_deadline(text),
                        "timestamp": seg.get("start", 0)
                    })

            # 3. Handle case where no segments found but raw text exists
            if not action_items and full_text:
                action_items = self._fallback_find_actions(full_text)

            return {
                "summary": self._generate_summary(full_text),
                "action_items": action_items,
                "clarity_score": 0.85, # Placeholder for NLP confidence logic
                "total_words": len(full_text.split())
            }
        except Exception as e:
            print(f"NLP Extraction Error: {str(e)}")
            raise RuntimeError(f"NLP Extraction Failed: {str(e)}")

    def _generate_summary(self, text: str):
        # Professional summary placeholder
        if not text:
            return "No audio content detected to summarize."
        return text[:300] + "..." if len(text) > 300 else text

    def _detect_owner(self, text: str):
        # Entity detection placeholder
        return "Unassigned"

    def _detect_deadline(self, text: str):
        # Time parsing placeholder
        return "TBD"

    def _fallback_find_actions(self, text: str):
        """Simple sentence splitting if segment data is missing."""
        sentences = text.split('.')
        found = []
        for s in sentences:
            if any(re.search(trigger, s) for trigger in self.action_triggers):
                found.append({"task": s.strip(), "owner": "Unassigned", "deadline": "TBD"})
        return found