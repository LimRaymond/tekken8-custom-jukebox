"""Build the local preview: intro once, then two loops."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.audio.wavio import write_wav


class PreviewError(Exception):
    """Playback could not start."""


def build_preview(intro: np.ndarray, loop: np.ndarray) -> np.ndarray:
    return np.concatenate([intro, loop, loop], axis=0)


def play_preview(
    audio: np.ndarray,
    sample_rate: int,
    player: Callable[[np.ndarray, int], None] | None = None,
) -> None:
    (player or default_player)(audio, sample_rate)


def default_player(audio: np.ndarray, sample_rate: int, starter: Callable[[Path], None] | None = None) -> None:
    if np.asarray(audio).size == 0:
        raise PreviewError("This slot has no audio to preview.")
    path = Path(tempfile.gettempdir()) / "tekken8-jukebox-preview.wav"
    write_wav(path, audio, sample_rate)
    (starter or _start_playback)(path)


def stop_playback(stopper: Callable[[], None] | None = None) -> None:
    (stopper or _stop_playback)()


def _stop_playback() -> None:
    if os.name == "nt":
        import winsound

        winsound.PlaySound(None, winsound.SND_PURGE)
        return
    try:
        import sounddevice as sd
    except (ImportError, OSError):
        return
    sd.stop()


def _start_playback(path: Path) -> None:
    if os.name == "nt":
        import winsound

        winsound.PlaySound(None, winsound.SND_PURGE)
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise PreviewError("No preview player is available.") from exc
    except OSError as exc:
        raise PreviewError("No audio device is available for preview.") from exc
    audio, rate = _read_for_device(path)
    sd.play(audio, rate, blocking=False)


def _read_for_device(path: Path) -> tuple[np.ndarray, int]:
    from app.audio.wavio import read_wav

    return read_wav(path)
