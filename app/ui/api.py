"""Python API behind the desktop window."""

from __future__ import annotations

import base64
from pathlib import Path

from app.audio.assign import SongInfo, fit_label
from app.audio.fit import prepare_audio
from app.audio.preview import play_preview, stop_playback
from app.audio.wavio import read_wav
from app.catalog import Catalog, CatalogError, load_catalog, slot_disabled
from app.library import Library
from app.mod.encode import find_wwise_console, find_wwise_project
from app.mod.install import find_default_tekken, uninstall_pak
from app.mod.pipeline import InstallError, build_and_install
from app.mod.setup import describe_setup


class JukeboxApi:
    def __init__(self, library: Library, catalog: Catalog, player=None, installer=None, stopper=None, catalog_path: Path | None = None):
        self.library = library
        self.catalog = catalog
        self.catalog_path = Path(catalog_path) if catalog_path else None
        self.player = player
        self.stopper = stopper
        self.installer = installer or build_and_install
        self.wwise_console: Path | None = None
        self.wwise_project: Path | None = None
        self.notice = ""

    def get_state(self) -> dict:
        console = self._console()
        project = self._project()
        game_dir = self._game_dir()
        setup = describe_setup(self.catalog, game_dir, wwise_console=console, project=project)
        tracks = []
        for track in self.library.tracks:
            slot = next((item for item in self.catalog.slots if item.id == track.slot_id), None)
            if slot is None:
                label = "unassigned"
                slot_name = ""
            else:
                label = fit_label(
                    SongInfo(track.id, track.sample_count, track.sample_rate),
                    slot,
                )
                slot_name = slot.name
            tracks.append(
                {
                    "id": track.id,
                    "name": track.name,
                    "slot_id": track.slot_id,
                    "slot_name": slot_name,
                    "label": label,
                    "duration": _clock(track.sample_count, track.sample_rate),
                }
            )
        return {
            "setup": setup,
            "tracks": tracks,
            "slots": [
                {
                    "id": slot.id,
                    "name": slot.name,
                    "duration": _clock(slot.intro_samples + slot.loop_samples, slot.sample_rate),
                    "disabled": slot_disabled(slot.name),
                }
                for slot in self.catalog.slots
            ],
            "notice": self.notice,
            "game_path": str(game_dir) if game_dir else "",
        }

    def add_paths(self, paths: list[str]) -> dict:
        added = 0
        skipped = 0
        errors: list[str] = []
        for path in paths:
            before = len(self.library.tracks)
            try:
                self.library.add_wav(Path(path))
            except (OSError, ValueError) as exc:
                errors.append(f"{Path(path).name}: {exc}")
                continue
            if len(self.library.tracks) == before:
                skipped += 1
            else:
                added += 1
        parts = []
        if added:
            parts.append(f"Added {added} song{'s' if added != 1 else ''}.")
        if skipped:
            names = ", ".join(track.name for track in self.library.tracks)
            parts.append(f"Skipped {skipped} already in the list: {names}.")
        if errors:
            parts.append(" ".join(errors))
        self.notice = " ".join(parts) if parts else "No wav files were added."
        return self.get_state()

    def add_wav_base64(self, name: str, payload: str) -> dict:
        try:
            self.library.add_bytes(name, base64.b64decode(payload))
        except (OSError, ValueError) as exc:
            self.notice = str(exc)
            return self.get_state()
        self.notice = f"Added {Path(name).stem}."
        return self.get_state()

    def preview(self, track_id: str) -> dict:
        try:
            track = next(item for item in self.library.tracks if item.id == track_id)
            if not track.slot_id:
                raise ValueError("Assign this song to a slot before previewing.")
            slot = self.catalog.slot_by_id(track.slot_id)
            audio, rate = read_wav(Path(track.path))
            fitted = prepare_audio(
                audio,
                rate,
                intro_samples=slot.intro_samples,
                loop_samples=slot.loop_samples,
                target_rate=slot.sample_rate,
                target_channels=slot.channels,
            )
            play_preview(build_preview_audio(fitted), fitted.sample_rate, self.player)
        except Exception as exc:
            self.notice = str(exc)
            return self.get_state()
        self.notice = "Playing the intro once, then the loop twice."
        return self.get_state()

    def stop_preview(self) -> dict:
        try:
            stop_playback(self.stopper)
        except Exception as exc:
            self.notice = str(exc)
            return self.get_state()
        self.notice = "Preview stopped."
        return self.get_state()

    def refresh(self) -> dict:
        if self.catalog_path and self.catalog_path.is_file():
            catalog = load_catalog(self.catalog_path)
            self.catalog = catalog
            loaded = Library.load(catalog, self.library.storage)
            self.library = loaded
        self.notice = "Refreshed."
        return self.get_state()

    def set_slot(self, track_id: str, slot_id: str) -> dict:
        try:
            slot = self.catalog.slot_by_id(slot_id)
        except CatalogError:
            self.notice = "That song or jukebox slot is not in the library."
            return self.get_state()
        if slot_disabled(slot.name):
            self.notice = "That jukebox song cannot be replaced."
            return self.get_state()
        try:
            self.library.set_slot(track_id, slot_id)
        except KeyError:
            self.notice = "That song or jukebox slot is not in the library."
            return self.get_state()
        self.notice = "Slot updated."
        return self.get_state()

    def remove_track(self, track_id: str) -> dict:
        self.library.remove(track_id)
        self.notice = "Song removed."
        return self.get_state()

    def set_game_dir(self, path: str) -> dict:
        self.library.set_game_dir(path or None)
        self.notice = "Game folder updated." if path else "Game folder cleared."
        return self.get_state()

    def install(self) -> dict:
        setup = self.get_state()["setup"]
        if not setup["install_allowed"]:
            self.notice = " ".join(setup["messages"])
            return self.get_state()
        game_dir = Path(setup["game_dir"])
        try:
            self.installer(
                self.library,
                self.catalog,
                game_dir,
                self.library.storage / "work",
                wwise_console=self._console(),
                project=self._project(),
            )
        except (InstallError, PermissionError) as exc:
            self.notice = str(exc)
            return self.get_state()
        names = []
        for track in self.library.tracks:
            if track.slot_id:
                names.append(self.catalog.slot_by_id(track.slot_id).name)
        listed = ", ".join(dict.fromkeys(names))
        self.notice = f"Installed. Close Tekken if it is open, then pick: {listed}."
        return self.get_state()

    def uninstall(self) -> dict:
        game_dir = self._game_dir()
        if game_dir is None or not Path(game_dir).is_dir():
            self.notice = "Tekken 8 folder was not found."
            return self.get_state()
        try:
            removed = uninstall_pak(Path(game_dir))
        except PermissionError as exc:
            self.notice = str(exc)
            return self.get_state()
        self.notice = "Removed the custom jukebox mod." if removed else "No custom jukebox mod was installed."
        return self.get_state()

    def choose_wavs(self) -> dict:
        window = _window()
        if window is None:
            self.notice = "The file picker opens from the desktop window."
            return self.get_state()
        import webview

        selected = window.create_file_dialog(
            _file_dialog(webview, "OPEN", "OPEN_DIALOG"),
            allow_multiple=True,
            file_types=("WAV files (*.wav)",),
        )
        if not selected:
            return self.get_state()
        return self.add_paths(list(selected))

    def choose_wav_folder(self) -> dict:
        window = _window()
        if window is None:
            self.notice = "The folder picker opens from the desktop window."
            return self.get_state()
        import webview

        selected = window.create_file_dialog(_file_dialog(webview, "FOLDER", "FOLDER_DIALOG"))
        if not selected:
            return self.get_state()
        try:
            paths = wavs_in_folder(Path(selected[0]))
        except (OSError, ValueError) as exc:
            self.notice = str(exc)
            return self.get_state()
        if not paths:
            self.notice = "That folder has no wav files."
            return self.get_state()
        return self.add_paths(paths)

    def choose_game_dir(self) -> dict:
        window = _window()
        if window is None:
            self.notice = "The folder picker opens from the desktop window."
            return self.get_state()
        import webview

        selected = window.create_file_dialog(_file_dialog(webview, "FOLDER", "FOLDER_DIALOG"))
        if not selected:
            return self.get_state()
        return self.set_game_dir(selected[0])

    def _game_dir(self) -> Path | None:
        if self.library.game_dir:
            return Path(self.library.game_dir)
        return find_default_tekken()

    def _console(self) -> Path | None:
        if self.wwise_console is not None:
            return self.wwise_console
        return find_wwise_console()

    def _project(self) -> Path | None:
        if self.wwise_project is not None:
            return self.wwise_project
        return find_wwise_project()


def build_preview_audio(fitted) -> object:
    from app.audio.preview import build_preview

    return build_preview(fitted.intro, fitted.loop)


def wavs_in_folder(folder: Path) -> list[str]:
    directory = Path(folder)
    if not directory.is_dir():
        raise ValueError(f"{directory} is not a folder")
    return sorted(
        str(path)
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".wav"
    )


def _file_dialog(webview, name: str, legacy: str):
    modern = getattr(webview, "FileDialog", None)
    if modern is not None and hasattr(modern, name):
        return getattr(modern, name)
    return getattr(webview, legacy)


def _window():
    try:
        import webview
    except ImportError:
        return None
    try:
        return webview.active_window()
    except Exception:
        return None


def _clock(samples: int, rate: int) -> str:
    if rate <= 0:
        return "0:00"
    seconds = int(round(samples / rate))
    return f"{seconds // 60}:{seconds % 60:02d}"
