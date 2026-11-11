"""Configurația deck-ului: valori implicite, încărcare, salvare, reîncărcare la modificare."""
import copy
import json
import os
import threading
import time

HOME = os.path.expanduser(os.environ.get("MACDECK_HOME", "~/.macdeck"))
CONFIG_PATH = os.path.join(HOME, "config.json")

PLAN_SAPT = (
    "Fă-mi planificarea săptămânală, citește Gmail, Slack, CRM, MeetGeek și fă-mi "
    "planificarea în Notion. Dă-mi și aici informația."
)
PLAN_ZI = "Fă-mi planificarea zilnică și adaugă în Notion task-urile."


def _app(id, label, app, **kw):
    b = {"id": id, "label": label, "action": {"type": "app", "app": app}}
    b.update(kw)
    return b


def _chrome(id, label, url, **kw):
    b = {"id": id, "label": label, "action": {"type": "chrome", "url": url}}
    match = kw.pop("match", None)
    if match:
        b["action"]["match"] = match
    b.update(kw)
    return b


def _soon(id, label, glyph, phase, **kw):
    b = {"id": id, "label": label, "icon": {"type": "glyph", "name": glyph},
         "action": {"type": "soon", "phase": phase}}
    b.update(kw)
    return b



CLAUDE_PINNED = [
    "Raport zilnic echipă David", "Dashboard Tehnic", "Rapoarte scădere SEO Gets (78 clienți)",
    "Dashboard specialist cu 1-1-uri", "Planificare săptămânală workflow",
    "Rapoarte Banca Transilvania și subsidiare (fork)", "Trenduri SEO Gets", "Raport echipă Technical SEO",
    "Portofoliu SEO & GEO pe echipe", "Plan săptămânal",
]

DEFAULT_PAGES = {
    "spotify": {"title": "Spotify"},
    "meet": {"title": "Google Meet"},
    "activity": {"title": "Activity Monitor"},
    "claude": {
        "title": "Claude",
        "pinned": [{"name": n} for n in CLAUDE_PINNED],
        "artifacts": [{"name": n} for n in CLAUDE_PINNED[:6]],
    },
    "sfrog": {
        "title": "Screaming Frog",
        "configs": [],
        "output_folder": "~/Documents/Mac Deck Crawls",
        "export_tabs": "Internal:All,Response Codes:Client Error (4xx)",
    },
    "meetgeek": {
        "title": "MeetGeek",
        "app": "MeetGeek",
        "start_names": ["Start recording", "Start Recording", "Record", "Începe înregistrarea"],
        "stop_names": ["Stop recording", "Stop Recording", "Oprește înregistrarea"],
        "toggle_keys": "",
    },
    "voice": {
        "title": "Prompt vocal",
        "templates": [
            {"label": "Direct", "text": "{text}"},
            {"label": "Rezumă", "text": "Rezumă pe scurt, în română:\n\n{text}"},
            {"label": "Email", "text": "Scrie un email profesionist în română pe baza notițelor:\n\n{text}"},
            {"label": "Task-uri Notion", "text": "Transformă notițele în task-uri și adaugă-le în Notion:\n\n{text}"},
        ],
    },
    "snippets": {
        "title": "Snippets",
        "items": [
            {"label": "Mulțumesc, revin", "text": "Mulțumesc! Revin cu un răspuns în cursul zilei."},
            {"label": "Raport atașat", "text": "Bună ziua,\n\nVă trimit atașat raportul SEO pentru perioada curentă.\n\nO zi bună,\nFlorin"},
            {"label": "Checklist SEO", "text": "- Title & meta description\n- H1 unic\n- Canonical\n- Indexabil\n- Schema\n- Viteză (CWV)\n- Linkuri interne"},
        ],
    },
    "timer": {"title": "Pomodoro", "work": 25, "break": 5},
    "analyze": {
        "title": "Analizează pagina",
        "tools": [
            {"label": "PageSpeed Insights", "url": "https://pagespeed.web.dev/analysis?url={url}"},
            {"label": "Search Console (inspectare)",
             "url": "https://search.google.com/search-console/inspect?resource_id=sc-domain%3A{domain}&id={url}"},
            {"label": "Rich Results Test", "url": "https://search.google.com/test/rich-results?url={url}"},
            {"label": "Schema validator", "url": "https://validator.schema.org/#url={url}"},
            {"label": "Google site:", "url": "https://www.google.com/search?q=site%3A{domain}"},
            {"label": "Wayback Machine", "url": "https://web.archive.org/web/*/{raw}"},
        ],
    },
    "audio": {"title": "Ieșire audio"},
    "windows": {"title": "Ferestre"},
    "numpad": {"title": "Num pad", "send_to": ""},
}

