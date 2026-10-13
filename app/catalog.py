"""Jukebox slot catalog built from the user's own Wwise extract."""

from __future__ import annotations

import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path

CODEC_BY_FORMAT = {
    0x0001: "pcm",
    0x0002: "adpcm",
    0xFFFE: "pcm",
    0xFFFF: "vorbis",
    0x3039: "opus",
    0x3040: "opus",
    0x3041: "opus",
}


class CatalogError(Exception):
    """The extract or catalog file cannot be used."""


@dataclass(frozen=True)
class WemInfo:
    codec: str
    channels: int
    sample_rate: int
    samples: int


# Tekken 8's own tracks stay the original audio. A few older slots do the same.
UNUSABLE_SLOT_NAMES = frozenset(
    {
        "El Condor / TEKKEN REVOLUTION",
        "Yodeling in meadow hill / TEKKEN 6",
    }
)


def slot_disabled(name: str) -> bool:
    game = name.rsplit("/", 1)[-1].strip()
    return game == "TEKKEN 8" or name in UNUSABLE_SLOT_NAMES


@dataclass(frozen=True)
class Slot:
    id: str
    name: str
    sample_rate: int
    channels: int
    codec: str
    intro_samples: int
    loop_samples: int
    intro_asset: str
    loop_asset: str


@dataclass(frozen=True)
class Catalog:
    game_version: str | None
    slots: tuple[Slot, ...]

    @property
    def install_ready(self) -> bool:
        return bool(self.game_version) and bool(self.slots)

    def slot_by_id(self, slot_id: str) -> Slot:
        for slot in self.slots:
            if slot.id == slot_id:
                return slot
        raise CatalogError(f"Unknown jukebox slot {slot_id}")


def load_catalog(path: Path) -> Catalog:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Could not read catalog {path}") from exc
    version = raw.get("game_version")
    if version is not None and not isinstance(version, str):
        raise CatalogError("game_version must be a string or null")
    slots = tuple(_slot_from_dict(item) for item in raw.get("slots", []))
    ids = [slot.id for slot in slots]
    if len(ids) != len(set(ids)):
        raise CatalogError("Catalog has duplicate slot ids")
    return Catalog(game_version=version or None, slots=slots)


