"""Pack replacement wems into one Tekken 8 mod pak."""

from __future__ import annotations

from pathlib import Path

import repak

MOUNT_POINT = "../../../"
PAK_VERSION = repak.Version.V11


def pack_files(files: list[tuple[str, bytes]], dest: Path) -> None:
    destination = Path(dest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    builder = repak.PakBuilder()
    with builder.writer(str(destination), version=PAK_VERSION, mount_point=MOUNT_POINT) as pak:
        for path, data in files:
            pak.write_file(path.replace("\\", "/"), data, compress=False)
