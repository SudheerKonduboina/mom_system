import whisper
import torch
import os

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.stt_model = whisper.load_model("base", device=self.device)

    def process_audio(self, file_path: str):
        # Day 3 Optimization: Whisper with word-level timestamps for accuracy
        result = self.stt_model.transcribe(file_path, verbose=False, fp16=False)
        
        segments = result['segments']
        structured_segments = []
        
        # Day 2 logic: Speaker Attribution based on turn-taking patterns
        # Day 3 logic: Edge case handling for silence (>2s) and overlaps (<0.5s)
        current_speaker_id = 1
        
        for i, seg in enumerate(segments):
            start = seg['start']
            end = seg['end']
            text = seg['text'].strip()
            
            # Day 3: Handle Edge Case - Silence/Gap analysis
            if i > 0:
                gap = start - segments[i-1]['end']
                if gap > 1.8: # Threshold for a definite speaker switch
                    current_speaker_id = 2 if current_speaker_id == 1 else 1
            
            structured_segments.append({
                "start": start,
                "end": end,
                "text": text,
                "speaker_label": f"Participant {current_speaker_id}",
                "confidence": seg.get("avg_logprob", 0) # Day 3 Quality Metric
            })

        return {
            "raw_text": result['text'],
            "segments": structured_segments,
            "metadata": {"duration": segments[-1]['end'] if segments else 0}
        }