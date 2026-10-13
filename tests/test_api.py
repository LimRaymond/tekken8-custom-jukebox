"""Desktop window API: drop songs, preview, swap slots, install."""

import base64
import wave
from pathlib import Path

from app.catalog import Catalog, Slot
from app.library import Library
from app.ui.api import JukeboxApi


def _catalog() -> Catalog:
    return Catalog(
        "build-100",
        (
            Slot(
                "brief",
                "Brief Theme",
                8000,
                1,
                "pcm",
                8,
                8,
                "Polaris/Content/brief-intro.wem",
                "Polaris/Content/brief-loop.wem",
            ),
            Slot(
                "anthem",
                "Anthem",
                8000,
                1,
                "pcm",
                8,
                24,
                "Polaris/Content/anthem-intro.wem",
                "Polaris/Content/anthem-loop.wem",
            ),
        ),
    )


def _wav(path: Path, frames: int) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x10" * frames)


def test_drop_previews_intro_plus_two_loops_and_swaps_slots(tmp_path: Path):
    library = Library(_catalog(), tmp_path / "lib")
    played: list[tuple[int, int]] = []
    api = JukeboxApi(
        library,
        library.catalog,
        player=lambda audio, rate: played.append((audio.shape[0], rate)),
    )
    short = tmp_path / "short.wav"
    long = tmp_path / "long.wav"
    _wav(short, 16)
    _wav(long, 32)

    state = api.add_paths([str(long), str(short)])
    by_name = {track["name"]: track for track in state["tracks"]}
    assert by_name["long"]["slot_name"] == "Anthem"
    assert by_name["long"]["label"] == "fits"
    assert by_name["short"]["slot_name"] == "Brief Theme"
    assert {slot["id"]: slot["duration"] for slot in state["slots"]} == {
        "brief": "0:00",
        "anthem": "0:00",
    }

    api.preview(by_name["short"]["id"])
    assert played == [(24, 8000)]

    state = api.set_slot(by_name["short"]["id"], "anthem")
    swapped = {track["name"]: track["slot_id"] for track in state["tracks"]}
    assert swapped == {"short": "anthem", "long": "brief"}


def test_dropped_file_bytes_join_the_library(tmp_path: Path):
    library = Library(_catalog(), tmp_path / "lib")
    api = JukeboxApi(library, library.catalog, player=lambda audio, rate: None)
    wav = tmp_path / "dropped.wav"
    _wav(wav, 16)

    state = api.add_wav_base64("dropped.wav", base64.b64encode(wav.read_bytes()).decode("ascii"))

    assert [track["name"] for track in state["tracks"]] == ["dropped"]
    assert state["tracks"][0]["slot_id"] == "brief"


def test_install_stays_blocked_until_the_game_catalog_and_wwise_line_up(tmp_path: Path):
    library = Library(_catalog(), tmp_path / "lib")
    calls: list[Path] = []

    def installer(library, catalog, game_dir, work_dir, *, wwise_console, project, runner=None):
        del library, catalog, work_dir, wwise_console, project, runner
        calls.append(game_dir)
        return game_dir / "Polaris" / "Content" / "Paks" / "Mods" / "z_tekken8_custom_jukebox_P.pak"

    api = JukeboxApi(library, library.catalog, player=lambda audio, rate: None, installer=installer)

    blocked = api.install()
    assert calls == []
    assert blocked["setup"]["install_allowed"] is False
    assert blocked["notice"]

    game = tmp_path / "TEKKEN 8"
    (game / "Polaris").mkdir(parents=True)
    (game / "game_version.txt").write_text("build-100\n", encoding="utf-8")
    console = tmp_path / "WwiseConsole.exe"
    project = tmp_path / "CustomJukebox.wproj"
    console.write_text("", encoding="utf-8")
    project.write_text("<Project/>", encoding="utf-8")
    library.set_game_dir(str(game))
    _wav(tmp_path / "song.wav", 16)
    api.add_paths([str(tmp_path / "song.wav")])
    api.wwise_console = console
    api.wwise_project = project

    installed = api.install()

    assert calls == [game]
    assert "Brief Theme" in installed["notice"]
    assert installed["setup"]["install_allowed"] is True
    assert installed["game_path"] == str(game)


def test_wavs_in_folder_returns_only_wav_files(tmp_path: Path):
    from app.ui.api import wavs_in_folder

    _wav(tmp_path / "one.wav", 16)
    _wav(tmp_path / "two.WAV", 16)
    (tmp_path / "notes.txt").write_text("skip", encoding="utf-8")

    found = wavs_in_folder(tmp_path)

    assert [Path(path).name for path in found] == ["one.wav", "two.WAV"]


def test_window_markup_has_a_drop_zone_preview_and_install():
    page = Path("app/ui/index.html").read_text(encoding="utf-8")
    assert 'id="drop"' in page
    assert 'id="game-path"' in page
    assert "preview" in page
    assert "install" in page
