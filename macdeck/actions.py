"""Acțiunile butoanelor. Fiecare acțiune primește dict-ul din config și întoarce un mesaj scurt."""
import json
import os
import subprocess
from urllib.parse import urlsplit

from . import system
from .system import SIM, log_sim, run, osa, osa_file

CHROME_LOCAL_STATE = os.path.expanduser("~/Library/Application Support/Google/Chrome/Local State")


class Soon(Exception):
    """Funcția vine într-o etapă viitoare."""

    def __init__(self, phase):
        super().__init__("vine în etapa %s" % phase)
        self.phase = phase


# ------------------------------------------------------------------ helpers

def default_match(url):
    """Textul după care recunoaștem un tab deja deschis: origin + cale, fără query."""
    p = urlsplit(url)
    path = p.path.rstrip("/")
    return "%s://%s%s" % (p.scheme, p.netloc, path)


def chrome_profile_dir(email):
    with open(CHROME_LOCAL_STATE, encoding="utf-8") as f:
        info = json.load(f).get("profile", {}).get("info_cache", {})
    for directory, meta in info.items():
        if (meta.get("user_name") or "").lower() == email.lower():
            return directory
    raise RuntimeError("nu găsesc profilul Chrome pentru %s" % email)


# ------------------------------------------------------------------ acțiuni

def do_app(a, ctx):
    run(["open", "-a", a["app"]])
    return "Deschis " + a["app"]


def do_chrome(a, ctx):
    url = a["url"]
    res = osa_file("chrome_open.applescript", url, a.get("match") or default_match(url),
                   "1" if a.get("new_tab") else "0")
    return "Tab adus în față" if res == "focused" else "Deschis în Chrome"


def do_chrome_profile(a, ctx):
    if SIM:
        log_sim("Chrome profil", a["email"])
        return "Profil deschis"
    d = chrome_profile_dir(a["email"])
    run(["open", "-na", "Google Chrome", "--args", "--profile-directory=" + d])
    return "Profil " + a["email"]


def do_lock(a, ctx):
    # ⌃⌘Q = Lock Screen (necesită permisiunea Accessibility)
    osa('tell application "System Events" to keystroke "q" using {control down, command down}')
    return "Mac blocat"


def do_display_sleep(a, ctx):
    run(["pmset", "displaysleepnow"])
    return "Ecran stins"


def do_screenshot(a, ctx):
    if a.get("mode") == "screen-recording":
        # ⌘⇧5 deschide bara de captură / înregistrare
        osa('tell application "System Events" to keystroke "5" using {command down, shift down}')
        return "Bara de înregistrare"
    # selecție de zonă, direct în clipboard (necesită permisiunea Screen Recording)
    if SIM:
        log_sim("screencapture -i -c")
    else:
        osa('tell application "System Events" to keystroke "4" using {command down, shift down, control down}')
    return "Selectează zona"


_caffeinate = {"proc": None}


def caffeinate_on():
    p = _caffeinate["proc"]
    return p is not None and (SIM or p.poll() is None)


def do_caffeinate(a, ctx):
    if caffeinate_on():
        if not SIM:
            _caffeinate["proc"].terminate()
        _caffeinate["proc"] = None
        msg = "Mac-ul poate adormi"
    else:
        if SIM:
            log_sim("caffeinate -di")
            _caffeinate["proc"] = True
        else:
            _caffeinate["proc"] = subprocess.Popen(["caffeinate", "-di"])
        msg = "Mac-ul rămâne treaz"
    ctx["state_changed"]()
    return msg


def do_claude(a, ctx):
    raise Soon(4)


def do_soon(a, ctx):
    raise Soon(a.get("phase", "?"))


HANDLERS = {
    "app": do_app,
    "chrome": do_chrome,
    "chrome_profile": do_chrome_profile,
    "lock": do_lock,
    "display_sleep": do_display_sleep,
    "screenshot": do_screenshot,
    "caffeinate": do_caffeinate,
    "claude": do_claude,
    "soon": do_soon,
}


def execute(action, ctx):
    h = HANDLERS.get(action.get("type"))
    if not h:
        raise ValueError("acțiune necunoscută: %s" % action.get("type"))
    return h(action, ctx)


def toggles():
    """Stările afișate pe butoane (state: ...)."""
    return {"caffeinate": caffeinate_on()}
