"""Paginile dedicate și funcțiile „live” ale deck-ului (etapele 3–6):
Spotify, Google Meet, Activity Monitor, Claude, Screaming Frog, MeetGeek, prompt vocal,
snippets, Pomodoro, analiză SEO, ieșire audio, ferestre, următorul meeting, insigne,
Focus, microfon, profiluri."""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import quote, urlsplit

from . import chrome, ics, uiauto
from .monitor import MONITOR
from .system import SCRIPTS, SIM, log_sim, osa, osa_file, run

MEET_CALL_RE = re.compile(r"https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}")
SF_APP = "Screaming Frog SEO Spider"
SF_CLI = "/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderLauncher"
SWITCH_AUDIO = ["/opt/homebrew/bin/SwitchAudioSource", "/usr/local/bin/SwitchAudioSource"]

# ------------------------------------------------------------------ JavaScript pentru pagini web

SPOTIFY_STATE_JS = r"""(function(){
var q=function(s){return document.querySelector(s)};var ms=navigator.mediaSession||{};var m=ms.metadata;
var t=(m&&m.title)||((q('[data-testid="context-item-info-title"]')||{}).textContent)||'';
var a=(m&&m.artist)||((q('[data-testid="context-item-info-artist"]')||{}).textContent)||'';
var art='';if(m&&m.artwork&&m.artwork.length){art=m.artwork[m.artwork.length-1].src}else{var i=q('[data-testid="now-playing-widget"] img');if(i)art=i.src}
var pp=q('[data-testid="control-button-playpause"]');var playing=ms.playbackState==='playing';
if(pp&&(!ms.playbackState||ms.playbackState==='none')){playing=/pauz|pause/i.test(pp.getAttribute('aria-label')||'')}
return JSON.stringify({title:t,artist:a,art:art,playing:playing});})()"""

SPOTIFY_CLICK_JS = r"""(function(id){var b=document.querySelector('[data-testid="'+id+'"]');if(!b)return 'notfound';b.click();return 'ok';})(%s)"""

MEET_JS = r"""(function(cmd){
var bs=[].slice.call(document.querySelectorAll('button,[role="button"]'));
function lab(b){return ((b.getAttribute('aria-label')||'')+' '+(b.getAttribute('data-tooltip')||'')).toLowerCase()}
var R={mic:[/\+ ?d\)/,/microphone|microfon/],cam:[/\+ ?e\)/,/camera|cameră|camera/],
hand:[/\+ ?h\)/,/raise hand|lower hand|ridică mâna|coboară mâna/],chat:[/chat/],people:[/people|participan|persoane/],
captions:[/\(c\)/,/caption|subtitr/],present:[/present now|prezint|share screen|prezentare/],
leave:[/leave call|părăsește|ieși din apel|end call|părăsiți/]};
function find(res,list){list=list||bs;for(var j=0;j<res.length;j++){for(var i=0;i<list.length;i++){if(res[j].test(lab(list[i])))return list[i]}}return null}
var muted=[].slice.call(document.querySelectorAll('[data-is-muted]'));
var mic=find(R.mic,muted),cam=find(R.cam,muted.filter(function(b){return b!==mic}));
var B={mic:mic,cam:cam,hand:find(R.hand),chat:find(R.chat),people:find(R.people),captions:find(R.captions),present:find(R.present),leave:find(R.leave)};
if(cmd){var b=B[cmd];if(!b)return 'notfound';b.click();return 'ok';}
function pr(b){return b?b.getAttribute('aria-pressed')==='true':null}
return JSON.stringify({in_call:!!(B.leave||mic),mic_on:mic?mic.getAttribute('data-is-muted')==='false':null,
cam_on:cam?cam.getAttribute('data-is-muted')==='false':null,hand:pr(B.hand),captions:pr(B.captions),
chat:pr(B.chat),people:pr(B.people),title:document.title});})(%s)"""

