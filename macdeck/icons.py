"""Iconițele butoanelor: logo-ul real al aplicațiilor de pe Mac sau favicon-ul site-urilor.
Totul se păstrează în ~/.macdeck/icons; dacă nu se poate obține, deck-ul afișează o inițială."""
import os
import struct
import subprocess
import threading
import urllib.request
import zlib
from urllib.parse import urlsplit

from .config import HOME
from .system import SIM

ICON_DIR = os.path.join(HOME, "icons")
_lock = threading.Lock()
_failed = set()

APP_DIRS = [
    "/Applications",
    os.path.expanduser("~/Applications"),
    "/System/Applications",
    "/System/Applications/Utilities",
    "/Applications/Utilities",
    "/System/Library/CoreServices",
]

# JXA: cere iconița aplicației de la NSWorkspace (merge și pentru aplicațiile cu Assets.car)
# și salvează cea mai mare reprezentare ca PNG.
JXA = r"""
ObjC.import('AppKit');
function run(argv) {
  var img = $.NSWorkspace.sharedWorkspace.iconForFile(argv[0]);
  var reps = $.NSBitmapImageRep.imageRepsWithData(img.TIFFRepresentation);
  var best = null, bestW = 0;
  for (var i = 0; i < reps.count; i++) {
    var r = reps.objectAtIndex(i);
    if (r.pixelsWide > bestW && r.pixelsWide <= 512) { best = r; bestW = r.pixelsWide; }
  }
  if (!best) best = reps.objectAtIndex(0);
  var png = best.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $());
  png.writeToFileAtomically(argv[1], true);
  return bestW;
}
"""


def find_app(name):
    for d in APP_DIRS:
        p = os.path.join(d, name + ".app")
        if os.path.isdir(p):
            return p
    try:
        out = subprocess.run(
            ["mdfind", "kMDItemContentType == 'com.apple.application-bundle' && kMDItemFSName == '%s.app'" % name],
            capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
        return out[0] if out else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _app_icon(app, out):
    path = find_app(app)
    if not path:
        return False
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", JXA, path, out],
                       capture_output=True, text=True, timeout=15)
    return r.returncode == 0 and os.path.exists(out)


def _favicon(url, out):
    host = urlsplit(url).netloc
    src = "https://www.google.com/s2/favicons?domain=%s&sz=128" % host
    req = urllib.request.Request(src, headers={"User-Agent": "mac-deck"})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = r.read()
    # Google întoarce un glob generic de 16px când nu găsește nimic; îl ignorăm.
    if len(data) < 400:
        return False
    with open(out, "wb") as f:
        f.write(data)
    return True


def icon_source(button):
    """Întoarce ('app', nume) / ('url', adresă) / None pentru un buton."""
    icon = button.get("icon") or {}
    if icon.get("type") == "app":
        return ("app", icon["app"])
    if icon.get("type") == "url":
        return ("url", icon["url"])
    if icon.get("type") in ("glyph", "emoji", "image"):
        return None
    a = button.get("action") or {}
    if a.get("type") == "app":
        return ("app", a["app"])
    if a.get("type") == "chrome":
        return ("url", a["url"])
    return None


def icon_path(button):
    """Calea către PNG-ul iconiței (îl creează la prima cerere) sau None."""
    icon = button.get("icon") or {}
    if icon.get("type") == "image":
        p = os.path.join(ICON_DIR, os.path.basename(icon.get("file", "")))
        return p if icon.get("file") and os.path.exists(p) else None
    src = icon_source(button)
    if not src or SIM and src[0] == "app":
        return None
    os.makedirs(ICON_DIR, exist_ok=True)
    key = "%s-%s" % (src[0], "".join(c if c.isalnum() else "_" for c in src[1])[:80])
    out = os.path.join(ICON_DIR, key + ".png")
    if os.path.exists(out):
        return out
    if key in _failed:
        return None
    with _lock:
        if os.path.exists(out):
            return out
        try:
            ok = _app_icon(src[1], out) if src[0] == "app" else _favicon(src[1], out)
        except Exception:
            ok = False
        if not ok:
            _failed.add(key)
            return None
    return out


# ------------------------------------------------------------------ iconița aplicației web
# Un PNG generat fără biblioteci: fundal negru cu o grilă 3×3 de pătrate verzi.

def _png(w, h, rows):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def app_icon_png(size=180):
    bg, green, dim = (0, 0, 0), (48, 209, 88), (20, 70, 36)
    pad, gap = size * 0.16, size * 0.06
    cell = (size - 2 * pad - 2 * gap) / 3
    rad = cell * 0.22
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            col = bg
            cx, cy = (x - pad) / (cell + gap), (y - pad) / (cell + gap)
            if 0 <= cx < 3 and 0 <= cy < 3:
                ix, iy = int(cx), int(cy)
                lx, ly = x - pad - ix * (cell + gap), y - pad - iy * (cell + gap)
                if lx <= cell and ly <= cell:
                    dx = max(rad - lx, 0, lx - (cell - rad))
                    dy = max(rad - ly, 0, ly - (cell - rad))
                    if dx * dx + dy * dy <= rad * rad:
                        col = green if (ix + iy) % 2 == 0 else dim
            row.extend(col)
        rows.append(row)
    return _png(size, size, rows)
