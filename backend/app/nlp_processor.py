import re

class NLPProcessor:
    def __init__(self):
        # Combined triggers for action item detection
        self.action_triggers = [
            r"(?i)i will", r"(?i)we need to", r"(?i)let's ensure", 
            r"(?i)action item", r"(?i)assigned to", r"(?i)by next week",
            r"(?i)need to", r"(?i)must", r"(?i)task"
        ]
        # Words that decrease the clarity score (Vagueness Detection)
        self.vague_words = ["maybe", "later", "probably", "might", "someone", "sometime", "eventually"]

    def extract_intel(self, audio_output: dict):
        """
        Processes the dictionary from AudioEngine to generate structured MOM.
        Calculates a real-time Clarity Score based on text quality.
        """
        try:
            full_text = audio_output.get("raw_text", "")
            segments = audio_output.get("segments", [])
            action_items = []
            vague_count = 0

            # 1. Analyze Segments for Action Items and Quality
            for seg in segments:
                text = seg['text']
                text_lower = text.lower()

                # Check for vague language
                for word in self.vague_words:
                    if word in text_lower:
                        vague_count += 1

                # Detect Action Items
                if any(re.search(trigger, text) for trigger in self.action_triggers):
                    # Try to detect owner dynamically
                    owner = self._detect_owner(text)
                    
                    action_items.append({
                        "task": text.strip(),
                        "owner": owner,
                        "deadline": self._detect_deadline(text),
                        "speaker": seg.get("speaker_id", "Unknown"),
                        "timestamp": seg.get("start", 0)
                    })

            # 2. Fallback logic if segments missed everything
            if not action_items and full_text:
                action_items = self._fallback_find_actions(full_text)

            # 3. Calculate Dynamic Clarity Score
            # Formula: Start at 100%, deduct 5% for vague words, 10% for unassigned tasks
            unassigned_count = len([a for a in action_items if a['owner'] == "Unassigned"])
            base_score = 100
            penalty = (vague_count * 5) + (unassigned_count * 10)
            final_score = max(5, min(100, base_score - penalty)) / 100

            return {
                "summary": self._generate_summary(full_text),
                "action_items": action_items,
                "clarity_score": final_score,
                "analysis": {
                    "vague_words_found": vague_count,
                    "unassigned_tasks": unassigned_count,
                    "total_words": len(full_text.split())
                }
            }
        except Exception as e:
            print(f"NLP Extraction Error: {str(e)}")
            raise RuntimeError(f"NLP Extraction Failed: {str(e)}")

    def _detect_owner(self, text: str):
        """Simple NER logic: Finds capitalized names following assignment keywords."""
        owner_match = re.search(r"(?:assign to|for|by)\s+([A-Z][a-z]+)", text)
        return owner_match.group(1) if owner_match else "Unassigned"

    def _detect_deadline(self, text: str):
        """Simple regex to find common deadline mentions."""
        deadline_match = re.search(r"(?i)(by\s+\w+|next\s+\w+|tomorrow|monday|friday)", text)
        return deadline_match.group(1) if deadline_match else "TBD"

    def _generate_summary(self, text: str):
        if not text:
            return "No content to summarize."
        return text[:300] + "..." if len(text) > 300 else text

    def _fallback_find_actions(self, text: str):
        sentences = text.split('.')
        found = []
        for s in sentences:
            if any(re.search(trigger, s) for trigger in self.action_triggers):
                found.append({
                    "task": s.strip(), 
                    "owner": "Unassigned", 
                    "deadline": "TBD",
                    "speaker": "Unknown",
                    "timestamp": 0
                })
        return found