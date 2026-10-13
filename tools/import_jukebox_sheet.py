"""Download the Jukebox WEM List and write data/slots.json."""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog import CatalogError, save_catalog
from app.jukebox_sheet import SHEET_CSV_URL, parse_jukebox_sheet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        help="CSV file. Omit to download the public Google Sheet.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/slots.json"),
        help="Catalog file to write (default: data/slots.json)",
    )
    args = parser.parse_args(argv)
    try:
        text = Path(args.source).read_text(encoding="utf-8") if args.source else _download()
        catalog = parse_jukebox_sheet(text)
        save_catalog(catalog, args.output)
    except (CatalogError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Wrote {len(catalog.slots)} slots to {args.output}")
    return 0


def _download() -> str:
    with urllib.request.urlopen(SHEET_CSV_URL, timeout=60) as response:
        return response.read().decode("utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
