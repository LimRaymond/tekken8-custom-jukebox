"""Launch the Custom Jukebox window."""

from __future__ import annotations

import os
from pathlib import Path

from app.catalog import load_catalog
from app.library import Library
from app.ui.api import JukeboxApi


def create_api(root: Path | None = None) -> JukeboxApi:
    project_root = root or Path(__file__).resolve().parents[1]
    catalog = load_catalog(project_root / "data" / "slots.json")
    storage = Path(os.environ.get("JUKEBOX_HOME", Path.home() / ".local" / "share" / "tekken8-custom-jukebox"))
    library = Library.load(catalog, storage)
    return JukeboxApi(library, catalog, catalog_path=project_root / "data" / "slots.json")


def main() -> None:
    import webview

    page = Path(__file__).resolve().parent / "ui" / "index.html"
    # A \\wsl$\ path is not a valid file URI, so WebView2 has to receive the HTML itself.
    webview.create_window(
        "Tekken 8 Custom Jukebox",
        html=page.read_text(encoding="utf-8"),
        js_api=create_api(),
        width=1040,
        height=760,
        min_size=(760, 560),
    )
    webview.start()


if __name__ == "__main__":
    main()
