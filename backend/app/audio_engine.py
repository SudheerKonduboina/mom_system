import re
import logging

logger = logging.getLogger("AudioEngine")


class AudioEngine:
    def __init__(self):
        from app.model_manager import model_manager
        self._model_manager = model_manager
        self._preprocessor = None

    def _get_preprocessor(self):
        if self._preprocessor is None:
            try:
                from app.audio_preprocessor import AudioPreprocessor
                self._preprocessor = AudioPreprocessor()
            except Exception as e:
                logger.warning(f"Audio preprocessor unavailable: {e}")
        return self._preprocessor

    def process_audio(self, file_path: str):
        """Full audio processing pipeline: preprocess → transcribe → clean."""
        logger.info(f"Processing audio: {file_path}")

        # Step 1: Preprocess (noise reduction, normalization, format conversion)
        preprocess_result = {"processed_path": file_path, "quality_score": 50,
                             "duration_sec": 0, "warnings": []}
        preprocessor = self._get_preprocessor()
        if preprocessor:
            try:
                preprocess_result = preprocessor.process(file_path)
                logger.info(f"Preprocessing done: quality={preprocess_result['quality_score']}, "
                            f"duration={preprocess_result['duration_sec']}s")
            except Exception as e:
                logger.warning(f"Preprocessing failed, using raw file: {e}")

        processed_path = preprocess_result.get("processed_path", file_path)

        # Step 2: Whisper transcription
        model = self._model_manager.get_whisper()
        device = self._model_manager.device

        initial_prompt = (
            "This is a meeting recording. The discussion covers agenda items, decisions, and action items. "
            "Terms like 'STT', 'MOM', 'AI', 'Backend', and 'Frontend' might be used."
        )

        result = model.transcribe(
            processed_path,
            task="translate",
            language=None,
            verbose=False,
            fp16=(device == "cuda"),
            temperature=0.0,
            initial_prompt=initial_prompt
        )

        # Step 3: Clean text
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

        # Step 4: Release GPU memory after processing
        self._model_manager._clear_gpu()

        return {
            "text": clean_text,
            "segments": segments,
            "metadata": {
                "language": result.get("language", "unknown"),
                "duration": segments[-1]["end"] if segments else 0
            },
            "preprocessing": {
                "quality_score": preprocess_result.get("quality_score", 0),
                "duration_sec": preprocess_result.get("duration_sec", 0),
                "warnings": preprocess_result.get("warnings", []),
                "processed_path": processed_path
            }
        }

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""

        text = text.strip()
        text = re.sub(r"\s+", " ", text)

        # Remove filler words
        text = re.sub(r"\b(um+|uh+|hmm+|yeah|ya|uh-huh|right|like|you know|sort of|basically)\b",
                       "", text, flags=re.I)

        # Remove Whisper hallucinations
        text = re.sub(r"(i\s+don'?t\s+know[\s,]*){2,}", "", text, flags=re.I)
        text = re.sub(r"(thank\s+you\s+for\s+watching[\s,]*){1,}", "", text, flags=re.I)
        text = re.sub(r"(please\s+subscribe[\s,]*){1,}", "", text, flags=re.I)

        # Remove repeated tokens/phrases
        text = re.sub(r"(\b[\w']+\b)(\s+\1){4,}", r"\1", text, flags=re.I)
        text = re.sub(r"(.+)(\s+\1){2,}", r"\1", text, flags=re.I)

        return text.strip()
