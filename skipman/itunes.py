# Apple Music Desktop Integration
# Copies tracks to the "Automatically Add to Apple Music" folder.
# Auto-converts unsupported formats to MP3 via ffmpeg.
# Launches Apple Music if not running so the folder gets ingested.

import os
import shutil
import subprocess
from pathlib import Path

APPLE_MUSIC_PROCESS_NAMES = ("AppleMusic.exe", "Music.exe")

AUTO_ADD_FOLDER = (
    Path.home() / "Music" / "Apple Music" / "Media"
    / "Automatically Add to Apple Music"
)

NATIVE_FORMATS = {".mp3", ".m4a", ".aac", ".aiff", ".wav", ".alac"}
NEEDS_CONVERSION = {".opus", ".ogg", ".wma", ".flac", ".webm"}


def _is_apple_music_running():
    """Check whether Apple Music is currently running."""
    try:
        for proc_name in APPLE_MUSIC_PROCESS_NAMES:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {proc_name}", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if proc_name.lower() in result.stdout.lower():
                return True
    except Exception:
        pass
    return False


def ensure_apple_music_running():
    """Launch Apple Music if it isn't running. Returns status string."""
    if _is_apple_music_running():
        return "already_running"

    ps_cmd = (
        "$app = Get-StartApps | "
        "Where-Object { $_.Name -like 'Apple Music*' } | "
        "Select-Object -First 1; "
        "if ($app) { Start-Process -FilePath ('shell:AppsFolder\\' + $app.AppID) }"
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return "launched"
    except Exception:
        return "failed"


def _get_ffmpeg_path():
    """Find ffmpeg executable — check local ffmpeg/ dir first, then PATH."""
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_ffmpeg = os.path.join(app_dir, "ffmpeg", "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    return None


def _convert_to_mp3(input_path, output_path, ffmpeg_path="ffmpeg"):
    """Convert an audio file to 320kbps MP3 using ffmpeg."""
    cmd = [
        ffmpeg_path, "-y", "-i", input_path,
        "-codec:a", "libmp3lame", "-b:a", "320k",
        "-map_metadata", "0",
        output_path,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")[:500]
        raise RuntimeError("ffmpeg conversion failed:\n" + err)


def _format_success(basename, launch_state, converted):
    """Build the user-facing success message based on Apple Music's state."""
    if converted:
        prefix = '"' + basename + '" converted to MP3 and added to Apple Music.'
    else:
        prefix = '"' + basename + '" added to Apple Music.'

    if launch_state == "already_running":
        suffix = " Apple Music is running — it should pick it up momentarily."
    elif launch_state == "launched":
        suffix = " Launching Apple Music now to ingest it..."
    else:
        suffix = " (Open Apple Music to finish importing the file.)"
    return prefix + suffix


def add_to_itunes(file_path):
    """Add an audio file to Apple Music. Launches the app if not running."""
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not AUTO_ADD_FOLDER.exists():
        raise RuntimeError(
            "Apple Music auto-add folder not found.\n"
            "Make sure Apple Music is installed and has been opened at least once.\n"
            f"Expected: {AUTO_ADD_FOLDER}"
        )

    ext = os.path.splitext(file_path)[1].lower()
    basename = os.path.basename(file_path)

    if ext in NEEDS_CONVERSION:
        ffmpeg_path = _get_ffmpeg_path()
        if not ffmpeg_path:
            raise RuntimeError(
                '"' + basename + '" is ' + ext + ' format which Apple Music cannot import.\n'
                "FFmpeg is needed to convert it but was not found.\n"
                "Run SkipMan's download feature once to auto-install FFmpeg."
            )

        mp3_name = os.path.splitext(basename)[0] + ".mp3"
        dest = AUTO_ADD_FOLDER / mp3_name

        _convert_to_mp3(file_path, str(dest), ffmpeg_path)
        launch_state = ensure_apple_music_running()
        return True, _format_success(basename, launch_state, converted=True)

    # Native format — just copy
    dest = AUTO_ADD_FOLDER / basename
    shutil.copy2(file_path, dest)
    launch_state = ensure_apple_music_running()
    return True, _format_success(basename, launch_state, converted=False)
