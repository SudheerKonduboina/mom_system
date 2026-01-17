import whisper
import torch
import os

class AudioEngine:
    def __init__(self):
        try:
            # Detect hardware acceleration (GPU vs CPU)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Initializing Whisper on: {self.device}")
            
            # Using "base" for optimal speed/accuracy balance
            self.stt_model = whisper.load_model("base", device=self.device)
            
        except Exception as e:
            print(f"Model Initialization Error: {e}")

    def process_audio(self, file_path: str):
        """
        Transcribes audio and performs simple gap-based speaker diarization.
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found at {file_path}")

            # 1. Transcribe the audio file
            # fp16=False ensures compatibility across all hardware
            result = self.stt_model.transcribe(file_path, verbose=False, fp16=False)
            
            structured_segments = []
            current_speaker = 1
            
            # 2. Process segments and apply Simple Diarization logic
            for i, item in enumerate(result['segments']):
                # LOGIC: If silence between segments > 1.5s, assume a different speaker
                if i > 0:
                    prev_end = result['segments'][i-1]['end']
                    curr_start = item['start']
                    if (curr_start - prev_end) > 1.5:
                        # Toggle between Speaker 1 and Speaker 2
                        current_speaker = 2 if current_speaker == 1 else 1
                
                structured_segments.append({
                    "start": item['start'],
                    "end": item['end'],
                    "text": item['text'].strip(),
                    "speaker_id": f"Speaker {current_speaker}"
                })

            # 3. Return the full intelligence package
            return {
                "raw_text": result['text'].strip(),
                "segments": structured_segments
            }

        except Exception as e:
            print(f"Audio Processing Failed: {str(e)}")
            raise RuntimeError(f"Audio Processing Failed: {str(e)}")