DEFAULT_INTEGRATIONS = {
    "claude": {"app": "Claude", "search_keys": "cmd+k", "new_chat_keys": "cmd+n",
               "delays": {"activate": 0.8, "search": 0.7, "results": 1.2, "open": 2.0}},
    "calendar": {"ical_url": ""},
    "focus": {"on_shortcut": "Mac Deck Focus On", "off_shortcut": "Mac Deck Focus Off", "during_meet": False},
}

DEFAULT_PROFILES = [
    {"name": "Birou", "days": [1, 2, 3, 4, 5], "from": "08:00", "to": "19:00"},
    {"name": "Acasă", "days": [1, 2, 3, 4, 5, 6, 7], "from": "00:00", "to": "23:59"},
]


def _page_btn(id, label, glyph, page, **kw):
    b = {"id": id, "label": label, "icon": {"type": "glyph", "name": glyph},
         "action": {"type": "page"}, "page": page}
    b.update(kw)
    return b


NEW_BUTTONS_SET2 = [
    {"id": "next-meeting", "label": "Următorul meeting", "icon": {"type": "glyph", "name": "clock"},
     "action": {"type": "next_meeting"}, "dynamic": "next_meeting"},
    {"id": "start-day", "label": "Pornește ziua", "icon": {"type": "glyph", "name": "sunrise"},
     "action": {"type": "sequence", "delay": 0.8, "steps": [
         {"type": "chrome", "url": "https://mail.google.com"},
         {"type": "chrome", "url": "https://calendar.google.com"},
         {"type": "app", "app": "Slack"},
         {"type": "chrome", "url": "https://david01.du.ro/daily/management/dashboard/florin"},
         {"type": "claude", "item": "Raport zilnic echipă David",
          "prompts": [{"label": "Pornește raportul", "text": "pornește raportul"}]},
     ]}},
    _page_btn("voice", "Prompt vocal", "mic", "voice"),
    _page_btn("snippets", "Snippets", "text", "snippets"),
    {"id": "focus", "label": "Focus", "icon": {"type": "glyph", "name": "moon"},
     "action": {"type": "focus"}, "state": "focus"},
    _page_btn("pomodoro", "Pomodoro", "timer", "timer", state="timer", dynamic="timer",
              long={"type": "timer", "cmd": "toggle", "label": "Start / Pauză"}),
    _page_btn("analyze", "Analizează pagina", "search", "analyze"),
    {"id": "crawl-current", "label": "Crawl site curent", "icon": {"type": "glyph", "name": "spider"},
     "action": {"type": "crawl_current"}},
    {"id": "mic-mute", "label": "Mic mute", "icon": {"type": "glyph", "name": "mic-off"},
     "action": {"type": "mic_mute"}, "state": "mic_muted"},
    _page_btn("audio-out", "Ieșire audio", "headphones", "audio"),
]

NEW_WINDOWS = _page_btn("windows", "Ferestre", "layout", "windows")
NEW_NUMPAD = _page_btn("numpad", "Num pad", "numpad", "numpad", auto_page=False)


