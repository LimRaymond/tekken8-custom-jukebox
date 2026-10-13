"""Cut a song to a jukebox slot's intro and loop."""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd

import numpy as np
from scipy.signal import resample_poly


@dataclass(frozen=True)
class FittedAudio:
    intro: np.ndarray
    loop: np.ndarray
    sample_rate: int
    channels: int


def prepare_audio(
    samples: np.ndarray,
    source_rate: int,
    *,
    intro_samples: int,
    loop_samples: int,
    target_rate: int,
    target_channels: int,
    crossfade_ms: float = 20.0,
    boost: bool = True,
) -> FittedAudio:
    if intro_samples < 0 or loop_samples <= 0:
        raise ValueError("intro and loop lengths must be positive")
    if source_rate <= 0 or target_rate <= 0 or target_channels <= 0:
        raise ValueError("sample rate and channel count must be positive")
    audio = _as_channels(np.asarray(samples, dtype=np.float64), target_channels)
    if audio.shape[0] == 0:
        raise ValueError("empty audio")
    audio = _resample(audio, source_rate, target_rate)
    if audio.shape[0] == 0:
        raise ValueError("empty audio")
    need = intro_samples + loop_samples
    if audio.shape[0] < need:
        repeats = int(np.ceil(need / audio.shape[0]))
        audio = np.tile(audio, (repeats, 1))
    audio = np.ascontiguousarray(audio[:need])
    if boost:
        audio = _raise_loudness(audio)
    intro = audio[:intro_samples]
    fade = int(round(crossfade_ms * target_rate / 1000.0))
    loop = _crossfade_loop(audio[intro_samples:need], fade)
    return FittedAudio(intro=intro, loop=loop, sample_rate=target_rate, channels=target_channels)


def _as_channels(samples: np.ndarray, target_channels: int) -> np.ndarray:
    if samples.ndim == 1:
        samples = samples[:, None]
    if samples.ndim != 2:
        raise ValueError("audio must be mono or a 2d channel array")
    if samples.shape[0] == 0:
        return np.zeros((0, target_channels), dtype=np.float64)
    source_channels = samples.shape[1]
    if source_channels == target_channels:
        return samples
    if target_channels == 1:
        return samples.mean(axis=1, keepdims=True)
    if source_channels == 1:
        return np.repeat(samples, target_channels, axis=1)
    if source_channels > target_channels:
        return samples[:, :target_channels]
    padded = np.zeros((samples.shape[0], target_channels), dtype=np.float64)
    padded[:, :source_channels] = samples
    padded[:, source_channels:] = samples[:, -1:]
    return padded


def _raise_loudness(audio: np.ndarray) -> np.ndarray:
    """Bring a quiet master up toward game-music loudness, then soften the peaks."""
    rms = float(np.sqrt(np.mean(np.square(audio))))
    if rms < 1e-5:
        return audio
    target_rms = 10 ** (-8.0 / 20.0)
    max_gain = 10 ** (12.0 / 20.0)
    gain = min(target_rms / rms, max_gain)
    boosted = audio * gain
    ceiling = 0.98
    return np.tanh(boosted / ceiling) * ceiling


def _resample(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return audio
    divisor = gcd(source_rate, target_rate)
    return resample_poly(audio, target_rate // divisor, source_rate // divisor, axis=0)


def _crossfade_loop(loop: np.ndarray, fade: int) -> np.ndarray:
    fade = min(max(fade, 0), loop.shape[0] // 2)
    if fade <= 0:
        return loop.copy()
    out = loop.copy()
    ramp = np.linspace(0.0, np.pi / 2.0, fade, endpoint=True)
    fade_out = np.cos(ramp)[:, None]
    fade_in = np.sin(ramp)[:, None]
    if fade == 1:
        target = loop[:1]
    else:
        target = np.concatenate([loop[1:fade], loop[:1]], axis=0)
    out[-fade:] = loop[-fade:] * fade_out + target * fade_in
    return out
