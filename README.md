# Tekken 8 Custom Jukebox

Drop `.wav` files into a desktop window. Each file is fitted to an existing jukebox song (a fixed intro plus a fixed loop), previewed in the app, and packed into one mod. In Tekken you still pick the original song name. The menu does not gain new entries.

The mod only changes music files on your PC. Your opponent does not hear it. Tekken 8’s own soundtrack slots do not stick with this pak, so that section is hidden. Slots from Tekken 1 through 7 can be replaced.

## If you downloaded the .exe

You do not install Python, and you do not set up a virtual environment. Double-click `Tekken8CustomJukebox.exe`. The song list is already inside it.

You still need:

- Tekken 8 on Steam. In the app, choose the folder that ends in `steamapps\common\TEKKEN 8`.
- [Wwise 2023.1](https://www.audiokinetic.com/download) with Windows Authoring. That is what turns each wav into the files Tekken plays. It is not inside the exe.

Install Wwise in the normal Audiokinetic folder and the app finds `WwiseConsole.exe` on its own. In that Wwise project, create conversion settings named exactly `Vorbis Quality High`, `PCM`, `ADPCM`, and `Opus Quality High`, then point the app at the project once:

```bat
setx WWISE_PROJECT "C:\path\to\your\project.wproj"
```

Open a new terminal after `setx`, then start the exe again. Set `WWISE_CONSOLE` only if Wwise is not in `C:\Program Files (x86)\Audiokinetic`.

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
2. Install Wwise 2023.1 if **Wwise** is not ready. In that Wwise project, create conversion settings with these exact names: `Vorbis Quality High`, `PCM`, `ADPCM`, `Opus Quality High`. Point the app at that project:

```bat
set WWISE_CONSOLE=C:\Program Files (x86)\Audiokinetic\Wwise 2023.1.19.8808\Authoring\x64\Release\bin\WwiseConsole.exe
set WWISE_PROJECT=C:\path\to\your\project.wproj
```

Use your real Wwise version folder and project path. You can also replace `wwise\CustomJukebox.wproj` with that project. The file in this repo is only a placeholder.

3. Add wav files, or a folder of them. Duplicates are skipped.
4. For each file, open the song list and pick the jukebox slot it should replace. **Duration** sorts shortest or longest. A slot another file already uses is marked **Used by**. Tekken 8 songs are not in the list.
5. **Preview** plays the intro once, then the loop twice.
6. Close Tekken, then click **Install mod**. The app writes only this file:

`TEKKEN 8\Polaris\Content\Paks\Mods\z_tekken8_custom_jukebox_P.pak`

7. Launch Tekken and, in the jukebox, pick the original names shown in the app.

**Remove mod** deletes that pak and nothing else. Close Tekken first, or Windows will say the file is in use.

The program is `dist\Tekken8CustomJukebox.exe`. It still needs WebView2, a Tekken 8 install, and Wwise 2023.1 on that PC. People who only download the exe cannot install a mod until Wwise is set up the same way as above.
