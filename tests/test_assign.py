"""Closest unique jukebox slot assignment."""

from app.audio.assign import SongInfo, assign_slots
from app.catalog import Slot


def _slot(slot_id: str, intro: int, loop: int, rate: int = 48000) -> Slot:
    return Slot(
        id=slot_id,
        name=slot_id,
        sample_rate=rate,
        channels=2,
        codec="vorbis",
        intro_samples=intro,
        loop_samples=loop,
        intro_asset=f"Polaris/Content/{slot_id}-intro.wem",
        loop_asset=f"Polaris/Content/{slot_id}-loop.wem",
    )


def test_longer_song_takes_the_longer_slot():
    songs = [
        SongInfo("short", sample_count=200, sample_rate=48000),
        SongInfo("long", sample_count=1000, sample_rate=48000),
    ]
    slots = [_slot("brief", 100, 100), _slot("anthem", 100, 900)]

    assigned = {item.song_id: item for item in assign_slots(songs, slots)}

    assert assigned["short"].slot_id == "brief"
    assert assigned["short"].label == "fits"
    assert assigned["long"].slot_id == "anthem"
    assert assigned["long"].label == "fits"


def test_label_reports_cut_seconds_and_early_repeat():
    long_song = [SongInfo("long", sample_count=48000 * 20, sample_rate=48000)]
    tiny_song = [SongInfo("tiny", sample_count=48000, sample_rate=48000)]

    cut = assign_slots(long_song, [_slot("eight", 48000, 48000 * 7)])
    repeat = assign_slots(tiny_song, [_slot("ten", 48000, 48000 * 9)])

    assert cut[0].label == "cuts 12s"
    assert repeat[0].label == "repeats early"


def test_songs_never_share_a_slot_and_overflow_stays_unassigned():
    songs = [
        SongInfo("one", sample_count=100, sample_rate=48000),
        SongInfo("two", sample_count=100, sample_rate=48000),
        SongInfo("three", sample_count=100, sample_rate=48000),
    ]
    slots = [_slot("a", 50, 50), _slot("b", 50, 50)]

    assigned = assign_slots(songs, slots)

    used = [item.slot_id for item in assigned if item.slot_id is not None]
    assert len(used) == len(set(used)) == 2
    unassigned = [item for item in assigned if item.slot_id is None]
    assert len(unassigned) == 1
    assert unassigned[0].label == "unassigned"


def test_unusable_slot_is_not_offered_to_a_new_song():
    songs = [SongInfo("custom", sample_count=48000 * 100, sample_rate=48000)]
    slots = [
        _slot("Colosseum (Normal) / TEKKEN 8", 48000 * 14, 48000 * 119),
        _slot("Marine Stadium / TEKKEN", 48000 * 45, 48000 * 41),
    ]

    assigned = assign_slots(songs, slots)

    assert assigned[0].slot_id == "Marine Stadium / TEKKEN"


def test_locked_slot_is_kept_and_the_other_song_takes_what_remains():
    songs = [
        SongInfo("kept", sample_count=1000, sample_rate=48000),
        SongInfo("other", sample_count=200, sample_rate=48000),
    ]
    slots = [_slot("brief", 100, 100), _slot("anthem", 100, 900)]

    assigned = {item.song_id: item for item in assign_slots(songs, slots, locked={"kept": "brief"})}

    assert assigned["kept"].slot_id == "brief"
    assert assigned["other"].slot_id == "anthem"
