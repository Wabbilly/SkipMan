"""Build app icons from skipman/ui/icon.png into build/ (.icns on Mac, .ico on Windows)."""
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "skipman", "ui", "icon.png")
OUT = os.path.join(ROOT, "build")
os.makedirs(OUT, exist_ok=True)
img = Image.open(SRC).convert("RGBA")

if sys.platform.startswith("win"):
    img.save(os.path.join(OUT, "SkipMan.ico"),
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                    (128, 128), (256, 256)])
elif sys.platform == "darwin":
    iconset = os.path.join(tempfile.mkdtemp(), "SkipMan.iconset")
    os.makedirs(iconset)
    for s in (16, 32, 128, 256, 512):
        img.resize((s, s), Image.NEAREST).save(f"{iconset}/icon_{s}x{s}.png")
        img.resize((s * 2, s * 2), Image.NEAREST).save(
            f"{iconset}/icon_{s}x{s}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o",
                    os.path.join(OUT, "SkipMan.icns")], check=True)
    shutil.rmtree(os.path.dirname(iconset))
print("icons ready in", OUT)
