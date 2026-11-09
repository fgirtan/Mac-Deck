"""Funcțiile configuratorului (accesibil doar de pe Mac, la http://localhost:8765/config)."""
import base64
import json
import os
import re
import time

from . import actions, icons, system
from .icons import APP_DIRS, ICON_DIR

ACTION_TYPES = set(actions.HANDLERS)
MAX_ICON_BYTES = 2 * 1024 * 1024


def installed_apps():
    names = set()
    for d in APP_DIRS + ["/System/Applications/Utilities"]:
        try:
            for n in os.listdir(d):
                if n.endswith(".app"):
                    names.add(n[:-4])
        except OSError:
            pass
    if system.SIM:
        names |= {"Claude", "Slack", "Finder", "Safari", "Google Chrome", "Screaming Frog SEO Spider",
                  "MeetGeek", "Mission Control", "Activity Monitor", "Notion", "Spotify"}
    return sorted(names, key=str.lower)


def chrome_profiles():
    try:
        with open(actions.CHROME_LOCAL_STATE, encoding="utf-8") as f:
            info = json.load(f).get("profile", {}).get("info_cache", {})
    except (OSError, ValueError):
        return [{"dir": "Default", "email": "fgirtan@gmail.com", "name": "Florin"}] if system.SIM else []
    return [{"dir": d, "email": m.get("user_name") or "", "name": m.get("name") or d} for d, m in info.items()]


def shortcuts_list():
    if system.SIM:
        return ["Exemplu shortcut"]
    try:
        out = system.run(["shortcuts", "list"], timeout=10)
        return [l for l in out.splitlines() if l.strip()]
    except Exception:
        return []


def meta():
    return {"apps": installed_apps(), "chrome_profiles": chrome_profiles(),
            "shortcuts": shortcuts_list(), "action_types": sorted(ACTION_TYPES)}


def validate(cfg):
    """Verifică structura configurației. Întoarce o listă de erori (goală = OK)."""
    errs = []
    if not isinstance(cfg, dict):
        return ["configurația trebuie să fie un obiect"]
    ui = cfg.get("ui") or {}
    for k, lo, hi in (("columns", 2, 8), ("rows", 1, 6), ("sleep_minutes", 1, 240)):
        v = ui.get(k)
        if not isinstance(v, int) or not lo <= v <= hi:
            errs.append("ui.%s trebuie să fie între %d și %d" % (k, lo, hi))
    sets = cfg.get("sets")
    if not isinstance(sets, list) or not sets:
        return errs + ["trebuie să existe cel puțin un set"]
    seen = set()
    for si, s in enumerate(sets):
        if not isinstance(s.get("buttons"), list):
            errs.append("setul %d nu are listă de butoane" % (si + 1))
            continue
        for b in s["buttons"]:
            if b is None:
                continue
            bid = b.get("id")
            where = "„%s”" % (b.get("label") or bid)
            if not bid or not re.match(r"^[A-Za-z0-9_-]{1,64}$", str(bid)):
                errs.append("buton %s: id invalid" % where)
            elif bid in seen:
                errs.append("buton %s: id duplicat (%s)" % (where, bid))
            seen.add(bid)
            for key in ("action", "long"):
                a = b.get(key)
                if a is None and key == "long":
                    continue
                if not isinstance(a, dict) or a.get("type") not in ACTION_TYPES:
                    errs.append("buton %s: acțiune%s necunoscută" % (where, " lungă" if key == "long" else ""))
            page = b.get("page")
            if page and page not in (cfg.get("pages") or {}):
                errs.append("buton %s: pagina %s nu există" % (where, page))
    return errs


def save_icon(button_id, data_url):
    m = re.match(r"^data:image/(png|jpeg|jpg|webp|gif|svg\+xml);base64,(.+)$", data_url or "", re.S)
    if not m or not re.match(r"^[A-Za-z0-9_-]{1,64}$", button_id or ""):
        raise ValueError("imagine invalidă")
    ext = {"jpeg": "jpg", "svg+xml": "svg"}.get(m.group(1), m.group(1))
    raw = base64.b64decode(m.group(2))
    if len(raw) > MAX_ICON_BYTES:
        raise ValueError("imaginea e prea mare (maxim 2 MB)")
    os.makedirs(ICON_DIR, exist_ok=True)
    name = "custom-%s-%d.%s" % (button_id, int(time.time()), ext)
    with open(os.path.join(ICON_DIR, name), "wb") as f:
        f.write(raw)
    return name
