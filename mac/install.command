#!/bin/bash
# ── SkipMan Mac installer ── double-click me (one time only) ───────────────
# Sets up SkipMan's own Python + packages, FFmpeg, builds SkipMan.app,
# puts it in Applications and the Dock, then opens it. After this, SkipMan
# updates itself from GitHub every time it starts.

set -e
cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"
echo ""
echo "// SKIPMAN INSTALL"
echo "   folder: $APP_DIR"
echo ""

# 1) Python (via uv — no Xcode or Homebrew needed)
UV="$(command -v uv || true)"
if [ -z "$UV" ]; then UV="$HOME/.local/bin/uv"; fi
if [ ! -x "$UV" ]; then
  echo "-> Getting uv (Python manager)…"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null
  UV="$HOME/.local/bin/uv"
fi
if [ ! -x .venv/bin/python ]; then
  echo "-> Creating SkipMan's Python…"
  "$UV" venv --python 3.12 .venv >/dev/null
fi
echo "-> Installing packages…"
"$UV" pip install -q --python .venv/bin/python -r requirements.txt

# 2) FFmpeg (one-time download unless you already have it)
echo "-> Checking FFmpeg…"
.venv/bin/python -c "from skipman.ffmpeg import ensure_ffmpeg; ensure_ffmpeg(print)"

# 3) Build SkipMan.app
echo "-> Building SkipMan.app…"
chmod +x mac/run.sh
TMP_SCRIPT="$(mktemp -t skipman).applescript"
sed "s#__APP_DIR__#${APP_DIR//#/\\#}#" mac/launcher.applescript > "$TMP_SCRIPT"
rm -rf SkipMan.app
osacompile -o SkipMan.app "$TMP_SCRIPT"
rm -f "$TMP_SCRIPT"

# Icon
ICONSET="$(mktemp -d)/SkipMan.iconset"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s skipman/ui/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s*2)); [ $d -le 1024 ] && sips -z $d $d skipman/ui/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o SkipMan.app/Contents/Resources/applet.icns
rm -f SkipMan.app/Contents/Resources/Assets.car

# Identity, skipman:// links, and accepting dropped links/files
PL=SkipMan.app/Contents/Info.plist
PB=/usr/libexec/PlistBuddy
$PB -c "Set :CFBundleIdentifier com.wabbilly.skipman" "$PL" 2>/dev/null || $PB -c "Add :CFBundleIdentifier string com.wabbilly.skipman" "$PL"
$PB -c "Delete :CFBundleURLTypes" "$PL" 2>/dev/null || true
$PB -c "Add :CFBundleURLTypes array" "$PL"
$PB -c "Add :CFBundleURLTypes:0 dict" "$PL"
$PB -c "Add :CFBundleURLTypes:0:CFBundleURLName string SkipMan link" "$PL"
$PB -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes array" "$PL"
$PB -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string skipman" "$PL"
$PB -c "Delete :CFBundleDocumentTypes" "$PL" 2>/dev/null || true
$PB -c "Add :CFBundleDocumentTypes array" "$PL"
$PB -c "Add :CFBundleDocumentTypes:0 dict" "$PL"
$PB -c "Add :CFBundleDocumentTypes:0:CFBundleTypeRole string Viewer" "$PL"
$PB -c "Add :CFBundleDocumentTypes:0:LSHandlerRank string Alternate" "$PL"
$PB -c "Add :CFBundleDocumentTypes:0:LSItemContentTypes array" "$PL"
i=0
for t in public.url com.apple.web-internet-location public.plain-text public.text; do
  $PB -c "Add :CFBundleDocumentTypes:0:LSItemContentTypes:$i string $t" "$PL"; i=$((i+1))
done
touch SkipMan.app
codesign --force --deep -s - SkipMan.app >/dev/null 2>&1 || true

# 4) Into Applications (the app always runs the code in this folder)
DEST="/Applications"
[ -w "$DEST" ] || DEST="$HOME/Applications"
mkdir -p "$DEST"
rm -rf "$DEST/SkipMan.app"
cp -R SkipMan.app "$DEST/SkipMan.app"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST/SkipMan.app" >/dev/null 2>&1 || true
echo "-> Installed to $DEST/SkipMan.app"

# 5) Pin to the Dock (if not already there)
if ! defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "SkipMan.app"; then
  defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$DEST/SkipMan.app</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
  killall Dock || true
  echo "-> Added to the Dock"
fi

# 6) Remember which version is installed (for auto-update)
if [ ! -d .git ]; then
  .venv/bin/python -c "from skipman import updater; updater._write_stamp(updater.latest_commit())" 2>/dev/null || true
fi

echo ""
echo "// DONE — opening SkipMan."
echo "   First time you send a song, macOS asks if SkipMan can control Music: click OK."
open "$DEST/SkipMan.app"