DEFAULT_CONFIG = {
    "version": 3,
    "ui": {
        "columns": 5,
        "rows": 3,
        "sleep_minutes": 5,
        "sound": True,
        "haptics": True,
        "profile": "auto",
        "auto_switch": True,
        "auto_close": True,
    },
    "sets": [
        {
            "name": "Lucru zilnic",
            "buttons": [
                _chrome("gmail", "Gmail", "https://mail.google.com",
                        long={"type": "chrome", "url": "https://mail.google.com/mail/?view=cm&fs=1",
                              "new_tab": True, "label": "Email nou"}),
                _app("claude", "Claude", "Claude", page="claude"),
                _app("slack", "Slack", "Slack"),
                _chrome("spotify", "Spotify", "https://open.spotify.com", page="spotify", dynamic="spotify",
                        long={"type": "spotify", "cmd": "playpause", "label": "Play / Pauză"}),
                _chrome("gemini", "Gemini", "https://gemini.google.com"),

                {"id": "raport", "label": "Raport zilnic", "icon": {"type": "glyph", "name": "report"},
                 "action": {"type": "claude", "item": "Raport zilnic echipă David",
                            "prompts": [{"label": "Pornește raportul", "text": "pornește raportul"}]}},
                {"id": "planificare", "label": "Planificare", "icon": {"type": "glyph", "name": "calendar-check"},
                 "action": {"type": "claude", "item": "Planificare săptămânală workflow",
                            "prompts": [
                                {"label": "📅 Săptămânal", "text": PLAN_SAPT},
                                {"label": "☀️ Zilnic", "text": PLAN_ZI},
                            ]}},
                _chrome("david", "Dashboard David",
                        "https://david01.du.ro/daily/management/dashboard/florin"),
                _app("finder", "Finder", "Finder"),
                {"id": "chrome-fgirtan", "label": "Chrome fgirtan",
                 "icon": {"type": "app", "app": "Google Chrome"},
                 "action": {"type": "chrome_profile", "email": "fgirtan@gmail.com"}},

                _chrome("seogets", "SEO Gets", "https://seogets.com/", match="https://seogets.com"),
                _chrome("dwf", "DWF", "https://app.dwf.ro/login", match="https://app.dwf.ro"),
                _app("sfrog", "Screaming Frog", "Screaming Frog SEO Spider", page="sfrog"),
                _app("meetgeek", "MeetGeek", "MeetGeek", page="meetgeek"),
                _chrome("notion", "Notion",
                        "https://app.notion.com/p/020088990c49423d82f7f29c5b91ff3e?v=7a2f6b94707842d1ac572d3924844823",
                        match="020088990c49423d82f7f29c5b91ff3e"),
            ],
        },
        {
            "name": "Întâlniri, productivitate, SEO",
            "buttons": [
                _chrome("meet", "Google Meet", "https://meet.google.com", page="meet", state="meet_call"),
                _chrome("calendar", "Calendar", "https://calendar.google.com",
                        long={"type": "chrome", "url": "https://calendar.google.com/calendar/r/eventedit",
                              "new_tab": True, "label": "Eveniment nou"}),
                *NEW_BUTTONS_SET2,
                _app("safari", "Safari", "Safari"),
                _app("mission", "Mission Control", "Mission Control"),
                _app("activity", "Activity Monitor", "Activity Monitor", page="activity"),
            ],
        },
        {
            "name": "Control Mac",
            "buttons": [
                NEW_WINDOWS,
                {"id": "screenshot", "label": "Screenshot", "icon": {"type": "glyph", "name": "camera"},
                 "action": {"type": "screenshot"},
                 "long": {"type": "screenshot", "mode": "screen-recording", "label": "Înregistrare ecran"}},
                {"id": "lock", "label": "Blochează Mac", "icon": {"type": "glyph", "name": "lock"},
                 "action": {"type": "lock"}},
                {"id": "display-off", "label": "Stinge ecranul", "icon": {"type": "glyph", "name": "monitor-off"},
                 "action": {"type": "display_sleep"}},
                {"id": "caffeinate", "label": "Ține treaz", "icon": {"type": "glyph", "name": "coffee"},
                 "action": {"type": "caffeinate"}, "state": "caffeinate"},
                NEW_NUMPAD,
            ],
        },
    ],
    "pages": copy.deepcopy(DEFAULT_PAGES),
    "integrations": copy.deepcopy(DEFAULT_INTEGRATIONS),
    "profiles": copy.deepcopy(DEFAULT_PROFILES),
}


