"""Read and write PCM wav files."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        rate = handle.getframerate()
        width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())
    if channels <= 0 or rate <= 0 or not frames:
        raise ValueError(f"{path} is empty")
    if width == 1:
        data = (np.frombuffer(frames, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        data = np.frombuffer(frames, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        samples = raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16)
        samples = np.where(samples >= 0x800000, samples - 0x1000000, samples)
        data = samples.astype(np.float64) / 8388608.0
    elif width == 4:
        data = np.frombuffer(frames, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"{path} uses an unsupported wav sample width")
    return data.reshape(-1, channels), rate


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    samples = np.asarray(audio, dtype=np.float64)
    if samples.ndim == 1:
        samples = samples[:, None]
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(pcm.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
