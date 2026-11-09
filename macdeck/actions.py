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


def do_url(a, ctx):
    run(["open", a["url"]])
    return "Deschis în browser"


# Taste speciale -> key code (System Events)
KEY_CODES = {
    "return": 36, "enter": 76, "tab": 48, "space": 49, "delete": 51, "backspace": 51, "esc": 53, "escape": 53,
    "left": 123, "right": 124, "down": 125, "up": 126, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "forwarddelete": 117,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100, "f9": 101,
    "f10": 109, "f11": 103, "f12": 111,
}
MODS = {"cmd": "command down", "command": "command down", "⌘": "command down",
        "shift": "shift down", "⇧": "shift down",
        "alt": "option down", "opt": "option down", "option": "option down", "⌥": "option down",
        "ctrl": "control down", "control": "control down", "⌃": "control down"}


def keystroke_script(combo):
    """'cmd+shift+f' -> comanda AppleScript pentru System Events."""
    parts = [p.strip().lower() for p in combo.replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise ValueError("scurtătură goală")
    key, mods = parts[-1], []
    for m in parts[:-1]:
        if m not in MODS:
            raise ValueError("modificator necunoscut: %s" % m)
        mods.append(MODS[m])
    using = (" using {%s}" % ", ".join(mods)) if mods else ""
    if key in KEY_CODES:
        return "key code %d%s" % (KEY_CODES[key], using)
    if len(key) != 1:
        raise ValueError("tastă necunoscută: %s" % key)
    return 'keystroke "%s"%s' % (key.replace("\\", "\\\\").replace('"', '\\"'), using)


def do_keys(a, ctx):
    lines = []
    if a.get("app"):
        lines.append('tell application "%s" to activate' % a["app"].replace('"', ''))
        lines.append("delay 0.25")
    lines.append('tell application "System Events" to ' + keystroke_script(a["keys"]))
    osa(*lines)
    return a["keys"]


def do_applescript(a, ctx):
    out = osa(a["script"], timeout=30)
    return (out[:80] if out else "AppleScript rulat")


def do_shell(a, ctx):
    out = run(["/bin/bash", "-lc", a["command"]], timeout=60)
    return (out.splitlines()[-1][:80] if out else "Comandă rulată")


def do_shortcut(a, ctx):
    run(["shortcuts", "run", a["name"]], timeout=120)
    return "Shortcut: " + a["name"]


def do_claude(a, ctx):
    prompts = a.get("prompts") or []
    prompt = None
    if prompts:
        i = a.get("choice", 0)
        prompt = prompts[max(0, min(int(i), len(prompts) - 1))].get("text")
    return ctx["features"].claude(a.get("item"), prompt, new_chat=not a.get("item"))


def do_sequence(a, ctx):
    """Macro: rulează pașii pe rând (ex. „Pornește ziua”)."""
    import time
    done, errors = 0, []
    for step in a.get("steps") or []:
        try:
            execute(step, ctx)
            done += 1
        except Exception as e:
            errors.append(str(e))
        time.sleep(float(a.get("delay", 0.8)))
    if errors:
        return "%d pași rulați, %d erori: %s" % (done, len(errors), errors[0])
    return "%d pași rulați" % done


def do_spotify(a, ctx):
    return ctx["features"].page_cmd("spotify", {"cmd": a.get("cmd", "playpause")})


def do_meet(a, ctx):
    return ctx["features"].page_cmd("meet", {"cmd": a.get("cmd", "mic")})


def do_mic_mute(a, ctx):
    return ctx["features"].toggle_mic()


def do_focus(a, ctx):
    return ctx["features"].toggle_focus()


def do_timer(a, ctx):
    return ctx["features"].timer_cmd(a.get("cmd", "toggle"))


def do_next_meeting(a, ctx):
    nm = ctx["features"].live.get("next_meeting")
    if nm and nm.get("link"):
        from . import chrome
        chrome.open_url(nm["link"])
        return "Intru în: " + nm.get("title", "")
    run(["open", "https://calendar.google.com"])
    return "Niciun meeting cu link în următoarele ore" if not nm else "Meeting fără link: " + nm.get("title", "")


def do_crawl_current(a, ctx):
    return ctx["features"].crawl_current()


def do_page(a, ctx):
    return ""  # doar deschide pagina pe telefon


def do_window(a, ctx):
    return ctx["features"].window(a.get("op", "full"))


def do_snippet(a, ctx):
    from . import uiauto
    uiauto.paste_text(a.get("text", ""), press_return=bool(a.get("enter")))
    return "Text lipit"


def do_profile(a, ctx):
    cfg = ctx["deck"].config.get()
    cfg.setdefault("ui", {})["profile"] = a.get("name") or "auto"
    ctx["deck"].config.save(cfg)
    ctx["features"]._update_profile()
    ctx["deck"].hub.send({"type": "config"})
    return "Profil: " + (a.get("name") or "automat")


def do_soon(a, ctx):
    raise Soon(a.get("phase", "?"))


HANDLERS = {
    "app": do_app,
    "chrome": do_chrome,
    "chrome_profile": do_chrome_profile,
    "url": do_url,
    "keys": do_keys,
    "applescript": do_applescript,
    "shell": do_shell,
    "shortcut": do_shortcut,
    "lock": do_lock,
    "display_sleep": do_display_sleep,
    "screenshot": do_screenshot,
    "caffeinate": do_caffeinate,
    "claude": do_claude,
    "sequence": do_sequence,
    "spotify": do_spotify,
    "meet": do_meet,
    "mic_mute": do_mic_mute,
    "focus": do_focus,
    "timer": do_timer,
    "next_meeting": do_next_meeting,
    "crawl_current": do_crawl_current,
    "page": do_page,
    "window": do_window,
    "snippet": do_snippet,
    "profile": do_profile,
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