def save_catalog(catalog: Catalog, path: Path) -> None:
    payload = {
        "game_version": catalog.game_version,
        "slots": [asdict(slot) for slot in catalog.slots],
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def import_extract(extract_dir: Path, output_path: Path) -> Catalog:
    root = Path(extract_dir)
    name_map_path = root / "name_map.json"
    try:
        name_map = json.loads(name_map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Could not read {name_map_path}") from exc
    version = name_map.get("game_version")
    if not isinstance(version, str) or not version.strip():
        raise CatalogError("name_map.json needs a game_version string")
    songs = name_map.get("songs")
    if not isinstance(songs, list) or not songs:
        raise CatalogError("name_map.json needs a songs list")

    slots: list[Slot] = []
    seen: set[str] = set()
    for song in songs:
        slot = _slot_from_song(root, song)
        if slot.id in seen:
            raise CatalogError(f"Duplicate song id {slot.id}")
        seen.add(slot.id)
        slots.append(slot)
    catalog = Catalog(game_version=version.strip(), slots=tuple(slots))
    save_catalog(catalog, output_path)
    return catalog


def parse_wem(path: Path) -> WemInfo:
    data = Path(path).read_bytes()
    if len(data) < 12 or data[:4] not in (b"RIFF", b"RIFX") or data[8:12] != b"WAVE":
        raise CatalogError(f"{path} is not a Wwise wem")
    endian = "<" if data[:4] == b"RIFF" else ">"
    chunks = _chunks(data, endian)
    fmt = chunks.get("fmt ")
    if fmt is None or len(fmt) < 16:
        raise CatalogError(f"{path} is missing a fmt chunk")
    format_tag, channels, sample_rate, _avg, _block, bits = struct.unpack(
        endian + "HHIIHH", fmt[:16]
    )
    if channels <= 0 or sample_rate <= 0:
        raise CatalogError(f"{path} has an unusable fmt chunk")
    try:
        codec = CODEC_BY_FORMAT[format_tag]
    except KeyError as exc:
        raise CatalogError(f"{path} uses unsupported Wwise codec {format_tag:#06x}") from exc
    samples = _sample_count(path, codec, chunks, fmt, channels, bits, endian)
    return WemInfo(codec=codec, channels=channels, sample_rate=sample_rate, samples=samples)


def _chunks(data: bytes, endian: str) -> dict[str, bytes]:
    pos = 12
    found: dict[str, bytes] = {}
    while pos + 8 <= len(data):
        fourcc = data[pos : pos + 4].decode("latin1")
        size = struct.unpack(endian + "I", data[pos + 4 : pos + 8])[0]
        start = pos + 8
        end = start + size
        if end > len(data):
            raise CatalogError("wem chunk extends past the end of the file")
        found[fourcc] = data[start:end]
        pos = end
    return found


def _sample_count(
    path: Path,
    codec: str,
    chunks: dict[str, bytes],
    fmt: bytes,
    channels: int,
    bits: int,
    endian: str,
) -> int:
    if codec == "pcm":
        data = chunks.get("data")
        width = bits // 8
        if data is None or width <= 0 or channels <= 0 or len(data) % (channels * width):
            raise CatalogError(f"{path} is missing a PCM sample count")
        return len(data) // (channels * width)
    if codec == "vorbis":
        vorb = chunks.get("vorb")
        if vorb is not None and len(vorb) >= 4:
            samples = struct.unpack(endian + "i", vorb[:4])[0]
        elif len(fmt) >= 0x1C:
            samples = struct.unpack(endian + "i", fmt[0x18:0x1C])[0]
        else:
            samples = 0
    elif codec in {"opus", "adpcm"}:
        if len(fmt) < 0x1C:
            raise CatalogError(f"{path} is missing a sample count")
        samples = struct.unpack(endian + "i", fmt[0x18:0x1C])[0]
    else:
        samples = 0
    if samples <= 0:
        raise CatalogError(f"{path} is missing a sample count")
    return samples


def _slot_from_song(root: Path, song: object) -> Slot:
    if not isinstance(song, dict):
        raise CatalogError("Each song in name_map.json must be an object")
    required = ("id", "name", "intro_wem", "loop_wem", "intro_asset", "loop_asset")
    missing = [key for key in required if not isinstance(song.get(key), str) or not song[key].strip()]
    if missing:
        raise CatalogError(f"Song is missing {', '.join(missing)}")
    intro = parse_wem(_find_wem(root, song["intro_wem"]))
    loop = parse_wem(_find_wem(root, song["loop_wem"]))
    if (intro.codec, intro.channels, intro.sample_rate) != (
        loop.codec,
        loop.channels,
        loop.sample_rate,
    ):
        raise CatalogError(f"{song['name']} intro and loop do not use the same codec, rate, and channels")
    return Slot(
        id=song["id"].strip(),
        name=song["name"].strip(),
        sample_rate=intro.sample_rate,
        channels=intro.channels,
        codec=intro.codec,
        intro_samples=intro.samples,
        loop_samples=loop.samples,
        intro_asset=_clean_asset(song["intro_asset"]),
        loop_asset=_clean_asset(song["loop_asset"]),
    )


def _find_wem(root: Path, name: str) -> Path:
    candidates = [root / name, root / "wems" / name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise CatalogError(f"Could not find {name} in the extract")


def _clean_asset(value: str) -> str:
    asset = value.strip().replace("\\", "/")
    parts = asset.split("/")
    if not asset or asset.startswith("/") or ".." in parts:
        raise CatalogError(f"Asset path is not usable: {value}")
    return asset


def _slot_from_dict(item: object) -> Slot:
    if not isinstance(item, dict):
        raise CatalogError("Catalog slot is not an object")
    try:
        slot = Slot(
            id=str(item["id"]),
            name=str(item["name"]),
            sample_rate=int(item["sample_rate"]),
            channels=int(item["channels"]),
            codec=str(item["codec"]),
            intro_samples=int(item["intro_samples"]),
            loop_samples=int(item["loop_samples"]),
            intro_asset=str(item["intro_asset"]),
            loop_asset=str(item["loop_asset"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CatalogError("Catalog slot is missing a field") from exc
    if slot.sample_rate <= 0 or slot.channels <= 0 or slot.intro_samples < 0 or slot.loop_samples <= 0:
        raise CatalogError(f"Slot {slot.id} has a non-positive length or rate")
    if slot.codec not in {"pcm", "adpcm", "vorbis", "opus"}:
        raise CatalogError(f"Slot {slot.id} has an unknown codec")
    return slot
