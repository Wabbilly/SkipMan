#!/bin/bash
# Fetch static ffmpeg + ffprobe for the build machine into build/ffmpeg/.
# Usage: packaging/get_ffmpeg.sh mac-arm64 | mac-x64 | windows
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=build/ffmpeg
rm -rf "$DEST" && mkdir -p "$DEST"
TMP=$(mktemp -d)

fetch() {  # url out — retries because mirrors are occasionally flaky
  for i in 1 2 3 4 5; do
    if curl -fsSL --retry 3 -o "$2" "$1"; then return 0; fi
    sleep 5
  done
  return 1
}

case "$1" in
  mac-arm64|mac-x64)
    ARCH=arm64; [ "$1" = mac-x64 ] && ARCH=amd64
    for bin in ffmpeg ffprobe; do
      ok=""
      for chan in release snapshot; do
        if fetch "https://ffmpeg.martin-riedl.de/redirect/latest/macos/$ARCH/$chan/$bin.zip" "$TMP/$bin.zip"; then
          unzip -o -q "$TMP/$bin.zip" -d "$TMP/$bin" && ok=1 && break
        fi
      done
      [ -n "$ok" ] || { echo "could not download $bin"; exit 1; }
      cp "$TMP/$bin/$bin" "$DEST/$bin"
      chmod +x "$DEST/$bin"
    done
    file "$DEST"/*
    ;;
  windows)
    fetch "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" "$TMP/ff.zip"
    unzip -q "$TMP/ff.zip" -d "$TMP/ff"
    cp "$TMP"/ff/*/bin/ffmpeg.exe "$TMP"/ff/*/bin/ffprobe.exe "$DEST/"
    ;;
  *) echo "unknown target $1"; exit 1 ;;
esac
"$DEST"/ffmpeg* -hide_banner -version | head -1
rm -rf "$TMP"
