"""Turn the public Jukebox WEM List into a slot catalog."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from app.catalog import Catalog, CatalogError, Slot, save_catalog

SHEET_ID = "1H379TN3fsntA9NV5UEKiaY3uLCpF4Opu2m6SHSdk4Lk"
SHEET_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
)
SAMPLE_RATE = 48000
CHANNELS = 2
CODEC = "vorbis"
MEDIA_DIR = "Polaris/Content/WwiseAudio/Media"


def parse_jukebox_sheet(text: str) -> Catalog:
    rows = csv.reader(io.StringIO(text.lstrip("\ufeff")))
    header: list[str] | None = None
    slots: list[Slot] = []
    seen_ids: set[str] = set()
    for row in rows:
        if header is None:
            if "Title" in row and "Intro ID" in row and "Loop ID" in row:
                header = row
            continue
        slot = _slot_from_row(row, header, seen_ids)
        if slot is None:
            continue
        seen_ids.add(slot.id)
        slots.append(slot)
    if header is None or not slots:
        raise CatalogError("The jukebox sheet has no song rows")
    return Catalog(game_version=None, slots=tuple(slots))


def write_catalog(catalog: Catalog, path: Path) -> None:
    save_catalog(catalog, path)


def _slot_from_row(row: list[str], header: list[str], seen_ids: set[str]) -> Slot | None:
    fields = {name: (row[index].strip() if index < len(row) else "") for index, name in enumerate(header)}
    title = fields.get("Title", "")
    intro_id = fields.get("Intro ID", "")
    loop_id = fields.get("Loop ID", "")
    if not title or not loop_id.isdigit():
        return None
    loop_samples = _length_to_samples(fields.get("Loop Length", ""))
    if loop_samples <= 0:
        raise CatalogError(f"{title} has no loop length")
    if intro_id == "-":
        intro_samples = 0
        intro_asset = f"{MEDIA_DIR}/{loop_id}.wem"
    elif intro_id.isdigit():
        intro_length = fields.get("Intro Length", "")
        intro_samples = 0 if intro_length == "-" else _length_to_samples(intro_length)
        intro_asset = f"{MEDIA_DIR}/{intro_id}.wem"
    else:
        return None
    number = fields.get("No", "")
    slot_id = number if number else _slug(title)
    if slot_id in seen_ids:
        slot_id = f"{slot_id}-{intro_id}"
    return Slot(
        id=slot_id,
        name=title,
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        codec=CODEC,
        intro_samples=intro_samples,
        loop_samples=loop_samples,
        intro_asset=intro_asset,
        loop_asset=f"{MEDIA_DIR}/{loop_id}.wem",
    )


def _length_to_samples(value: str) -> int:
    match = re.fullmatch(r"(\d+):(\d{2})", value.strip())
    if match is None:
        raise CatalogError(f"Unusable length {value!r}")
    minutes, seconds = int(match.group(1)), int(match.group(2))
    if seconds >= 60:
        raise CatalogError(f"Unusable length {value!r}")
    return (minutes * 60 + seconds) * SAMPLE_RATE


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "slot"
