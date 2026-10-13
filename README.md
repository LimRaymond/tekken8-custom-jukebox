# Tekken 8 Custom Jukebox

Drop `.wav` files into a desktop window. Each file is fitted to an existing jukebox song (a fixed intro plus a fixed loop), previewed in the app, and packed into one mod. In Tekken you still pick the original song name. The menu does not gain new entries.

The mod only changes music files on your PC. Your opponent does not hear it. Tekken 8’s own soundtrack slots do not stick with this pak, so that section is hidden. Slots from Tekken 1 through 7 can be replaced.

## If you downloaded the .exe

You do not install Python, and you do not set up a virtual environment. Double-click `Tekken8CustomJukebox.exe`. The song list is already inside it.

You still need:

- Tekken 8 on Steam. In the app, choose the folder that ends in `steamapps\common\TEKKEN 8`.
- [Wwise 2023.1](https://www.audiokinetic.com/download) with Windows Authoring. That is what turns each wav into the files Tekken plays. It is not inside the exe.

In that Wwise project, create conversion settings named exactly `Vorbis Quality High`, `PCM`, `ADPCM`, and `Opus Quality High`.

The Wwise Launcher usually installs the tools under `C:\Audiokinetic\Wwise_<version>\`, not under `Program Files`. The app does not look there by itself. Point it at `WwiseConsole.exe` and at the `.wproj` file inside the project folder (the file is not the folder next to it):

```bat
setx WWISE_CONSOLE "C:\Audiokinetic\Wwise_2023.1.19.8928\Authoring\x64\Release\bin\WwiseConsole.exe"
setx WWISE_PROJECT "C:\Users\You\Documents\WwiseProjects\CustomJukebox\CustomJukebox.wproj"
```

Use your real version folder and Windows user name. Close the `.exe` completely and open it again. **Refresh** does not see a `setx` you ran while the app was open.

Then follow **Use the app** from step 3.

## Run from source

Open the project folder in a Windows terminal. Keep the virtual environment on `C:`, not on a `\\wsl$\` path.

```bat
py -3.12 -m venv %USERPROFILE%\tekken8-jukebox-venv
%USERPROFILE%\tekken8-jukebox-venv\Scripts\python -m pip install -e .
%USERPROFILE%\tekken8-jukebox-venv\Scripts\python -m app
```

Your song list is saved under `%USERPROFILE%\.local\share\tekken8-custom-jukebox`.

## Use the app

1. Set the Tekken 8 folder. The usual Steam path ends in `steamapps\common\TEKKEN 8`. The status cards should show the game folder, the song catalog, and **Converter ready**.
2. If **Wwise** is not ready, set `WWISE_CONSOLE` and `WWISE_PROJECT` the same way as in **If you downloaded the .exe**, then start the app again from that terminal. `set` only lasts in the window where you typed it. The `wwise\CustomJukebox.wproj` file in this repo is a placeholder and does not count.

3. Add wav files, or a folder of them. Duplicates are skipped.
4. For each file, open the song list and pick the jukebox slot it should replace. **Duration** sorts shortest or longest. A slot another file already uses is marked **Used by**. Tekken 8 songs are not in the list.
5. **Preview** plays the intro once, then the loop twice.
6. Close Tekken, then click **Install mod**. The app writes only this file:

`TEKKEN 8\Polaris\Content\Paks\Mods\z_tekken8_custom_jukebox_P.pak`

7. Launch Tekken and, in the jukebox, pick the original names shown in the app.

**Remove mod** deletes that pak and nothing else. Close Tekken first, or Windows will say the file is in use.

## Build the .exe

From the project folder, with the virtual environment above:

```bat
%USERPROFILE%\tekken8-jukebox-venv\Scripts\python -m pip install pyinstaller
%USERPROFILE%\tekken8-jukebox-venv\Scripts\python -m PyInstaller --noconfirm --windowed --onefile --name Tekken8CustomJukebox --add-data "data;data" --add-data "app\ui\index.html;ui" --collect-all webview --collect-all repak app\main.py
```

Upload `dist\Tekken8CustomJukebox.exe` alone. People who download it still need Tekken 8 and Wwise, as in **If you downloaded the .exe**. WebView2 is already on Windows 11.
