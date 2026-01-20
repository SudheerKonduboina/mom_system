import whisper
import torch

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.stt_model = whisper.load_model("base", device=self.device)

    def process_audio(self, file_path: str):
        print(f"Processing audio with Translation task: {file_path}")

        result = self.stt_model.transcribe(
            file_path,
            task="translate",
            verbose=False,
            fp16=(self.device == "cuda")
        )

        segments = result.get("segments", [])
        structured_segments = []

        for seg in segments:
            structured_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
                "confidence": seg.get("avg_logprob", 0)
            })

        return {
            "text": result.get("text", ""),
            "segments": structured_segments,
            "metadata": {
                "duration": segments[-1]["end"] if segments else 0
            }
        }
