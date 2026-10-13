"""Saved playlist of wav files and the jukebox slots they replace."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from app.audio.assign import SongInfo, assign_slots
from app.audio.wavio import read_wav
from app.catalog import Catalog


@dataclass
class Track:
    id: str
    name: str
    path: str
    sample_count: int
    sample_rate: int
    channels: int
    slot_id: str | None = None
    locked: bool = False


class Library:
    def __init__(self, catalog: Catalog, storage: Path):
        self.catalog = catalog
        self.storage = Path(storage)
        self.tracks: list[Track] = []
        self.game_dir: str | None = None

    @classmethod
    def load(cls, catalog: Catalog, storage: Path) -> Library:
        library = cls(catalog, storage)
        path = library.storage / "library.json"
        if not path.is_file():
            return library
        raw = json.loads(path.read_text(encoding="utf-8"))
        library.game_dir = raw.get("game_dir")
        for item in raw.get("tracks", []):
            library.tracks.append(
                Track(
                    id=item["id"],
                    name=item["name"],
                    path=item["path"],
                    sample_count=int(item["sample_count"]),
                    sample_rate=int(item["sample_rate"]),
                    channels=int(item["channels"]),
                    slot_id=item.get("slot_id"),
                    locked=bool(item.get("locked", False)),
                )
            )
        library._reassign()
        return library

    def add_wav(self, path: Path) -> Track:
        resolved = Path(path).resolve()
        key = os.path.normcase(str(resolved))
        for track in self.tracks:
            if os.path.normcase(str(Path(track.path))) == key:
                return track
        audio, rate = read_wav(resolved)
        track = Track(
            id=uuid.uuid4().hex,
            name=resolved.stem,
            path=str(resolved),
            sample_count=int(audio.shape[0]),
            sample_rate=rate,
            channels=int(audio.shape[1]),
        )
        self.tracks.append(track)
        self._reassign()
        self.save()
        return track

    def add_bytes(self, name: str, data: bytes) -> Track:
        folder = self.storage / "wavs"
        folder.mkdir(parents=True, exist_ok=True)
        filename = Path(name).name or "song.wav"
        if not filename.lower().endswith(".wav"):
            filename += ".wav"
        destination = folder / f"{uuid.uuid4().hex}-{filename}"
        destination.write_bytes(data)
        track = self.add_wav(destination)
        track.name = Path(filename).stem or track.name
        self.save()
        return track

    def remove(self, track_id: str) -> None:
        self.tracks = [track for track in self.tracks if track.id != track_id]
        self._reassign()
        self.save()

    def set_slot(self, track_id: str, slot_id: str) -> None:
        if slot_id not in {slot.id for slot in self.catalog.slots}:
            raise KeyError(slot_id)
        track = self._track(track_id)
        other = next(
            (item for item in self.tracks if item.id != track.id and item.slot_id == slot_id),
            None,
        )
        previous = track.slot_id
        track.slot_id = slot_id
        track.locked = True
        if other is not None:
            if previous is None:
                other.slot_id = None
                other.locked = False
            else:
                other.slot_id = previous
                other.locked = True
        self._reassign()
        self.save()

    def set_game_dir(self, game_dir: str | None) -> None:
        self.game_dir = game_dir
        self.save()

    def save(self) -> None:
        self.storage.mkdir(parents=True, exist_ok=True)
        payload = {
            "game_dir": self.game_dir,
            "tracks": [asdict(track) for track in self.tracks],
        }
        (self.storage / "library.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _track(self, track_id: str) -> Track:
        for track in self.tracks:
            if track.id == track_id:
                return track
        raise KeyError(track_id)

    def _reassign(self) -> None:
        songs = [
            SongInfo(track.id, track.sample_count, track.sample_rate)
            for track in self.tracks
        ]
        locks = {
            track.id: track.slot_id
            for track in self.tracks
            if track.locked and track.slot_id
        }
        assigned = {
            item.song_id: item.slot_id
            for item in assign_slots(songs, list(self.catalog.slots), locks)
        }
        for track in self.tracks:
            track.slot_id = assigned.get(track.id)