def migrate(data):
    """Aduce o configurație mai veche la versiunea curentă, păstrând modificările utilizatorului."""
    changed = False
    if data.get("version", 1) < 2:
        repl = {b["id"]: b for b in NEW_BUTTONS_SET2 + [NEW_WINDOWS]}
        for s in data.get("sets", []):
            for i, b in enumerate(s.get("buttons", [])):
                if not b:
                    continue
                if b.get("action", {}).get("type") == "soon" and b.get("id") in repl:
                    s["buttons"][i] = copy.deepcopy(repl[b["id"]])
                elif b.get("id") == "spotify":
                    b.setdefault("long", {"type": "spotify", "cmd": "playpause", "label": "Play / Pauză"})
                    b.setdefault("dynamic", "spotify")
                elif b.get("id") == "meet":
                    b.setdefault("state", "meet_call")
        pages = data.setdefault("pages", {})
        for k, v in DEFAULT_PAGES.items():
            if k not in pages:
                pages[k] = copy.deepcopy(v)
            else:
                pages[k].pop("phase", None)
                for kk, vv in v.items():
                    pages[k].setdefault(kk, copy.deepcopy(vv))
        integ = data.setdefault("integrations", {})
        for k, v in DEFAULT_INTEGRATIONS.items():
            integ.setdefault(k, copy.deepcopy(v))
        data.setdefault("profiles", copy.deepcopy(DEFAULT_PROFILES))
        data.setdefault("ui", {}).setdefault("profile", "auto")
        data["version"] = 2
        changed = True
    if data.get("version", 1) < 3:
        data.setdefault("pages", {}).setdefault("numpad", copy.deepcopy(DEFAULT_PAGES["numpad"]))
        ids = {b.get("id") for s in data.get("sets", []) for b in s.get("buttons", []) if b}
        if "numpad" not in ids and data.get("sets"):
            cols = (data.get("ui") or {}).get("columns", 5) * (data.get("ui") or {}).get("rows", 3)
            # pe setul cu „Ferestre” (Control Mac), altfel pe ultimul set; primul loc liber
            target = next((s for s in data["sets"] if any(b and b.get("id") == "windows" for b in s.get("buttons", []))),
                          data["sets"][-1])
            btns = target.setdefault("buttons", [])
            slot = next((i for i, b in enumerate(btns) if b is None), len(btns))
            if slot < cols:
                if slot == len(btns):
                    btns.append(copy.deepcopy(NEW_NUMPAD))
                else:
                    btns[slot] = copy.deepcopy(NEW_NUMPAD)
        data["version"] = 3
        changed = True
    return changed


class Config:
    """Ține configurația în memorie și o reîncarcă atunci când fișierul se schimbă pe disc."""

    def __init__(self, path=CONFIG_PATH, on_change=None):
        self.path = path
        self.on_change = on_change
        self._lock = threading.Lock()
        self._mtime = None
        self.data = None
        self.load()

    def load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self.save(copy.deepcopy(DEFAULT_CONFIG))
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print("  ! config.json invalid (%s) - folosesc configurația anterioară" % e)
            return False
        if migrate(data):
            print("  ✓ Configurația a fost actualizată la versiunea %s (butoanele tale au fost păstrate)." % data["version"])
            self.save(data)
            return True
        with self._lock:
            self.data = data
            self._mtime = os.path.getmtime(self.path)
        return True

    def save(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
        with self._lock:
            self.data = data
            self._mtime = os.path.getmtime(self.path)

    def get(self):
        with self._lock:
            return self.data

    def find_button(self, button_id):
        for s in self.get().get("sets", []):
            for b in s.get("buttons", []):
                if b and b.get("id") == button_id:
                    return b
        return None

    def watch(self, interval=1.0):
        def loop():
            while True:
                time.sleep(interval)
                try:
                    m = os.path.getmtime(self.path)
                except OSError:
                    continue
                if m != self._mtime and self.load() and self.on_change:
                    self.on_change()
        threading.Thread(target=loop, daemon=True).start()
