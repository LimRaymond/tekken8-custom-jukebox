"""Fit assigned songs, encode them, pack one mod, and install it."""

from __future__ import annotations

from pathlib import Path

from app.audio.fit import prepare_audio
from app.audio.wavio import read_wav, write_wav
from app.catalog import Catalog
from app.library import Library
from app.mod.encode import Runner, encode_wav
from app.mod.install import install_pak
from app.mod.pack import pack_files
from app.mod.setup import describe_setup

PAK_FILENAME = "z_tekken8_custom_jukebox_P.pak"


class InstallError(Exception):
    """The mod could not be installed."""


def build_and_install(
    library: Library,
    catalog: Catalog,
    game_dir: Path,
    work_dir: Path,
    *,
    wwise_console: Path,
    project: Path,
    runner: Runner | None = None,
) -> Path:
    status = describe_setup(catalog, game_dir, wwise_console=wwise_console, project=project)
    if not status["install_allowed"]:
        raise InstallError(" ".join(status["messages"]))
    assigned = [track for track in library.tracks if track.slot_id]
    if not assigned:
        raise InstallError("No songs are assigned to a jukebox slot.")
    files: list[tuple[str, bytes]] = []
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    for track in assigned:
        slot = catalog.slot_by_id(track.slot_id or "")
        audio, rate = read_wav(Path(track.path))
        fitted = prepare_audio(
            audio,
            rate,
            intro_samples=slot.intro_samples,
            loop_samples=slot.loop_samples,
            target_rate=slot.sample_rate,
            target_channels=slot.channels,
        )
        if fitted.intro.shape[0] != slot.intro_samples or fitted.loop.shape[0] != slot.loop_samples:
            raise InstallError(f"{track.name} did not fit {slot.name}")
        if fitted.intro.shape[1] != slot.channels or fitted.loop.shape[1] != slot.channels:
            raise InstallError(f"{track.name} did not fit {slot.name}")
        if fitted.intro.shape[0] > 0:
            intro_wav = work / f"{track.id}-intro.wav"
            write_wav(intro_wav, fitted.intro, fitted.sample_rate)
            intro_wem = encode_wav(
                wav=intro_wav,
                asset_path=slot.intro_asset,
                codec=slot.codec,
                work_dir=work / track.id,
                wwise_console=wwise_console,
                project=project,
                runner=runner,
            )
            files.append((slot.intro_asset, intro_wem.read_bytes()))
        loop_wav = work / f"{track.id}-loop.wav"
        write_wav(loop_wav, fitted.loop, fitted.sample_rate)
        loop_wem = encode_wav(
            wav=loop_wav,
            asset_path=slot.loop_asset,
            codec=slot.codec,
            work_dir=work / f"{track.id}-loop",
            wwise_console=wwise_console,
            project=project,
            runner=runner,
        )
        files.append((slot.loop_asset, loop_wem.read_bytes()))
    pak_path = work / PAK_FILENAME
    pack_files(files, pak_path)
    return install_pak(pak_path, game_dir)
