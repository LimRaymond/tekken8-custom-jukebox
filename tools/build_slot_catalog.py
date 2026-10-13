"""Import a Tekken 8 jukebox slot catalog from a local Wwise extract.

The extract directory needs name_map.json and the .wem files it names.
No game audio is copied into the catalog: only names, lengths, codecs, and
asset paths.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.catalog import CatalogError, import_extract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extract_dir", type=Path, help="Folder containing name_map.json and wems/")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/slots.json"),
        help="Catalog file to write (default: data/slots.json)",
    )
    args = parser.parse_args(argv)
    try:
        catalog = import_extract(args.extract_dir, args.output)
    except CatalogError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Wrote {len(catalog.slots)} slots for game version {catalog.game_version} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
