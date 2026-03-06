# app/speaker_diarization.py
# Speaker diarization using pyannote.audio with timestamp alignment to Whisper segments

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("SpeakerDiarization")


class SpeakerDiarizer:
    """
    Identifies who speaks when using pyannote.audio,
    then aligns results with Whisper transcript segments.
    """

    def __init__(self):
        self._pipeline = None

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            from app.model_manager import model_manager
            self._pipeline = model_manager.get_diarizer()
            return self._pipeline
        except Exception as e:
            logger.error(f"Failed to load diarization pipeline: {e}")
            return None

    def diarize(self, audio_path: str) -> List[Dict]:
        """
        Run speaker diarization on audio file.
        Returns: [{speaker: "SPEAKER_00", start: 0.5, end: 3.2}, ...]
        """
        pipeline = self._load_pipeline()
        if pipeline is None:
            logger.warning("Diarization unavailable. Returning empty segments.")
            return []

        try:
            diarization = pipeline(audio_path)
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    "speaker": speaker,
                    "start": round(turn.start, 3),
                    "end": round(turn.end, 3),
                })
            logger.info(f"Diarization complete: {len(segments)} segments, "
                        f"{len(set(s['speaker'] for s in segments))} speakers")
            return segments
        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            return []

    def align_with_transcript(self, diarization_segments: List[Dict],
                               whisper_segments: List[Dict]) -> List[Dict]:
        """
        Align diarization speaker labels with Whisper transcript segments.
        Uses Intersection over Union (IoU) for time-overlap matching.

        Args:
            diarization_segments: [{speaker, start, end}, ...]
            whisper_segments: [{start, end, text, confidence}, ...]

        Returns: [{speaker, start, end, text, confidence}, ...]
        """
        if not diarization_segments:
            return [{"speaker": "Speaker", **seg} for seg in whisper_segments]

        aligned = []
        for w_seg in whisper_segments:
            w_start = w_seg.get("start", 0)
            w_end = w_seg.get("end", 0)

            best_speaker = "Unknown"
            best_overlap = 0

            for d_seg in diarization_segments:
                d_start = d_seg["start"]
                d_end = d_seg["end"]

                # Calculate overlap
                overlap_start = max(w_start, d_start)
                overlap_end = min(w_end, d_end)
                overlap = max(0, overlap_end - overlap_start)

                # IoU = overlap / union
                union = max(0.001, (w_end - w_start) + (d_end - d_start) - overlap)
                iou = overlap / union

                if iou > best_overlap:
                    best_overlap = iou
                    best_speaker = d_seg["speaker"]

            # Only assign if overlap is meaningful (> 30%)
            if best_overlap < 0.3:
                best_speaker = "Unknown"

            aligned.append({
                "speaker": best_speaker,
                "start": w_start,
                "end": w_end,
                "text": w_seg.get("text", ""),
                "confidence": w_seg.get("confidence", 0),
            })

        return aligned

    def build_speaker_transcript(self, aligned_segments: List[Dict]) -> str:
        """Build a readable speaker-labeled transcript string."""
        if not aligned_segments:
            return ""

        lines = []
        current_speaker = None

        for seg in aligned_segments:
            speaker = seg.get("speaker", "Unknown")
            text = seg.get("text", "").strip()
            if not text:
                continue

            if speaker != current_speaker:
                current_speaker = speaker
                lines.append(f"\n{speaker}: {text}")
            else:
                lines.append(f" {text}")

        return "".join(lines).strip()

    def get_speaking_times(self, aligned_segments: List[Dict]) -> Dict[str, float]:
        """Calculate total speaking time per speaker in seconds."""
        times: Dict[str, float] = {}
        for seg in aligned_segments:
            speaker = seg.get("speaker", "Unknown")
            duration = seg.get("end", 0) - seg.get("start", 0)
            times[speaker] = times.get(speaker, 0) + max(0, duration)
        return {k: round(v, 2) for k, v in times.items()}
