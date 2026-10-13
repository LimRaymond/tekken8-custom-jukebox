"""Locate Tekken 8 and install or remove this app's pak only."""

from __future__ import annotations

import os
from pathlib import Path

PAK_NAME = "z_tekken8_custom_jukebox_P.pak"
STEAM_APP_ID = "1778820"
GAME_FOLDER = "TEKKEN 8"
GAME_HAS_MOD_OPEN = "Close Tekken first. The game still has the mod file open."


def mods_dir(game_dir: Path) -> Path:
    return Path(game_dir) / "Polaris" / "Content" / "Paks" / "Mods"


def install_pak(source: Path, game_dir: Path) -> Path:
    destination = mods_dir(game_dir) / PAK_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{PAK_NAME}.tmp")
    temporary.write_bytes(Path(source).read_bytes())
    try:
        os.replace(temporary, destination)
    except PermissionError as exc:
        raise PermissionError(GAME_HAS_MOD_OPEN) from exc
    return destination


def uninstall_pak(game_dir: Path) -> bool:
    destination = mods_dir(game_dir) / PAK_NAME
    if not destination.is_file():
        return False
    try:
        destination.unlink()
    except PermissionError as exc:
        raise PermissionError(GAME_HAS_MOD_OPEN) from exc
    return True


def read_game_version(game_dir: Path) -> str | None:
    sidecar = Path(game_dir) / "game_version.txt"
    if sidecar.is_file():
        text = sidecar.read_text(encoding="utf-8").strip()
        return text or None
    manifest = Path(game_dir).parent.parent / f"appmanifest_{STEAM_APP_ID}.acf"
    if not manifest.is_file():
        return None
    state = parse_vdf(manifest.read_text(encoding="utf-8")).get("AppState", {})
    build_id = state.get("buildid") if isinstance(state, dict) else None
    return str(build_id) if build_id else None


def find_tekken_dirs(library_vdf: Path) -> list[Path]:
    parsed = parse_vdf(Path(library_vdf).read_text(encoding="utf-8"))
    libraries = parsed.get("libraryfolders", {})
    if not isinstance(libraries, dict):
        return []
    found: list[Path] = []
    for entry in libraries.values():
        if not isinstance(entry, dict):
            continue
        apps = entry.get("apps", {})
        path = entry.get("path")
        if not isinstance(apps, dict) or STEAM_APP_ID not in apps or not isinstance(path, str):
            continue
        game = Path(path) / "steamapps" / "common" / GAME_FOLDER
        if game.is_dir():
            found.append(game)
    return found


def find_default_tekken() -> Path | None:
    try:
        for candidate in default_library_vdfs():
            if _is_file(candidate):
                found = find_tekken_dirs(candidate)
                if found:
                    return found[0]
    except OSError:
        return None
    return None


def default_library_vdfs() -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".steam" / "steam" / "steamapps" / "libraryfolders.vdf",
        home / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf",
    ]
    if os.name == "nt":
        program_files = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")
        if program_files:
            candidates.append(Path(program_files) / "Steam" / "steamapps" / "libraryfolders.vdf")
    else:
        candidates.append(Path("/mnt/c/Program Files (x86)/Steam/steamapps/libraryfolders.vdf"))
    return candidates


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def parse_vdf(text: str) -> dict:
    tokens = _tokenize(text)
    position = 0

    def parse_value() -> object:
        nonlocal position
        token = tokens[position]
        position += 1
        if token != "{":
            return token
        mapping: dict[str, object] = {}
        while position < len(tokens) and tokens[position] != "}":
            key = tokens[position]
            position += 1
            mapping[key] = parse_value()
        position += 1
        return mapping

    if not tokens:
        return {}
    root_key = tokens[position]
    position += 1
    value = parse_value()
    return {root_key: value}


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in "{}":
            tokens.append(char)
            index += 1
            continue
        if char == '"':
            index += 1
            buffer: list[str] = []
            while index < length:
                if text[index] == "\\" and index + 1 < length:
                    buffer.append(text[index + 1])
                    index += 2
                    continue
                if text[index] == '"':
                    index += 1
                    break
                buffer.append(text[index])
                index += 1
            tokens.append("".join(buffer))
            continue
        raise ValueError(f"Unexpected character in Valve text at {index}")
    return tokens
