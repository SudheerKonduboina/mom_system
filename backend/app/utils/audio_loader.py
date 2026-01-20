import soundfile as sf
import torch
import numpy as np
import librosa

def load_audio_safe(path, target_sr=16000):
    audio, sr = sf.read(path)

    # Stereo → Mono
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)

    # Resample if needed
    if sr != target_sr:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
        sr = target_sr

    waveform = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
    return waveform, sr
