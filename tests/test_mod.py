"""WwiseConsole encoding and pak install."""

import json
import subprocess
import wave
from pathlib import Path

import pytest

from app.catalog import Catalog, Slot, save_catalog
from app.library import Library
from app.mod.encode import EncodeError, encode_wav
from app.mod.install import PAK_NAME, find_default_tekken, find_tekken_dirs, install_pak, read_game_version, uninstall_pak
from app.mod.pack import pack_files
from app.mod.pipeline import InstallError, build_and_install
from app.mod.setup import describe_setup


def _wav(path: Path, frames: int = 16) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x01\x00" * frames)


def _catalog(root: Path) -> Catalog:
    catalog = Catalog(
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
                "Polaris/Content/WwiseAudio/brief-intro.wem",
                "Polaris/Content/WwiseAudio/brief-loop.wem",
            ),
        ),
    )
    save_catalog(catalog, root / "slots.json")
    return catalog


def test_encode_wav_asks_wwise_for_one_wem_and_renames_it(tmp_path: Path):
    wav = tmp_path / "intro.wav"
    _wav(wav)
    project = tmp_path / "CustomJukebox.wproj"
    project.write_text("<Project/>", encoding="utf-8")
    console = tmp_path / "WwiseConsole.exe"
    console.write_text("", encoding="utf-8")
    seen: dict[str, list[str]] = {}

    def runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        seen["cmd"] = cmd
        output = Path(cmd[cmd.index("--output") + 1])
        output.mkdir(parents=True, exist_ok=True)
        (output / "generated.wem").write_bytes(b"WEMDATA")
        source = Path(cmd[cmd.index("--source-file") + 1])
        listing = source.read_text(encoding="utf-8")
        assert "PCM" in listing
        assert wav.name in listing
        return subprocess.CompletedProcess(cmd, 0, "", "")

    staged = encode_wav(
        wav=wav,
        asset_path="Polaris/Content/WwiseAudio/brief-intro.wem",
        codec="pcm",
        work_dir=tmp_path / "work",
        wwise_console=console,
        project=project,
        runner=runner,
    )

    assert seen["cmd"][1] == "convert-external-source"
    assert staged.read_bytes() == b"WEMDATA"
    assert staged.name == "brief-intro.wem"


def test_encode_wav_refuses_a_missing_converter(tmp_path: Path):
    wav = tmp_path / "intro.wav"
    _wav(wav)
    with pytest.raises(EncodeError, match="Wwise"):
        encode_wav(
            wav=wav,
            asset_path="Polaris/Content/a.wem",
            codec="pcm",
            work_dir=tmp_path / "work",
            wwise_console=tmp_path / "missing.exe",
            project=tmp_path / "missing.wproj",
            runner=lambda cmd: subprocess.CompletedProcess(cmd, 0),
        )


def test_denied_steam_path_does_not_raise(monkeypatch):
    def denied(self):
        raise PermissionError("Access is denied")

    monkeypatch.setattr(Path, "is_file", denied)
    assert find_default_tekken() is None


def test_finds_tekken_and_reads_the_steam_build_id(tmp_path: Path):
    steam = tmp_path / "Steam"
    game = steam / "steamapps" / "common" / "TEKKEN 8"
    (game / "Polaris").mkdir(parents=True)
    (steam / "steamapps" / "appmanifest_1778820.acf").write_text(
        '"AppState"\n{\n\t"buildid"\t\t"555"\n}\n',
        encoding="utf-8",
    )
    vdf = tmp_path / "libraryfolders.vdf"
    vdf.write_text(
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"'
        + str(steam)
        + '"\n\t\t"apps"\n\t\t{\n\t\t\t"1778820"\t\t"1"\n\t\t}\n\t}\n}\n',
        encoding="utf-8",
    )

    found = find_tekken_dirs(vdf)
    assert found == [game]
    assert read_game_version(game) == "555"


def test_pack_files_roundtrip_on_a_dummy_tree(tmp_path: Path):
    import repak

    dest = tmp_path / "z_tekken8_custom_jukebox_P.pak"
    pack_files(
        [
            ("Polaris/Content/WwiseAudio/brief-intro.wem", b"intro"),
            ("Polaris/Content/WwiseAudio/brief-loop.wem", b"loop"),
        ],
        dest,
    )

    with repak.PakBuilder().reader(str(dest)) as pak:
        assert pak.mount_point.startswith("../../../")
        names = set(pak.entries())
        assert "Polaris/Content/WwiseAudio/brief-intro.wem" in names
        assert pak.get("Polaris/Content/WwiseAudio/brief-loop.wem") == b"loop"


def test_install_replaces_only_our_pak(tmp_path: Path):
    game = tmp_path / "TEKKEN 8"
    mods = game / "Polaris" / "Content" / "Paks" / "Mods"
    mods.mkdir(parents=True)
    other = mods / "someone_else_P.pak"
    other.write_bytes(b"keep")
    pak = tmp_path / PAK_NAME
    pak.write_bytes(b"first")

    installed = install_pak(pak, game)
    pak.write_bytes(b"second")
    install_pak(pak, game)

    assert installed.read_bytes() == b"second"
    assert other.read_bytes() == b"keep"
    assert uninstall_pak(game) is True
    assert not installed.exists()
    assert other.exists()
    assert uninstall_pak(game) is False


