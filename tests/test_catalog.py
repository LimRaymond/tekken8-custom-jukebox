"""Slot catalog import from a local Wwise extract."""

import json
import struct
from pathlib import Path

import pytest

from app.catalog import CatalogError, import_extract, load_catalog


def _chunk(fourcc: bytes, body: bytes) -> bytes:
    return fourcc + struct.pack("<I", len(body)) + body


def _wem(path: Path, *, codec: str, channels: int, rate: int, samples: int) -> None:
    if codec == "vorbis":
        fmt = bytearray(0x42)
        struct.pack_into("<H", fmt, 0x00, 0xFFFF)
        struct.pack_into("<H", fmt, 0x02, channels)
        struct.pack_into("<I", fmt, 0x04, rate)
        struct.pack_into("<H", fmt, 0x10, 0x30)
        struct.pack_into("<i", fmt, 0x18, samples)
        fmt_body = bytes(fmt)
    elif codec == "pcm":
        block = channels * 2
        fmt_body = struct.pack("<HHIIHH", 0x0001, channels, rate, rate * block, block, 16)
    elif codec == "opus":
        fmt = bytearray(0x28)
        struct.pack_into("<H", fmt, 0x00, 0x3041)
        struct.pack_into("<H", fmt, 0x02, channels)
        struct.pack_into("<I", fmt, 0x04, rate)
        struct.pack_into("<H", fmt, 0x10, 0x10)
        struct.pack_into("<i", fmt, 0x18, samples)
        fmt_body = bytes(fmt)
    else:
        raise AssertionError(codec)
    data = b"\x00" * 8
    if codec == "pcm":
        data = b"\x00\x00" * (samples * channels)
    body = b"WAVE" + _chunk(b"fmt ", fmt_body) + _chunk(b"data", data)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def _extract(root: Path) -> None:
    wems = root / "wems"
    wems.mkdir()
    _wem(wems / "111.wem", codec="vorbis", channels=2, rate=48000, samples=144000)
    _wem(wems / "222.wem", codec="vorbis", channels=2, rate=48000, samples=960000)
    (root / "name_map.json").write_text(
        json.dumps(
            {
                "game_version": "build-100",
                "songs": [
                    {
                        "id": "my-last-stand",
                        "name": "My Last Stand",
                        "intro_wem": "111.wem",
                        "loop_wem": "222.wem",
                        "intro_asset": "Polaris/Content/WwiseAudio/Media/111.wem",
                        "loop_asset": "Polaris/Content/WwiseAudio/Media/222.wem",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_import_extract_records_slot_lengths_codec_and_paths(tmp_path: Path):
    extract = tmp_path / "extract"
    extract.mkdir()
    _extract(extract)
    dest = tmp_path / "slots.json"

    catalog = import_extract(extract, dest)

    assert catalog.game_version == "build-100"
    assert len(catalog.slots) == 1
    slot = catalog.slots[0]
    assert slot.id == "my-last-stand"
    assert slot.name == "My Last Stand"
    assert slot.sample_rate == 48000
    assert slot.channels == 2
    assert slot.codec == "vorbis"
    assert slot.intro_samples == 144000
    assert slot.loop_samples == 960000
    assert slot.intro_asset == "Polaris/Content/WwiseAudio/Media/111.wem"
    assert slot.loop_asset == "Polaris/Content/WwiseAudio/Media/222.wem"
    loaded = load_catalog(dest)
    assert loaded == catalog


def test_import_reads_pcm_and_opus_sample_counts(tmp_path: Path):
    wems = tmp_path / "wems"
    wems.mkdir()
    _wem(wems / "a.wem", codec="pcm", channels=1, rate=44100, samples=1000)
    _wem(wems / "b.wem", codec="pcm", channels=1, rate=44100, samples=1500)
    _wem(wems / "c.wem", codec="opus", channels=2, rate=48000, samples=2000)
    _wem(wems / "d.wem", codec="opus", channels=2, rate=48000, samples=2500)
    (tmp_path / "name_map.json").write_text(
        json.dumps(
            {
                "game_version": "build-pcm",
                "songs": [
                    {
                        "id": "pcm-song",
                        "name": "PCM Song",
                        "intro_wem": "a.wem",
                        "loop_wem": "b.wem",
                        "intro_asset": "Polaris/Content/A.wem",
                        "loop_asset": "Polaris/Content/B.wem",
                    },
                    {
                        "id": "opus-song",
                        "name": "Opus Song",
                        "intro_wem": "c.wem",
                        "loop_wem": "d.wem",
                        "intro_asset": "Polaris/Content/C.wem",
                        "loop_asset": "Polaris/Content/D.wem",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    catalog = import_extract(tmp_path, tmp_path / "slots.json")

    pcm, opus = catalog.slots
    assert pcm.codec == "pcm"
    assert pcm.intro_samples == 1000
    assert pcm.loop_samples == 1500
    assert pcm.sample_rate == 44100
    assert pcm.channels == 1
    assert opus.codec == "opus"
    assert opus.intro_samples == 2000
    assert opus.loop_samples == 2500


def test_import_rejects_a_vorbis_wem_without_a_sample_count(tmp_path: Path):
    wems = tmp_path / "wems"
    wems.mkdir()
    fmt = struct.pack("<HHIIHHH", 0xFFFF, 2, 48000, 0, 0, 0, 0)
    body = b"WAVE" + _chunk(b"fmt ", fmt) + _chunk(b"data", b"\x00" * 4)
    (wems / "111.wem").write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
    (wems / "222.wem").write_bytes((wems / "111.wem").read_bytes())
    (tmp_path / "name_map.json").write_text(
        json.dumps(
            {
                "game_version": "build-100",
                "songs": [
                    {
                        "id": "broken",
                        "name": "Broken",
                        "intro_wem": "111.wem",
                        "loop_wem": "222.wem",
                        "intro_asset": "Polaris/Content/111.wem",
                        "loop_asset": "Polaris/Content/222.wem",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="sample count"):
        import_extract(tmp_path, tmp_path / "slots.json")


def test_shipped_catalog_loads_the_jukebox_sheet():
    catalog = load_catalog(Path("data/slots.json"))

    assert catalog.game_version is None
    assert catalog.install_ready is False
    assert len(catalog.slots) >= 400
    first = catalog.slots[0]
    assert first.name == "Character Select (Arcade ver.) / TEKKEN"
    assert first.intro_samples == 48000
    assert first.loop_samples == 7 * 48000
    assert first.intro_asset == "Polaris/Content/WwiseAudio/Media/58037268.wem"
