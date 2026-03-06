import whisper
import torch
import re

class AudioEngine:

    def __init__(self):

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.stt_model = whisper.load_model("base", device=self.device)


        print("🔊 Loading Whisper tiny model...")
        self.model = whisper.load_model("tiny", device=self.device)
        print("✅ Whisper loaded")



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


        print("⏳ Running Whisper STT...")

        result = self.model.transcribe(
            file_path,
            task="translate",        # Hindi → English
            language="hi",
            fp16=(self.device == "cuda"),
            temperature=0.2,
            beam_size=5,
            best_of=5,
            verbose=True
        )

        text = result.get("text", "")

        text = self.clean_transcript(text)

        segments = []

        for seg in result.get("segments", []):

            segments.append({
                "speaker_id": "Speaker-1",
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": self.clean_transcript(seg.get("text", ""))
            })

        duration = segments[-1]["end"] if segments else 0

        print("✅ Transcription + Translation completed")

        return {
            "text": text,
            "segments": segments,
            "metadata": {
                "duration": duration
            }
        }


    def clean_transcript(self, text):

        # remove repeated words
        text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text)

        # remove filler words
        text = re.sub(r'\b(um|uh|hmm|yeah|okay)\b', '', text, flags=re.I)

        # remove extra spaces
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

