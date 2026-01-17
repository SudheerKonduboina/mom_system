import whisper
import torch
import os

class AudioEngine:
    def __init__(self):
        try:
            # Detect hardware acceleration
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Initializing Whisper on: {self.device}")
            
            # Using "base" for speed/efficiency
            # For better MOM accuracy, you can use "small" or "medium"
            self.stt_model = whisper.load_model("base", device=self.device)
            
        except Exception as e:
            print(f"Model Initialization Error: {e}")

    def process_audio(self, file_path: str):
        """
        Transcribes audio and returns both raw text and structured segments.
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found at {file_path}")

            # 1. Transcribe the audio file
            # fp16=False is used to ensure compatibility with CPU-only environments
            result = self.stt_model.transcribe(file_path, verbose=False, fp16=False)
            
            # 2. Extract full text (from new version)
            full_text = result['text'].strip()

            # 3. Extract segments with timestamps (from old version)
            # This is critical for MOM to track when things were said
            structured_segments = []
            for item in result['segments']:
                structured_segments.append({
                    "start": item['start'],
                    "end": item['end'],
                    "text": item['text'].strip(),
                    "speaker_id": "Speaker_Unknown" # Placeholder for future diarization
                })

            # Return a dictionary containing both formats
            return {
                "raw_text": full_text,
                "segments": structured_segments
            }

        except Exception as e:
            print(f"Audio Processing Failed: {str(e)}")
            raise RuntimeError(f"Audio Processing Failed: {str(e)}")