# PyInstaller recipe for the downloadable SkipMan app (Mac .app / Windows .exe)
# Built by .github/workflows/release.yml:  pyinstaller packaging/SkipMan.spec
# Put ffmpeg + ffprobe in build/ffmpeg/ first and they get bundled.

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

with open(os.path.join(ROOT, "skipman", "__init__.py")) as f:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)

datas = [(os.path.join(ROOT, "skipman", "ui"), "skipman/ui")]
binaries = []
ff = os.path.join(ROOT, "build", "ffmpeg")
if os.path.isdir(ff):
    for name in os.listdir(ff):
        # Windows: ship as plain files so PyInstaller doesn't copy FFmpeg's
        # DLLs a second time. Mac: as binaries so they get signed.
        (datas if IS_WIN else binaries).append((os.path.join(ff, name), "ffmpeg"))

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    excludes=["tkinter", "static_ffmpeg", "pytest", "PyQt5", "PyQt6",
              "PySide2", "PySide6", "gi", "matplotlib", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

icon = None
if IS_MAC and os.path.exists(os.path.join(ROOT, "build", "SkipMan.icns")):
    icon = os.path.join(ROOT, "build", "SkipMan.icns")
if IS_WIN and os.path.exists(os.path.join(ROOT, "build", "SkipMan.ico")):
    icon = os.path.join(ROOT, "build", "SkipMan.ico")

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SkipMan",
    console=False,
    icon=icon,
    argv_emulation=IS_MAC,      # links dropped on the icon at launch
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="SkipMan", upx=False)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="SkipMan.app",
        icon=icon,
        bundle_identifier="com.wabbilly.skipman",
        version=VERSION,
        info_plist={
            "CFBundleName": "SkipMan",
            "CFBundleDisplayName": "SkipMan",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.music",
            "NSHighResolutionCapable": True,
            "NSAppleEventsUsageDescription":
                "SkipMan adds your songs to the Music app and its SkipMan playlist.",
            "CFBundleURLTypes": [{
                "CFBundleURLName": "SkipMan link",
                "CFBundleURLSchemes": ["skipman"],
            }],
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Link",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["public.url",
                                       "com.apple.web-internet-location",
                                       "public.plain-text"],
            }],
        },
    )
