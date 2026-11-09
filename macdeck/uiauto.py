"""Automatizarea interfeței macOS prin System Events (necesită permisiunea Accessibility):
clipboard, lipire de text, clic pe butoane după nume, listarea elementelor unei aplicații."""
import json
import subprocess
import time

from .system import SIM, log_sim, osa


def _q(s):
    """Text -> literal AppleScript."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def get_clipboard():
    if SIM:
        return ""
    try:
        return subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return ""


def set_clipboard(text):
    if SIM:
        log_sim("pbcopy", text[:60])
        return
    subprocess.run(["pbcopy"], input=text, text=True, timeout=3)


def paste_text(text, press_return=False, restore=True):
    """Lipește `text` în aplicația din față (prin clipboard, ca să meargă și diacriticele)."""
    old = get_clipboard() if restore else None
    set_clipboard(text)
    lines = ['tell application "System Events" to keystroke "v" using {command down}']
    if press_return:
        lines += ["delay 0.25", 'tell application "System Events" to key code 36']
    osa(*lines)
    if restore and old is not None:
        time.sleep(0.4)
        set_clipboard(old)


def activate(app):
    osa("tell application %s to activate" % _q(app))


def frontmost_app():
    if SIM:
        return "Finder"
    return osa('tell application "System Events" to get name of first application process whose frontmost is true')


def click_named(process, names, kinds=("button", "menu item", "checkbox", "menu bar item")):
    """Caută în toate elementele aplicației unul al cărui nume/descriere conține unul din `names`
    și dă clic pe el. Întoarce numele găsit sau None."""
    if SIM:
        log_sim("click", process, names)
        return names[0] if names else None
    conds = " or ".join("(n contains %s)" % _q(x) for x in names)
    script = """
tell application "System Events"
  if not (exists process %(p)s) then return "__NOPROC__"
  tell process %(p)s
    set els to entire contents
    repeat with e in els
      try
        set r to role of e
        if r is in {"AXButton", "AXMenuItem", "AXCheckBox", "AXMenuBarItem", "AXRadioButton"} then
          set n to ""
          try
            set n to (name of e) as text
          end try
          if n is "" or n is "missing value" then
            try
              set n to (description of e) as text
            end try
          end if
          if %(conds)s then
            click e
            return n
          end if
        end if
      end try
    end repeat
  end tell
end tell
return ""
""" % {"p": _q(process), "conds": conds}
    out = osa(script, timeout=25)
    if out == "__NOPROC__":
        raise RuntimeError("%s nu rulează" % process)
    return out or None


def exists_named(process, names):
    """Ca click_named, dar doar verifică existența (pentru afișarea stării)."""
    if SIM:
        return False
    conds = " or ".join("(n contains %s)" % _q(x) for x in names)
    script = """
tell application "System Events"
  if not (exists process %(p)s) then return "0"
  tell process %(p)s
    repeat with e in (entire contents)
      try
        set n to ""
        try
          set n to (name of e) as text
        end try
        if n is "" or n is "missing value" then set n to (description of e) as text
        if %(conds)s then return "1"
      end try
    end repeat
  end tell
end tell
return "0"
""" % {"p": _q(process), "conds": conds}
    try:
        return osa(script, timeout=25) == "1"
    except RuntimeError:
        return False


def click_menu(process, path):
    """Clic pe un meniu: path = ["Mode", "List"]."""
    if SIM:
        log_sim("menu", process, " > ".join(path))
        return
    if len(path) == 2:
        ref = "menu item %s of menu %s of menu bar item %s of menu bar 1" % (_q(path[1]), _q(path[0]), _q(path[0]))
    elif len(path) == 3:
        ref = ("menu item %s of menu %s of menu item %s of menu %s of menu bar item %s of menu bar 1"
               % (_q(path[2]), _q(path[1]), _q(path[1]), _q(path[0]), _q(path[0])))
    else:
        raise ValueError("cale de meniu invalidă")
    osa('tell application "System Events" to tell process %s to click %s' % (_q(process), ref))


def dump(process, limit=400):
    """Lista elementelor UI ale unei aplicații (rol, nume, descriere) - pentru diagnostic."""
    if SIM:
        return [{"role": "AXButton", "name": "Start", "desc": ""}, {"role": "AXMenuItem", "name": "List", "desc": ""}]
    script = """
set out to ""
tell application "System Events"
  if not (exists process %(p)s) then return "__NOPROC__"
  tell process %(p)s
    set i to 0
    repeat with e in (entire contents)
      set i to i + 1
      if i > %(lim)d then exit repeat
      try
        set r to role of e
        set n to ""
        set d to ""
        try
          set n to (name of e) as text
        end try
        try
          set d to (description of e) as text
        end try
        if r is in {"AXButton", "AXMenuItem", "AXCheckBox", "AXMenuBarItem", "AXRadioButton", "AXTextField", "AXPopUpButton", "AXStaticText"} then
          set out to out & r & tab & n & tab & d & linefeed
        end if
      end try
    end repeat
  end tell
end tell
return out
""" % {"p": _q(process), "lim": limit}
    out = osa(script, timeout=60)
    if out == "__NOPROC__":
        raise RuntimeError("%s nu rulează" % process)
    res = []
    for line in out.splitlines():
        p = (line.split("\t") + ["", ""])[:3]
        res.append({"role": p[0], "name": "" if p[1] == "missing value" else p[1],
                    "desc": "" if p[2] == "missing value" else p[2]})
    return res


def notify(title, text):
    if SIM:
        log_sim("notificare", title, text)
        return
    try:
        osa("display notification %s with title %s sound name \"Glass\"" % (_q(text), _q(title)))
    except RuntimeError:
        pass
