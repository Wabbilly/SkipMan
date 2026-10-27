#!/bin/bash
# Fetch static ffmpeg + ffprobe for the build machine into build/ffmpeg/.
# Usage: packaging/get_ffmpeg.sh mac-arm64 | mac-x64 | windows
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=build/ffmpeg
rm -rf "$DEST" && mkdir -p "$DEST"
TMP=$(mktemp -d)

fetch() {  # url out — retries because mirrors are occasionally flaky
  for i in 1 2 3; do
    if curl -fsSL --retry 3 -o "$2" "$1"; then return 0; fi
    sleep 5
  done
  return 1
}

case "$1" in
  mac-arm64|mac-x64)
    ARCH=arm64; [ "$1" = mac-x64 ] && ARCH=amd64
    # Source 1: martin-riedl.de static builds
    for bin in ffmpeg ffprobe; do
      for chan in release snapshot; do
        if fetch "https://ffmpeg.martin-riedl.de/redirect/latest/macos/$ARCH/$chan/$bin.zip" "$TMP/$bin.zip"; then
          unzip -o -q "$TMP/$bin.zip" -d "$TMP/$bin" && cp "$TMP/$bin/$bin" "$DEST/$bin" && break
        fi
      done
    done
    # Source 2 (backup, hosted on GitHub): static-ffmpeg's builds
    if [ ! -f "$DEST/ffmpeg" ] || [ ! -f "$DEST/ffprobe" ]; then
      echo "martin-riedl unavailable; using GitHub-hosted backup"
      ZIP=darwin_arm64; [ "$ARCH" = amd64 ] && ZIP=darwin
      fetch "https://github.com/zackees/ffmpeg_bins/raw/main/v8.0/$ZIP.zip" "$TMP/bk.zip"
      unzip -o -q "$TMP/bk.zip" -d "$TMP/bk"
      for bin in ffmpeg ffprobe; do
        cp "$(find "$TMP/bk" -type f -name "$bin" | head -1)" "$DEST/$bin"
      done
    fi
    chmod +x "$DEST"/*
    file "$DEST"/*
    ;;
  windows)
    # LGPL shared build: ffmpeg + ffprobe share one set of DLLs (much smaller)
    fetch "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-lgpl-shared.zip" "$TMP/ff.zip"
    unzip -q "$TMP/ff.zip" -d "$TMP/ff"
    cp "$TMP"/ff/*/bin/ffmpeg.exe "$TMP"/ff/*/bin/ffprobe.exe "$TMP"/ff/*/bin/*.dll "$DEST/"
    "$DEST/ffmpeg.exe" -hide_banner -encoders 2>/dev/null | grep -q libmp3lame || { echo "no mp3 encoder"; exit 1; }
    ;;
  *) echo "unknown target $1"; exit 1 ;;
esac
"$DEST"/ffmpeg* -hide_banner -version | head -1
rm -rf "$TMP"