def test_uninstall_says_to_close_tekken_when_the_pak_is_open(tmp_path: Path, monkeypatch):
    game = tmp_path / "TEKKEN 8"
    mods = game / "Polaris" / "Content" / "Paks" / "Mods"
    mods.mkdir(parents=True)
    (mods / PAK_NAME).write_bytes(b"locked")

    def locked(self):
        raise PermissionError(32, "in use", str(self))

    monkeypatch.setattr(Path, "unlink", locked)

    with pytest.raises(PermissionError, match="Close Tekken"):
        uninstall_pak(game)


def test_unpinned_catalog_uses_the_installed_build_id(tmp_path: Path):
    catalog = Catalog(None, _catalog(tmp_path).slots)
    game = tmp_path / "TEKKEN 8"
    (game / "Polaris").mkdir(parents=True)
    (game / "game_version.txt").write_text("555\n", encoding="utf-8")
    console = tmp_path / "WwiseConsole.exe"
    project = tmp_path / "CustomJukebox.wproj"
    console.write_text("", encoding="utf-8")
    project.write_text("<Project/>", encoding="utf-8")

    status = describe_setup(catalog, game, wwise_console=console, project=project)

    assert status["game_version"] == "555"
    assert status["version_matches"] is True
    assert status["install_allowed"] is True


def test_build_and_install_refuses_a_different_game_version(tmp_path: Path):
    catalog = _catalog(tmp_path)
    library = Library(catalog, tmp_path / "lib")
    _wav(tmp_path / "song.wav", 16)
    library.add_wav(tmp_path / "song.wav")
    game = tmp_path / "TEKKEN 8"
    (game / "Polaris").mkdir(parents=True)
    (game / "game_version.txt").write_text("build-999\n", encoding="utf-8")
    status = describe_setup(
        catalog,
        game,
        wwise_console=tmp_path / "WwiseConsole.exe",
        project=tmp_path / "CustomJukebox.wproj",
    )
    (tmp_path / "WwiseConsole.exe").write_text("", encoding="utf-8")
    (tmp_path / "CustomJukebox.wproj").write_text("<Project/>", encoding="utf-8")
    status = describe_setup(
        catalog,
        game,
        wwise_console=tmp_path / "WwiseConsole.exe",
        project=tmp_path / "CustomJukebox.wproj",
    )

    assert status["install_allowed"] is False
    assert any("version" in message.lower() for message in status["messages"])
    with pytest.raises(InstallError, match="version"):
        build_and_install(
            library,
            catalog,
            game,
            tmp_path / "work",
            wwise_console=tmp_path / "WwiseConsole.exe",
            project=tmp_path / "CustomJukebox.wproj",
            runner=lambda cmd: subprocess.CompletedProcess(cmd, 0),
        )


def test_placeholder_wwise_project_is_not_ready(tmp_path: Path):
    catalog = _catalog(tmp_path)
    game = tmp_path / "TEKKEN 8"
    (game / "Polaris").mkdir(parents=True)
    (game / "game_version.txt").write_text("build-100\n", encoding="utf-8")
    console = tmp_path / "WwiseConsole.exe"
    project = tmp_path / "CustomJukebox.wproj"
    console.write_text("", encoding="utf-8")
    project.write_text("<!-- JUKEBOX_PLACEHOLDER -->\n", encoding="utf-8")

    status = describe_setup(catalog, game, wwise_console=console, project=project)

    assert status["project_found"] is False
    assert status["install_allowed"] is False
    assert any("empty template" in message for message in status["messages"])


def test_build_and_install_packs_fitted_songs(tmp_path: Path):
    import repak

    catalog = _catalog(tmp_path)
    library = Library(catalog, tmp_path / "lib")
    _wav(tmp_path / "song.wav", 16)
    library.add_wav(tmp_path / "song.wav")
    game = tmp_path / "TEKKEN 8"
    (game / "Polaris").mkdir(parents=True)
    (game / "game_version.txt").write_text("build-100\n", encoding="utf-8")
    console = tmp_path / "WwiseConsole.exe"
    project = tmp_path / "CustomJukebox.wproj"
    console.write_text("", encoding="utf-8")
    project.write_text("<Project/>", encoding="utf-8")

    def runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        output = Path(cmd[cmd.index("--output") + 1])
        output.mkdir(parents=True, exist_ok=True)
        (output / "one.wem").write_bytes(b"W" + Path(cmd[cmd.index("--source-file") + 1]).stem.encode())
        return subprocess.CompletedProcess(cmd, 0, "", "")

    installed = build_and_install(
        library,
        catalog,
        game,
        tmp_path / "work",
        wwise_console=console,
        project=project,
        runner=runner,
    )

    assert installed.name == PAK_NAME
    assert installed.parent == game / "Polaris" / "Content" / "Paks" / "Mods"
    with repak.PakBuilder().reader(str(installed)) as pak:
        assert pak.get("Polaris/Content/WwiseAudio/brief-intro.wem")
        assert pak.get("Polaris/Content/WwiseAudio/brief-loop.wem")
    saved = json.loads((tmp_path / "lib" / "library.json").read_text(encoding="utf-8"))
    assert saved["tracks"][0]["slot_id"] == "brief"
