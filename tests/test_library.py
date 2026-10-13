"""Library drop, slot swap, and saved assignments."""

import json
import wave
from pathlib import Path

from app.catalog import Catalog, Slot
from app.library import Library


def _catalog() -> Catalog:
    slots = (
        Slot("brief", "Brief Theme", 8000, 1, "pcm", 8, 8, "Polaris/Content/brief-intro.wem", "Polaris/Content/brief-loop.wem"),
        Slot("anthem", "Anthem", 8000, 1, "pcm", 8, 24, "Polaris/Content/anthem-intro.wem", "Polaris/Content/anthem-loop.wem"),
    )
    return Catalog("build-100", slots)


def _wav(path: Path, frames: int) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x10" * frames)


def test_adding_wavs_assigns_closest_free_slots_and_remembers_them(tmp_path: Path):
    library = Library(_catalog(), tmp_path / "lib")
    short = tmp_path / "short.wav"
    long = tmp_path / "long.wav"
    _wav(short, 16)
    _wav(long, 32)

    library.add_wav(long)
    library.add_wav(short)

    by_name = {track.name: track for track in library.tracks}
    assert by_name["long"].slot_id == "anthem"
    assert by_name["short"].slot_id == "brief"

    restored = Library.load(_catalog(), tmp_path / "lib")
    restored_names = {track.name: track.slot_id for track in restored.tracks}
    assert restored_names == {"long": "anthem", "short": "brief"}


def test_adding_the_same_wav_twice_keeps_one_song(tmp_path: Path):
    library = Library(_catalog(), tmp_path / "lib")
    song = tmp_path / "song.wav"
    _wav(song, 16)

    library.add_wav(song)
    library.add_wav(song)

    assert len(library.tracks) == 1


def test_slot_swap_exchanges_the_two_songs(tmp_path: Path):
    library = Library(_catalog(), tmp_path / "lib")
    _wav(tmp_path / "short.wav", 16)
    _wav(tmp_path / "long.wav", 32)
    library.add_wav(tmp_path / "long.wav")
    library.add_wav(tmp_path / "short.wav")
    short = next(track for track in library.tracks if track.name == "short")
    long = next(track for track in library.tracks if track.name == "long")

    library.set_slot(short.id, long.slot_id)

    assert next(track for track in library.tracks if track.id == short.id).slot_id == "anthem"
    assert next(track for track in library.tracks if track.id == long.id).slot_id == "brief"
    saved = json.loads((tmp_path / "lib" / "library.json").read_text(encoding="utf-8"))
    assert {item["name"]: item["slot_id"] for item in saved["tracks"]} == {"short": "anthem", "long": "brief"}