MEET_KEYS = {"mic": "cmd+d", "cam": "cmd+e", "hand": "ctrl+cmd+h", "chat": "ctrl+cmd+c",
             "people": "ctrl+cmd+p", "captions": "c"}

DOCK_BADGES = """
tell application "System Events" to tell process "Dock"
  set out to ""
  repeat with e in UI elements of list 1
    try
      set b to value of attribute "AXStatusLabel" of e
      if b is not missing value then set out to out & (name of e) & tab & b & linefeed
    end try
  end repeat
end tell
return out
"""


def _keys(combo, app=None):
    from .actions import keystroke_script
    lines = []
    if app:
        lines += ['tell application "%s" to activate' % app.replace('"', ""), "delay 0.25"]
    lines.append('tell application "System Events" to ' + keystroke_script(combo))
    osa(*lines)


def _bin(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return shutil.which(os.path.basename(paths[0]))


def osa_file_safe(name):
    try:
        return osa_file(name, timeout=4)
    except RuntimeError:
        return ""


class Features:
    def __init__(self, deck):
        self.deck = deck
        self.live = {"meet_call": False, "meet": None, "spotify": None, "badges": {}, "next_meeting": None,
                     "timer": None, "focus": False, "mic_muted": False, "profile": None, "hint": None}
        self.lock = threading.Lock()
        self.sf = {"mode": "spider", "url": "", "list": "", "config": "", "proc": None, "log": [],
                   "progress": None, "started": None, "out": None}
        self.timer = {"mode": "work", "running": False, "ends_at": None, "left": None, "round": 1}
        self._mic_prev = 75
        self._ics_text = None
        self._ics_fetched = 0
        self._mg_cache = (0, None)
        self._sim_front = None

    # ---------------------------------------------------------------- utilitare
    def cfg(self):
        return self.deck.config.get()

    def page_cfg(self, pid):
        return (self.cfg().get("pages") or {}).get(pid) or {}

    def integ(self, key):
        return (self.cfg().get("integrations") or {}).get(key) or {}

    def set_live(self, **kw):
        with self.lock:
            changed = any(self.live.get(k) != v for k, v in kw.items())
            self.live.update(kw)
        if changed:
            self.deck.push_state()

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.live))

    def event(self, **ev):
        self.deck.hub.send(ev)

    # ---------------------------------------------------------------- fire de fundal
    def start(self):
        for target in (self._fast_loop, self._slow_loop, self._timer_loop, self._front_loop):
            threading.Thread(target=target, daemon=True).start()

    def _active(self):
        return self.deck.hub.count() > 0

    # ---------------------------------------------------------------- aplicația din față -> deck
    def front_app(self):
        """Numele aplicației active pe Mac și, pentru Chrome, URL-ul tab-ului activ."""
        if SIM:
            return self._sim_front, None
        asn = run(["lsappinfo", "front"], check=False).strip()
        if not asn:
            return None, None
        out = run(["lsappinfo", "info", "-only", "name", asn], check=False)
        m = re.search(r'"LSDisplayName"="(.*)"', out)
        name = m.group(1) if m else None
        url = None
        if name == "Google Chrome":
            url = osa_file_safe("chrome_active.applescript") or None
        return name, url

    def auto_target(self, app, url):
        """Ce trebuie afișat pe deck pentru aplicația/URL-ul activ: (pagină, index set)."""
        cfg = self.cfg()
        page = None
        for s in cfg.get("sets", []):
            for b in s.get("buttons", []):
                if not b or not b.get("page") or b.get("auto_page") is False or b.get("page") == "meet":
                    continue
                a = b.get("action") or {}
                if a.get("type") == "app" and app and a.get("app", "").lower() == app.lower():
                    page = b["page"]
                elif a.get("type") == "chrome" and url:
                    host = urlsplit(a.get("url", "")).netloc
                    if (a.get("match") and a["match"] in url) or (host and "://" + host in url):
                        page = b["page"]
                if page:
                    break
            if page:
                break
        set_idx = None
        for i, s in enumerate(cfg.get("sets", [])):
            for entry in s.get("apps") or []:
                e = entry.strip().lower()
                if e and ((app and e == app.lower()) or (url and e in url.lower())):
                    set_idx = i
                    break
            if set_idx is not None:
                break
        return page, set_idx

    def _front_loop(self):
        last = None
        while True:
            time.sleep(1)
            ui = self.cfg().get("ui") or {}
            if not self._active() or ui.get("auto_switch") is False:
                last = None
                continue
            try:
                app, url = self.front_app()
            except Exception:
                continue
            if not app or app in ("loginwindow", "ScreenSaverEngine"):
                continue
            page, set_idx = self.auto_target(app, url)
            key = (app, page, set_idx)
            if key == last:
                continue
            last = key
            self.event(type="auto", app=app, page=page, set=set_idx,
                       close=ui.get("auto_close", True))

    def _fast_loop(self):
        while True:
            time.sleep(2)
            if not self._active() or SIM:
                continue
            try:
                self._watch_chrome()
            except Exception as e:
                print("  ! chrome: %s" % e)

    def _slow_loop(self):
        n = 0
        while True:
            time.sleep(5)
            n += 1
            if not self._active():
                continue
            try:
                self._update_badges()
            except Exception:
                pass
            self.read_mic()
            if n % 6 == 1:
                try:
                    self._update_meeting()
                except Exception as e:
                    print("  ! calendar: %s" % e)
                self._update_profile()

    def _timer_loop(self):
        while True:
            time.sleep(1)
            t = self.timer
            if t["running"] and t["ends_at"] and time.time() >= t["ends_at"]:
                done = t["mode"]
                durs = self.page_cfg("timer")
                nxt = "break" if done == "work" else "work"
                if done == "break":
                    t["round"] += 1
                t.update(mode=nxt, running=False, ends_at=None,
                         left=int(durs.get(nxt, 25 if nxt == "work" else 5)) * 60)
                msg = "Pauză! Ai terminat o sesiune de lucru." if done == "work" else "Pauza s-a terminat. Înapoi la lucru."
                uiauto.notify("Pomodoro", msg)
                self.event(type="toast", msg="⏱ " + msg)
            self.set_live(timer=self._timer_view())

    # ---------------------------------------------------------------- Chrome: Meet + Spotify
    def _watch_chrome(self):
        tabs = chrome.tabs()
        call = next((t["url"] for t in tabs if MEET_CALL_RE.match(t["url"])), None)
        was = self.live.get("meet_call")
        meet = None
        if call:
            try:
                meet = chrome.js_json(MEET_CALL_RE.match(call).group(0), MEET_JS % "null")
            except chrome.ChromeError as e:
                self.set_live(hint=str(e))
        in_call = bool(call) and (meet is None or meet.get("in_call"))
        if in_call and not was:
            self.event(type="open-page", page="meet")
            if self.integ("focus").get("during_meet") and not self.live.get("focus"):
                self._focus(True)
        elif was and not in_call:
            self.event(type="close-page", page="meet")
            if self.integ("focus").get("during_meet") and self.live.get("focus"):
                self._focus(False)
        sp = None
        if any("open.spotify.com" in t["url"] for t in tabs):
            try:
                sp = chrome.js_json("open.spotify.com", SPOTIFY_STATE_JS)
            except chrome.ChromeError as e:
                self.set_live(hint=str(e))
        gmail = None
        for t in tabs:
            if "mail.google.com" in t["url"]:
                m = re.search(r"\((\d+)\)", t["title"])
                gmail = int(m.group(1)) if m else 0
                break
        badges = dict(self.live.get("badges") or {})
        badges["__gmail"] = gmail
        self.set_live(meet_call=in_call, meet=meet if in_call else None, spotify=sp, badges=badges)

    def _update_badges(self):
        if SIM:
            return
        try:
            out = osa(DOCK_BADGES, timeout=6)
        except RuntimeError:
            return
        dock = {}
        for line in out.splitlines():
            if "\t" in line:
                name, val = line.split("\t", 1)
                dock[name.strip()] = val.strip()
        badges = dict(self.live.get("badges") or {})
        badges["__dock"] = dock
        self.set_live(badges=badges)

    # ---------------------------------------------------------------- calendar
    def _update_meeting(self):
        url = self.integ("calendar").get("ical_url")
        if not url:
            if self.live.get("next_meeting"):
                self.set_live(next_meeting=None)
            return
        if not self._ics_text or time.time() - self._ics_fetched > 300:
            self._ics_text = ics.fetch(url)
            self._ics_fetched = time.time()
        self.set_live(next_meeting=ics.next_meeting(self._ics_text))

    # ---------------------------------------------------------------- profiluri
    def _update_profile(self):
        cfg = self.cfg()
        profiles = cfg.get("profiles") or []
        manual = (cfg.get("ui") or {}).get("profile") or "auto"
        if not profiles:
            name = None
        elif manual != "auto":
            name = manual
        else:
            now = dt.datetime.now()
            name = profiles[-1].get("name")
            for p in profiles:
                days = p.get("days") or [1, 2, 3, 4, 5, 6, 7]
                fr, to = p.get("from", "00:00"), p.get("to", "23:59")
                hm = now.strftime("%H:%M")
                if now.isoweekday() in days and fr <= hm < to:
                    name = p.get("name")
                    break
        self.set_live(profile=name)

    # ---------------------------------------------------------------- Focus / microfon
    def _focus(self, on):
        f = self.integ("focus")
        name = f.get("on_shortcut" if on else "off_shortcut") or ("Mac Deck Focus On" if on else "Mac Deck Focus Off")
        run(["shortcuts", "run", name], timeout=30)
        self.set_live(focus=on)
        return "Focus pornit" if on else "Focus oprit"

    def toggle_focus(self):
        return self._focus(not self.live.get("focus"))

    def toggle_mic(self):
        if SIM:
            muted = not self.live.get("mic_muted")
        else:
            cur = int(osa("input volume of (get volume settings)") or 0)
            if cur > 0:
                self._mic_prev = cur
                osa("set volume input volume 0")
                muted = True
            else:
                osa("set volume input volume %d" % (self._mic_prev or 75))
                muted = False
        self.set_live(mic_muted=muted)
        return "Microfon oprit" if muted else "Microfon pornit"

    def read_mic(self):
        if SIM:
            return
        try:
            self.live["mic_muted"] = int(osa("input volume of (get volume settings)") or 0) == 0
        except Exception:
            pass

    # ---------------------------------------------------------------- Claude
    def claude(self, item=None, prompt=None, new_chat=False):
        c = self.integ("claude")
        d = c.get("delays") or {}
        app = c.get("app") or "Claude"
        if SIM:
            log_sim("Claude", item or "(chat nou)", (prompt or "")[:60])
            return "Trimis în Claude"
        uiauto.activate(app)
        time.sleep(float(d.get("activate", 0.8)))
        if new_chat:
            _keys(c.get("new_chat_keys") or "cmd+n")
            time.sleep(float(d.get("open", 1.5)))
        elif item:
            _keys(c.get("search_keys") or "cmd+k")
            time.sleep(float(d.get("search", 0.7)))
            uiauto.paste_text(item)
            time.sleep(float(d.get("results", 1.2)))
            osa('tell application "System Events" to key code 36')
            time.sleep(float(d.get("open", 2.0)))
        if prompt:
            uiauto.paste_text(prompt, press_return=True)
            return "Prompt trimis în Claude"
        return "Deschis în Claude"

    # ---------------------------------------------------------------- Screaming Frog
    def sf_view(self):
        s = self.sf
        p = s["proc"]
        running = p is not None and (p.poll() is None)
        return {"mode": s["mode"], "url": s["url"], "list": s["list"], "config": s["config"],
                "configs": self.page_cfg("sfrog").get("configs") or [],
                "cli": {"running": running, "progress": s["progress"], "log": s["log"][-6:],
                        "started": s["started"], "out": s["out"],
                        "exit": (p.returncode if p is not None and not running else None)},
                "cli_available": SIM or os.path.exists(SF_CLI)}

    def sf_cli(self, mode, url=None, urls=None, config=None):
        if self.sf["proc"] is not None and self.sf["proc"].poll() is None:
            raise RuntimeError("un crawl rulează deja")
        pc = self.page_cfg("sfrog")
        out = os.path.expanduser(pc.get("output_folder") or "~/Documents/Mac Deck Crawls")
        os.makedirs(out, exist_ok=True)
        args = [SF_CLI, "--headless", "--save-crawl", "--timestamped-output", "--output-folder", out,
                "--export-tabs", pc.get("export_tabs") or "Internal:All,Response Codes:Client Error (4xx)"]
        if config:
            args += ["--config", os.path.expanduser(config)]
        if mode == "list":
            lst = [u.strip() for u in (urls or "").splitlines() if u.strip()]
            if not lst:
                raise ValueError("lista de URL-uri e goală")
            fpath = os.path.join(out, "lista-%d.txt" % int(time.time()))
            with open(fpath, "w") as f:
                f.write("\n".join(lst) + "\n")
            args += ["--crawl-list", fpath]
        else:
            if not url:
                raise ValueError("lipsește URL-ul")
            args += ["--crawl", url]
        self.sf.update(log=[], progress=None, started=time.time(), out=out)
        if SIM:
            log_sim(*args)
            self.sf["proc"] = subprocess.Popen(["sleep", "8"])
            self.sf["log"] = ["(simulat) crawl pornit"]
            return "Crawl pornit (simulat)"
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.sf["proc"] = p

        def reader():
            for line in p.stdout:
                line = line.strip()
                if not line:
                    continue
                self.sf["log"].append(line[-200:])
                self.sf["log"] = self.sf["log"][-50:]
                m = re.search(r"(\d{1,3}(?:\.\d+)?)\s?%", line)
                if m:
                    self.sf["progress"] = float(m.group(1))
                m = re.search(r"[Cc]ompleted[=: ]+(\d+).*?[Ww]aiting[=: ]+(\d+)", line)
                if m:
                    done, wait = int(m.group(1)), int(m.group(2))
                    self.sf["progress"] = round(100.0 * done / max(1, done + wait), 1)
            uiauto.notify("Screaming Frog", "Crawl terminat. Rezultatele sunt în %s" % out)
            self.event(type="toast", msg="🕷 Crawl terminat")
        threading.Thread(target=reader, daemon=True).start()
        return "Crawl pornit în fundal"

    def sf_cmd(self, b):
        cmd = b.get("cmd")
        for k in ("mode", "url", "list", "config"):
            if k in b:
                self.sf[k] = b[k]
        if cmd == "save":
            return "Salvat"
        if cmd == "cli_start":
            return self.sf_cli(self.sf["mode"], self.sf["url"], self.sf["list"], self.sf["config"])
        if cmd == "cli_stop":
            p = self.sf["proc"]
            if p is not None and p.poll() is None:
                p.terminate()
                return "Crawl oprit"
            return "Nu rulează niciun crawl"
        if cmd == "open_out":
            run(["open", self.sf["out"] or os.path.expanduser("~/Documents/Mac Deck Crawls")])
            return "Folder deschis"
        # controlul ferestrei Screaming Frog (Accessibility)
        names = self.page_cfg("sfrog").get("buttons") or {}
        if cmd == "gui_mode":
            uiauto.activate(SF_APP)
            uiauto.click_menu(SF_APP, ["Mode", "List" if self.sf["mode"] == "list" else "Spider"])
            return "Mod: " + ("List" if self.sf["mode"] == "list" else "Spider")
        if cmd in ("gui_start", "gui_pause", "gui_stop"):
            uiauto.activate(SF_APP)
            if cmd == "gui_start" and self.sf["mode"] == "spider" and self.sf["url"] and not SIM:
                try:  # încearcă să completeze câmpul de URL
                    osa('tell application "System Events" to tell process "%s" to set value of text field 1 of window 1 to "%s"'
                        % (SF_APP, self.sf["url"].replace('"', "")))
                except RuntimeError:
                    pass
            wanted = {"gui_start": names.get("start") or ["Start", "Resume"],
                      "gui_pause": names.get("pause") or ["Pause"],
                      "gui_stop": names.get("stop") or ["Stop", "Clear"]}[cmd]
            hit = uiauto.click_named(SF_APP, wanted)
            if not hit:
                raise RuntimeError("nu găsesc butonul %s în Screaming Frog (vezi Diagnostic în configurator)" % "/".join(wanted))
            return hit
        raise ValueError("comandă necunoscută")

    def crawl_current(self):
        url = chrome.active_url() if not SIM else "https://example.com/pagina"
        if not url or not url.startswith("http"):
            raise RuntimeError("nu găsesc un site în tab-ul activ din Chrome")
        if self.sf["proc"] is not None and self.sf["proc"].poll() is None:
            raise RuntimeError("un crawl rulează deja")
        p = urlsplit(url)
        root = "%s://%s/" % (p.scheme, p.netloc)
        self.sf.update(mode="spider", url=root)
        default = (self.page_cfg("sfrog").get("configs") or [{}])[0].get("path")
        self.sf_cli("spider", root, config=default)
        self.event(type="open-page", page="sfrog")
        return "Crawl pornit: " + p.netloc

    # ---------------------------------------------------------------- MeetGeek
    def meetgeek_view(self, fresh=False):
        pc = self.page_cfg("meetgeek")
        app = pc.get("app") or "MeetGeek"
        if not fresh and time.time() - self._mg_cache[0] < 5 and self._mg_cache[1]:
            return self._mg_cache[1]
        running = SIM or bool(run(["pgrep", "-f", app], check=False))
        rec = uiauto.exists_named(app, pc.get("stop_names") or ["Stop recording", "Stop Recording", "Oprește înregistrarea"]) if running else False
        v = {"running": running, "recording": rec, "keys": pc.get("toggle_keys") or ""}
        self._mg_cache = (time.time(), v)
        return v

    def meetgeek_toggle(self):
        pc = self.page_cfg("meetgeek")
        app = pc.get("app") or "MeetGeek"
        if pc.get("toggle_keys"):
            _keys(pc["toggle_keys"], app if pc.get("keys_need_focus") else None)
            self._mg_cache = (0, None)
            return "Scurtătură trimisă"
        rec = self.meetgeek_view(fresh=True)["recording"]
        names = (pc.get("stop_names") or ["Stop recording", "Stop Recording", "Oprește înregistrarea"]) if rec else \
                (pc.get("start_names") or ["Start recording", "Start Recording", "Record", "Începe înregistrarea"])
        hit = uiauto.click_named(app, names)
        self._mg_cache = (0, None)
        if not hit:
            raise RuntimeError("nu găsesc butonul în MeetGeek (vezi Diagnostic în configurator)")
        return ("Înregistrare oprită" if rec else "Înregistrare pornită")

    # ---------------------------------------------------------------- Pomodoro
    def _timer_view(self):
        t = self.timer
        durs = self.page_cfg("timer")
        full = int(durs.get(t["mode"], 25 if t["mode"] == "work" else 5)) * 60
        if t["running"] and t["ends_at"]:
            left = max(0, int(t["ends_at"] - time.time()))
        else:
            left = t["left"] if t["left"] is not None else full
        return {"mode": t["mode"], "running": t["running"], "left": left, "full": full, "round": t["round"]}

    def timer_cmd(self, cmd):
        t = self.timer
        v = self._timer_view()
        if cmd == "start":
            t.update(running=True, ends_at=time.time() + v["left"])
        elif cmd == "pause":
            t.update(running=False, left=v["left"], ends_at=None)
        elif cmd == "toggle":
            return self.timer_cmd("pause" if t["running"] else "start")
        elif cmd == "reset":
            t.update(running=False, ends_at=None, left=None)
        elif cmd == "skip":
            t.update(mode="break" if t["mode"] == "work" else "work", running=False, ends_at=None, left=None)
        self.set_live(timer=self._timer_view())
        return {"start": "Timer pornit", "pause": "Pauză", "reset": "Resetat", "skip": "Sărit"}.get(cmd, "")

    # ---------------------------------------------------------------- audio, ferestre
    def audio_view(self):
        if SIM:
            return {"available": True, "devices": ["MacBook Pro Speakers", "AirPods Pro", "LG UltraFine"],
                    "current": "MacBook Pro Speakers"}
        b = _bin(SWITCH_AUDIO)
        if not b:
            return {"available": False, "hint": "Instalează o dată: brew install switchaudio-osx"}
        devs = [l.strip() for l in run([b, "-a", "-t", "output"]).splitlines() if l.strip()]
        cur = run([b, "-c", "-t", "output"]).strip()
        return {"available": True, "devices": devs, "current": cur}

    def audio_set(self, name):
        if SIM:
            log_sim("audio", name)
            return "Ieșire: " + name
        b = _bin(SWITCH_AUDIO)
        if not b:
            raise RuntimeError("Instalează: brew install switchaudio-osx")
        run([b, "-s", name, "-t", "output"])
        return "Ieșire: " + name

    def window(self, op):
        out = run(["osascript", "-l", "JavaScript", os.path.join(SCRIPTS, "window.js"), op], timeout=10)
        if out == "no-window":
            raise RuntimeError("nu există o fereastră activă")
        return {"left": "Stânga", "right": "Dreapta", "top": "Sus", "bottom": "Jos", "full": "Tot ecranul",
                "center": "Centru", "next": "Monitorul următor"}.get(op, op)

    # ---------------------------------------------------------------- pagini: stare
    def page_state(self, pid):
        if pid == "activity":
            return MONITOR.snapshot()
        if pid == "spotify":
            sp = self.live.get("spotify")
            if not SIM and sp is None:
                try:
                    sp = chrome.js_json("open.spotify.com", SPOTIFY_STATE_JS)
                except chrome.ChromeError as e:
                    return {"error": str(e)}
            if SIM:
                sp = {"title": "Strobe", "artist": "deadmau5", "art": "", "playing": True}
            return {"track": sp}
        if pid == "meet":
            return {"meet": self.live.get("meet") if not SIM else
                    {"in_call": True, "mic_on": True, "cam_on": False, "hand": False, "captions": False}}
        if pid == "claude":
            pc = self.page_cfg("claude")
            return {"pinned": pc.get("pinned") or [], "artifacts": pc.get("artifacts") or []}
        if pid == "sfrog":
            return self.sf_view()
        if pid == "meetgeek":
            return self.meetgeek_view()
        if pid == "voice":
            return {"templates": self.page_cfg("voice").get("templates") or []}
        if pid == "snippets":
            return {"items": self.page_cfg("snippets").get("items") or []}
        if pid == "timer":
            return {"timer": self._timer_view()}
        if pid == "analyze":
            url = "https://example.com/pagina" if SIM else chrome.active_url()
            return {"url": url, "tools": self.page_cfg("analyze").get("tools") or []}
        if pid == "audio":
            return self.audio_view()
        if pid == "windows":
            return {}
        return {}

    # ---------------------------------------------------------------- pagini: comenzi
    def page_cmd(self, pid, b):
        cmd = b.get("cmd")
        if pid == "activity" and cmd == "kill":
            return MONITOR.kill(b.get("pid"))
        if pid == "spotify":
            if cmd == "search":
                q = (b.get("q") or "").strip()
                if not q:
                    raise ValueError("scrie ceva de căutat")
                chrome.set_url("open.spotify.com", "https://open.spotify.com/search/" + quote(q))
                return "Caut: " + q
            ids = {"playpause": "control-button-playpause", "next": "control-button-skip-forward",
                   "prev": "control-button-skip-back", "shuffle": "control-button-shuffle",
                   "repeat": "control-button-repeat"}
            if cmd in ids:
                if SIM:
                    log_sim("spotify", cmd)
                    return "OK"
                r = chrome.js("open.spotify.com", SPOTIFY_CLICK_JS % json.dumps(ids[cmd]))
                if r is None:
                    raise RuntimeError("Spotify nu e deschis în Chrome")
                if r == "notfound":
                    raise RuntimeError("nu găsesc butonul în pagina Spotify")
                time.sleep(0.4)
                try:
                    self.set_live(spotify=chrome.js_json("open.spotify.com", SPOTIFY_STATE_JS))
                except chrome.ChromeError:
                    pass
                return "OK"
        if pid == "meet":
            if SIM:
                log_sim("meet", cmd)
                return "OK"
            tab = next((t["url"] for t in chrome.tabs() if MEET_CALL_RE.match(t["url"])), None)
            if not tab:
                raise RuntimeError("nu ești într-un apel Google Meet")
            match = MEET_CALL_RE.match(tab).group(0)
            r = chrome.js(match, MEET_JS % json.dumps(cmd))
            if r == "notfound" and cmd in MEET_KEYS:
                chrome.open_url(tab, match)  # aduce tab-ul în față
                time.sleep(0.3)
                _keys(MEET_KEYS[cmd])
            elif r == "notfound":
                raise RuntimeError("nu găsesc butonul în Meet")
            time.sleep(0.4)
            self.set_live(meet=chrome.js_json(match, MEET_JS % "null"))
            return "OK"
        if pid == "claude":
            lst = self.page_cfg("claude").get(b.get("list") or "pinned") or []
            i = int(b.get("index", -1))
            if not 0 <= i < len(lst):
                raise ValueError("element inexistent")
            it = lst[i]
            return self.claude(it.get("name"), it.get("prompt") if b.get("with_prompt", True) else None)
        if pid == "sfrog":
            return self.sf_cmd(b)
        if pid == "meetgeek" and cmd == "toggle":
            return self.meetgeek_toggle()
        if pid == "voice" and cmd == "send":
            text = (b.get("text") or "").strip()
            if not text:
                raise ValueError("textul e gol")
            tpls = self.page_cfg("voice").get("templates") or []
            i = b.get("template")
            if i is not None and 0 <= int(i) < len(tpls):
                text = tpls[int(i)].get("text", "{text}").replace("{text}", text)
            return self.claude(prompt=text, new_chat=True)
        if pid == "snippets" and cmd == "paste":
            items = self.page_cfg("snippets").get("items") or []
            it = items[int(b.get("index"))]
            uiauto.paste_text(it.get("text", ""), press_return=bool(it.get("enter")))
            return "Lipit: " + it.get("label", "")
        if pid == "timer":
            return self.timer_cmd(cmd)
        if pid == "analyze" and cmd == "open":
            url = b.get("url") or ("https://example.com/pagina" if SIM else chrome.active_url())
            if not url:
                raise RuntimeError("nu găsesc tab-ul activ din Chrome")
            tool = (self.page_cfg("analyze").get("tools") or [])[int(b.get("index"))]
            dom = urlsplit(url).netloc
            target = tool["url"].replace("{url}", quote(url, safe="")).replace("{domain}", dom).replace("{raw}", url)
            chrome.open_url(target, new_tab=True)
            return tool.get("label", "Deschis")
        if pid == "audio" and cmd == "set":
            return self.audio_set(b.get("name"))
        if pid == "windows":
            return self.window(cmd)
        raise ValueError("comandă necunoscută")
