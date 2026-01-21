import whisper
import torch
import re

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.stt_model = whisper.load_model("base", device=self.device)

    def process_audio(self, file_path: str):
        print(f"Processing bilingual audio → English: {file_path}")

        result = self.stt_model.transcribe(
            file_path,
            task="translate",        #  FORCE translation to English
            language=None,           #  Auto-detect Hindi / English
            verbose=False,
            fp16=(self.device == "cuda"),
            temperature=0.0          #  Stable deterministic output
        )

        raw_text = result.get("text", "")
        clean_text = self._clean_text(raw_text)

        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": self._clean_text(seg["text"]),
                "confidence": seg.get("avg_logprob", 0)
            })

        return {
            "text": clean_text,
            "segments": segments,
            "metadata": {
                "language": "translated_to_english",
                "duration": segments[-1]["end"] if segments else 0
            }
        }

    def _clean_text(self, text: str) -> str:
        """
        Normalize Whisper output for NLP + MOM
        """
        if not text:
            return ""

        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\b(um|uh|hmm|yeah|ya)\b", "", text, flags=re.I)

        return text.strip()
