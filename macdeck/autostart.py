"""Pornire automată la login (LaunchAgent macOS): serverul rulează în fundal, fără Terminal,
și repornește singur dacă se oprește."""
import os
import shutil
import subprocess
import sys

from .config import HOME

LABEL = "ro.macdeck.server"
PLIST = os.path.expanduser("~/Library/LaunchAgents/%s.plist" % LABEL)
LOG = os.path.join(HOME, "macdeck.log")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Copie a aplicației într-un folder pe care macOS nu-l protejează. Un proces pornit de launchd
# nu poate citi Documents / Desktop / Downloads (unde e adesea clonat proiectul) fără Full Disk Access.
APP_DIR = os.path.join(HOME, "app")

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>-m</string>
    <string>macdeck</string>
  </array>
  <key>WorkingDirectory</key><string>{repo}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key><string>1</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
"""


def _launchctl(*args):
    return subprocess.run(["launchctl"] + list(args), capture_output=True, text=True)


def domain():
    return "gui/%d" % os.getuid()


def installed():
    return os.path.exists(PLIST)


def running():
    r = _launchctl("print", "%s/%s" % (domain(), LABEL))
    return r.returncode == 0 and "state = running" in r.stdout


def real_python():
    """Calea reală a interpretorului Python (cea care trebuie adăugată la Accessibility)."""
    exe = os.path.realpath(sys.executable)
    # Python din Command Line Tools rulează de fapt prin Python.app din framework
    fw = os.path.join(os.path.dirname(os.path.dirname(exe)), "Resources", "Python.app")
    return fw if os.path.isdir(fw) else exe


def sync_app():
    """Copiază pachetul macdeck din proiect în ~/.macdeck/app (la instalare și la fiecare repornire)."""
    src = os.path.join(REPO, "macdeck")
    if os.path.realpath(src).startswith(os.path.realpath(APP_DIR)):
        return  # rulăm deja din copie
    dst = os.path.join(APP_DIR, "macdeck")
    tmp = dst + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.rmtree(dst, ignore_errors=True)
    os.replace(tmp, dst)
    with open(os.path.join(APP_DIR, "SOURCE"), "w") as f:
        f.write(REPO + "\n")


def install():
    os.makedirs(os.path.dirname(PLIST), exist_ok=True)
    os.makedirs(HOME, exist_ok=True)
    sync_app()
    with open(PLIST, "w") as f:
        f.write(TEMPLATE.format(label=LABEL, python=sys.executable, repo=APP_DIR, log=LOG))
    _launchctl("bootout", "%s/%s" % (domain(), LABEL))  # dacă era deja încărcat
    r = _launchctl("bootstrap", domain(), PLIST)
    if r.returncode != 0 and "already" not in (r.stderr or ""):
        raise RuntimeError(r.stderr.strip() or "launchctl a eșuat")
    _launchctl("kickstart", "-k", "%s/%s" % (domain(), LABEL))
    # aplicația „Mac Deck” din ~/Applications (dacă nu există deja)
    try:
        from . import macapp
        if not os.path.exists(macapp.APP):
            macapp.make_app()
    except Exception as e:
        print("  ! nu am putut crea aplicația Mac Deck: %s" % e)


def uninstall():
    _launchctl("bootout", "%s/%s" % (domain(), LABEL))
    if os.path.exists(PLIST):
        os.remove(PLIST)


def restart():
    if installed():
        sync_app()  # preia modificările aduse de git pull
    _launchctl("kickstart", "-k", "%s/%s" % (domain(), LABEL))


def main(cmd):
    if sys.platform != "darwin":
        print("Pornirea automată funcționează doar pe macOS.")
        return 1
    if cmd == "install":
        install()
        print()
        print("  ✓ Mac Deck pornește acum automat la fiecare login și rulează în fundal.")
        print("    Nu mai ai nevoie de Terminal. Configuratorul: http://localhost:8765/config")
        print("    (acolo găsești și adresa pentru iPhone și codul de asociere: butonul „iPhone”)")
        print()
        print("  ! Permisiuni: în fundal, macOS cere permisiunile pentru Python, nu pentru Terminal.")
        print("    System Settings → Privacy & Security → Accessibility → + și adaugă:")
        print("    " + real_python())
        print("    (în fereastra de alegere apasă ⌘⇧G și lipește calea de mai sus)")
        print()
        print("  Jurnal: " + LOG)
        print()
        print("  Aplicația „Mac Deck” e în ~/Applications (o găsești în Launchpad și cu ⌘ Space).")
        print("  O deschizi ca să actualizezi deck-ul și să deschizi configuratorul. Poți s-o tragi în Dock.")
    elif cmd == "uninstall":
        uninstall()
        print("  ✓ Pornirea automată a fost oprită. Serverul nu mai rulează în fundal.")
    elif cmd == "restart":
        restart()
        print("  ✓ Serverul a fost repornit.")
    elif cmd == "status":
        print("  Pornire automată: %s · Server: %s" % ("instalată" if installed() else "neinstalată",
                                                      "rulează" if running() else "oprit"))
        if os.path.exists(LOG):
            print("\n  Ultimele linii din jurnal (%s):" % LOG)
            with open(LOG, errors="replace") as f:
                for line in f.readlines()[-15:]:
                    print("    " + line.rstrip())
    return 0
