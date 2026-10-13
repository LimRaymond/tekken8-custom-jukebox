"""Assign each song to the closest free jukebox slot."""

from __future__ import annotations

from dataclasses import dataclass

from app.catalog import Slot, slot_disabled


@dataclass(frozen=True)
class SongInfo:
    id: str
    sample_count: int
    sample_rate: int


@dataclass(frozen=True)
class Assignment:
    song_id: str
    slot_id: str | None
    label: str


def assign_slots(
    songs: list[SongInfo],
    slots: list[Slot],
    locked: dict[str, str] | None = None,
) -> list[Assignment]:
    locks = dict(locked or {})
    slot_by_id = {slot.id: slot for slot in slots}
    used_slots: set[str] = set()
    chosen: dict[str, str] = {}
    for song_id, slot_id in locks.items():
        if slot_id not in slot_by_id or song_id in chosen:
            continue
        if slot_id in used_slots:
            raise ValueError(f"Slot {slot_id} is locked more than once")
        used_slots.add(slot_id)
        chosen[song_id] = slot_id

    pairs: list[tuple[int, int, int, str, str]] = []
    for index, song in enumerate(songs):
        if song.id in chosen:
            continue
        for slot in slots:
            if slot.id in used_slots or slot_disabled(slot.name):
                continue
            waste, shortfall = _waste_shortfall(song, slot)
            pairs.append((waste, shortfall, index, song.id, slot.id))
    pairs.sort()
    claimed_songs: set[str] = set()
    for _waste, _shortfall, _index, song_id, slot_id in pairs:
        if song_id in claimed_songs or slot_id in used_slots:
            continue
        claimed_songs.add(song_id)
        used_slots.add(slot_id)
        chosen[song_id] = slot_id

    songs_by_id = {song.id: song for song in songs}
    results: list[Assignment] = []
    for song in songs:
        slot_id = chosen.get(song.id)
        if slot_id is None:
            results.append(Assignment(song.id, None, "unassigned"))
            continue
        results.append(Assignment(song.id, slot_id, fit_label(songs_by_id[song.id], slot_by_id[slot_id])))
    return results


def fit_label(song: SongInfo, slot: Slot) -> str:
    waste, shortfall = _waste_shortfall(song, slot)
    if waste / slot.sample_rate >= 0.5:
        return f"cuts {round(waste / slot.sample_rate)}s"
    if shortfall / slot.sample_rate >= 0.5:
        return "repeats early"
    return "fits"


def _waste_shortfall(song: SongInfo, slot: Slot) -> tuple[int, int]:
    if song.sample_rate == slot.sample_rate:
        length = song.sample_count
    else:
        length = int(round(song.sample_count * slot.sample_rate / song.sample_rate))
    usable = slot.intro_samples + slot.loop_samples
    return max(0, length - usable), max(0, usable - length)
