"""Aplicația „Mac Deck” din ~/Applications: o deschizi din Launchpad / Dock / Spotlight și
- descarcă actualizările (git pull în folderul proiectului),
- pornește (sau repornește) serverul în fundal și pornirea automată la login,
- deschide configuratorul.
Fără Terminal după instalarea inițială."""
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile

from . import icons

APP = os.path.expanduser("~/Applications/Mac Deck.app")


def repo_path():
    """Folderul proiectului (git). Dacă rulăm din copia ~/.macdeck/app, îl citim din fișierul SOURCE."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(here, "SOURCE")
    if os.path.exists(src) and not os.path.isdir(os.path.join(here, ".git")):
        with open(src) as f:
            return f.read().strip() or here
    return here

SCRIPT = r"""#!/bin/bash
# Mac Deck: actualizare + pornire server + configurator. Generat de: python3 -m macdeck --install-app
REPO=%(repo)s
PY=%(python)s
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export GIT_TERMINAL_PROMPT=0
MODE="$1"
PLIST="$HOME/Library/LaunchAgents/ro.macdeck.server.plist"
notify() { osascript -e "display notification \"$1\" with title \"Mac Deck\"" >/dev/null 2>&1; }
up() { curl -s -o /dev/null --max-time 1 http://127.0.0.1:8765/setup; }

if ! cd "$REPO" 2>/dev/null; then
  notify "Nu găsesc proiectul în $REPO. Reinstalează aplicația din folderul proiectului."
  up && [ "$MODE" != "update" ] && open "http://127.0.0.1:8765/config"
  exit 1
fi

OLD=""; NEW=""
if [ -d .git ]; then
  OLD=$(git rev-parse HEAD 2>/dev/null)
  if ! git pull --ff-only -q >/dev/null 2>&1; then
    [ "$MODE" = "update" ] && notify "Actualizarea nu a reușit (git pull). Încearcă din Terminal: git pull"
  fi
  NEW=$(git rev-parse HEAD 2>/dev/null)
fi

if [ "$OLD" != "$NEW" ] || [ ! -f "$PLIST" ] || ! up; then
  "$PY" -m macdeck --autostart >/dev/null 2>&1
  if [ "$OLD" != "$NEW" ]; then notify "Actualizat la ultima versiune."
  elif [ "$MODE" = "update" ]; then notify "Ai deja ultima versiune."; fi
elif [ "$MODE" = "update" ]; then
  notify "Ai deja ultima versiune."
fi

for i in $(seq 1 30); do up && break; sleep 0.5; done
if ! up; then
  notify "Serverul nu pornește. Vezi jurnalul: ~/.macdeck/macdeck.log"
  open -a TextEdit "$HOME/.macdeck/macdeck.log" 2>/dev/null
  exit 1
fi
[ "$MODE" != "update" ] && open "http://127.0.0.1:8765/config"
exit 0
"""


def _q(s):
    return "'" + s.replace("'", "'\\''") + "'"


def make_icns(dest):
    """Iconița aplicației (aceeași grilă verde ca pe telefon), prin utilitarul iconutil din macOS."""
    tmp = tempfile.mkdtemp()
    iconset = os.path.join(tmp, "MacDeck.iconset")
    os.makedirs(iconset)
    for base in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = base * scale
            name = "icon_%dx%d%s.png" % (base, base, "@2x" if scale == 2 else "")
            with open(os.path.join(iconset, name), "wb") as f:
                f.write(icons.app_icon_png(px, maskable=True))
    r = subprocess.run(["iconutil", "-c", "icns", iconset, "-o", dest], capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return r.returncode == 0


def make_app():
    contents = os.path.join(APP, "Contents")
    macos = os.path.join(contents, "MacOS")
    res = os.path.join(contents, "Resources")
    if os.path.exists(APP):
        shutil.rmtree(APP)
    os.makedirs(macos)
    os.makedirs(res)
    exe = os.path.join(macos, "MacDeck")
    with open(exe, "w") as f:
        f.write(SCRIPT % {"repo": _q(repo_path()), "python": _q(sys.executable)})
    os.chmod(exe, 0o755)
    info = {
        "CFBundleName": "Mac Deck",
        "CFBundleDisplayName": "Mac Deck",
        "CFBundleIdentifier": "ro.macdeck.launcher",
        "CFBundleExecutable": "MacDeck",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "11.0",
        "LSUIElement": True,  # nu rămâne în Dock: își face treaba și se închide
        "NSHighResolutionCapable": True,
    }
    if sys.platform == "darwin" and make_icns(os.path.join(res, "AppIcon.icns")):
        info["CFBundleIconFile"] = "AppIcon"
    with open(os.path.join(contents, "Info.plist"), "wb") as f:
        plistlib.dump(info, f)
    if sys.platform == "darwin":
        # Finder / Launchpad află imediat de aplicația nouă
        subprocess.run(["touch", APP])
        lsr = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/"
               "Support/lsregister")
        if os.path.exists(lsr):
            subprocess.run([lsr, "-f", APP], capture_output=True)
    return APP


def run_update():
    """Pornește aplicația în modul „update” (git pull + repornire), din contextul ei de permisiuni."""
    if not os.path.exists(APP):
        raise RuntimeError("aplicația Mac Deck nu e instalată (python3 -m macdeck --install-app)")
    subprocess.Popen(["open", "-g", "-a", APP, "--args", "update"])
