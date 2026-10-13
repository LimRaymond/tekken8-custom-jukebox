"""Convert fitted wavs to wem files with WwiseConsole."""

from __future__ import annotations

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

CONVERSION_BY_CODEC = {
    "vorbis": "Vorbis Quality High",
    "pcm": "PCM",
    "adpcm": "ADPCM",
    "opus": "Opus Quality High",
}

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


class EncodeError(Exception):
    """Wwise could not convert a fitted wav."""


def find_wwise_console() -> Path | None:
    env = os.environ.get("WWISE_CONSOLE")
    if env and Path(env).is_file():
        return Path(env)
    root = os.environ.get("WWISEROOT")
    if root:
        candidate = Path(root) / "Authoring" / "x64" / "Release" / "bin" / "WwiseConsole.exe"
        if candidate.is_file():
            return candidate
    patterns = [
        "C:/Program Files (x86)/Audiokinetic/Wwise*/Authoring/x64/Release/bin/WwiseConsole.exe",
        "/mnt/c/Program Files (x86)/Audiokinetic/Wwise*/Authoring/x64/Release/bin/WwiseConsole.exe",
    ]
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(Path(part) for part in _glob(pattern))
    return Path(matches[-1]) if matches else None


def find_wwise_project() -> Path | None:
    env = os.environ.get("WWISE_PROJECT")
    if env and Path(env).is_file():
        return Path(env)
    candidate = Path(__file__).resolve().parents[2] / "wwise" / "CustomJukebox.wproj"
    return candidate if candidate.is_file() else None


def encode_wav(
    *,
    wav: Path,
    asset_path: str,
    codec: str,
    work_dir: Path,
    wwise_console: Path,
    project: Path,
    runner: Runner | None = None,
) -> Path:
    if not Path(wwise_console).is_file() or not Path(project).is_file():
        raise EncodeError(
            "WwiseConsole or the Wwise project was not found. Install Wwise 2023.1 and set WWISE_CONSOLE."
        )
    try:
        conversion = CONVERSION_BY_CODEC[codec]
    except KeyError as exc:
        raise EncodeError(f"No Wwise conversion is configured for {codec}") from exc
    job = Path(work_dir) / Path(asset_path).stem
    if job.exists():
        shutil.rmtree(job)
    output = job / "out"
    output.mkdir(parents=True)
    source_file = job / "list.wsources"
    _write_wsources(source_file, wav, conversion)
    command = [
        str(wwise_console),
        "convert-external-source",
        str(project),
        "--source-file",
        str(source_file),
        "--output",
        str(output),
    ]
    completed = (runner or _run)(command)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "WwiseConsole failed").strip()
        raise EncodeError(detail)
    produced = list(output.rglob("*.wem"))
    if len(produced) != 1:
        raise EncodeError(f"Wwise produced {len(produced)} wem files for {wav.name}")
    staged = job / Path(asset_path).name
    staged.write_bytes(produced[0].read_bytes())
    return staged


def _write_wsources(path: Path, wav: Path, conversion: str) -> None:
    root = ET.Element("ExternalSourcesList", {"SchemaVersion": "1", "Root": str(wav.parent)})
    ET.SubElement(root, "Source", {"Path": wav.name, "Conversion": conversion})
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _glob(pattern: str) -> list[str]:
    import glob

    return glob.glob(pattern)
