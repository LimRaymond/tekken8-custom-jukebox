"""Plain-language readiness for install."""

from __future__ import annotations

from pathlib import Path

from app.catalog import Catalog
from app.mod.install import read_game_version


def describe_setup(
    catalog: Catalog,
    game_dir: Path | None,
    *,
    wwise_console: Path | None,
    project: Path | None,
) -> dict:
    messages: list[str] = []
    game_path = Path(game_dir) if game_dir else None
    game_found = bool(game_path and game_path.is_dir() and (game_path / "Polaris").is_dir())
    if not game_found:
        messages.append("Tekken 8 folder was not found.")
    game_version = read_game_version(game_path) if game_found and game_path else None
    has_slots = bool(catalog.slots)
    if not has_slots:
        messages.append(
            "The slot catalog is empty. Import one with tools/import_jukebox_sheet.py before installing."
        )
    if catalog.game_version:
        version_matches = game_version == catalog.game_version
    else:
        version_matches = True
    if game_found and catalog.game_version and not version_matches:
        if game_version is None:
            messages.append("Could not read the installed game version.")
        else:
            messages.append(
                f"Game version {game_version} does not match the slot catalog version {catalog.game_version}."
            )
    wwise_found = bool(wwise_console and Path(wwise_console).is_file())
    project_found = _project_ready(project)
    if not wwise_found:
        messages.append("WwiseConsole was not found. Install Wwise 2023.1 or set WWISE_CONSOLE.")
    if project and Path(project).is_file() and not project_found:
        messages.append(
            "The Wwise project is still the empty template. Create a Wwise 2023.1 project with the "
            "conversion settings listed in wwise/conversions.json and save it over wwise/CustomJukebox.wproj."
        )
    elif not project_found:
        messages.append("The Wwise project template was not found. Set WWISE_PROJECT.")
    install_allowed = game_found and has_slots and version_matches and wwise_found and project_found
    if install_allowed:
        messages.append("Ready to install.")
    return {
        "game_dir": str(game_path) if game_found and game_path else None,
        "game_found": game_found,
        "game_version": game_version,
        "catalog_version": catalog.game_version,
        "version_matches": version_matches,
        "wwise_found": wwise_found,
        "project_found": project_found,
        "catalog_ready": has_slots,
        "slot_count": len(catalog.slots),
        "install_allowed": install_allowed,
        "messages": messages,
    }


def _project_ready(project: Path | None) -> bool:
    if not project or not Path(project).is_file():
        return False
    text = Path(project).read_text(encoding="utf-8", errors="ignore")
    return "JUKEBOX_PLACEHOLDER" not in text
