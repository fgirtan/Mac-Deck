"""Controlul Google Chrome: tab-uri, JavaScript în pagini, tab-ul activ."""
import json

from .system import SIM, osa_file, run

JS_OFF_HINT = ("Activează în Chrome: View → Developer → Allow JavaScript from Apple Events")


class ChromeError(Exception):
    pass


def js(match, code, timeout=8):
    """Rulează `code` (o expresie JS care întoarce un string) în tab-ul care conține `match`."""
    if SIM:
        return None
    try:
        out = osa_file("chrome_js.applescript", match, code, timeout=timeout)
    except RuntimeError as e:
        msg = str(e)
        if "JavaScript" in msg and ("Apple" in msg or "turned off" in msg or "dezactiv" in msg):
            raise ChromeError(JS_OFF_HINT)
        raise ChromeError(msg)
    if out in ("__NOCHROME__", "__NOTAB__"):
        return None
    return out


def js_json(match, code, timeout=8):
    out = js(match, code, timeout)
    if not out:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def tabs():
    """Lista tab-urilor: [{"active": bool, "url": str, "title": str}]."""
    if SIM:
        return []
    try:
        out = osa_file("chrome_tabs.applescript", timeout=6)
    except RuntimeError:
        return []
    res = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            res.append({"active": parts[0] == "1", "url": parts[1], "title": parts[2]})
    return res


def active_url():
    for t in tabs():
        if t["active"]:
            return t["url"]
    return None


def open_url(url, match=None, new_tab=False):
    from .actions import default_match
    return osa_file("chrome_open.applescript", url, match or default_match(url), "1" if new_tab else "0")


def set_url(match, url):
    """Navighează tab-ul existent (sau deschide unul nou) la `url` și îl aduce în față."""
    if js(match, "location.href=%s;'ok'" % json.dumps(url)) is None:
        open_url(url, match)
    else:
        open_url(url, match)  # aduce tab-ul în față


def running():
    if SIM:
        return False
    try:
        return run(["pgrep", "-x", "Google Chrome"], check=False) != ""
    except Exception:
        return False
